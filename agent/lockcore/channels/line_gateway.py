"""LINE 通道 — webhook 接入,把 LINE 訊息接到 LockCore AgentLoop。

流程:
  LINE 平台 --POST /callback--> 本服務(驗 X-Line-Signature)
    → 取 event.source.user_id(當 user_id)+ 文字/照片
    → resolve_identity → (tenant, user_id)
    → AgentLoop._process_message → 回覆文字
    → LINE reply API 回給客人

訊息型別(2026-07-03 VLN 修復):
  - 文字 → 原有 turn 流程。
  - 照片 → 以 Blob API 下載到 get_media_dir("line") → InboundMessage(media=[路徑])
    → context 既有 vision 管線(base64 image_url)交給 LLM 理解。
  - 其他(貼圖/語音/影片/檔案/位置)→ 回友善話術(原本是靜默丟棄=已讀不回)。

身分:user_id 直接用 LINE 的 userId(per official-account 穩定);tenant 先固定單一店家。
機密(channel secret / access token)走 .env,不入庫。
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from pathlib import Path
from typing import Any

from loguru import logger

from lockcore.bus.events import InboundMessage

# LINE 單則文字訊息上限 5000 字,留點 buffer。
_LINE_TEXT_LIMIT = 4900

# 內部錯誤外洩防線:LiteLLMProvider 失敗時 content 會是 "[litellm error] ..."。
# 這類字串(或空回覆)絕不可原文丟給客人,改回友善話術。
_ERROR_SENTINEL = "[litellm error]"
_FALLBACK_REPLY = "不好意思,系統忙線中,請稍後再試,或留言由專員與您聯繫 🙏"

# VLN(2026-07-03):非文字/照片型別的友善回覆(原本靜默丟棄=已讀不回)。
_UNSUPPORTED_MEDIA_REPLY = (
    "不好意思,我目前只看得懂文字和照片 🙏\n"
    "麻煩您用文字描述問題,或直接拍一張門鎖的照片傳給我,我馬上為您服務!"
)
_IMAGE_DOWNLOAD_FAIL_REPLY = "照片好像沒有傳送成功,麻煩您再傳一次,謝謝 🙏"

# 對話已升級為人工接管、客人又傳訊息時的自動安撫語(AI 暫停期間唯一會送的話)。
# 純文字(LINE 不 render markdown);不承諾時間、不報價。
_HANDOVER_WAIT_REPLY = (
    "您好,目前已由真人專員接手為您服務 🙏\n"
    "麻煩您稍候,專員看到訊息後會盡快回覆您。"
)
# 節流:接管期間客人可能連傳多則,若每則都回「請稍候」會洗版。以 session 為 key、
# 記上次送出時間(process 內記憶,單實例;fail-open:查不到就送)。冷卻內不重複送,
# 但客人訊息仍照常持久化讓真人看得到。重啟後至多多送一次(可接受)。
_HANDOVER_NOTICE_COOLDOWN_SEC = 600.0  # 10 分鐘
_handover_notice_at: dict[str, float] = {}


def _should_notify_handover(session_key: str) -> bool:
    """接管期間本則是否該送「請稍候」提示(冷卻節流,避免洗版)。fail-open。"""
    try:
        now = time.monotonic()
        last = _handover_notice_at.get(session_key)
        if last is not None and now - last < _HANDOVER_NOTICE_COOLDOWN_SEC:
            return False
        _handover_notice_at[session_key] = now
        return True
    except Exception:  # noqa: BLE001 — 節流失敗不可阻斷提示,寧可多送
        return True


# 對話管理(後台)持久化用的型別標記。
_MEDIA_KIND_MARKERS = {
    "sticker": "[貼圖]",
    "audio": "[語音訊息]",
    "video": "[影片]",
    "file": "[檔案]",
    "location": "[位置訊息]",
}

# 方案 A:對話旁路持久化。把每輪「客人訊息 + AI 回覆」POST 給 API,寫進
# conversations/messages,使工單/對話後台能重新渲染對話歷史。env 未設 → 略過
# (不破壞無此設定的既有部署);失敗一律 fail-soft(只 log,絕不阻斷回客人)。
#
# 逾時分兩種：
# - persist POST 在「回覆送出後」fire-and-forget，拉長到 20s 以撐過 API 冷啟動
#   （Cloud Run min-instances=0 時冷啟 ~10s），不影響客人回覆延遲。
# - handover 查詢在「回覆前」會阻塞回覆，維持短逾時 + fail-soft（查不到就 AI 照常回），
#   避免冷啟動拖慢客人首次回覆。
_PERSIST_TIMEOUT_SEC = 20.0
_HANDOVER_CHECK_TIMEOUT_SEC = 5.0


# ── CR-0120:連續訊息合併(trailing debounce)────────────────────────────
# 客人短時間連傳多則,原本每則各開一個併發 turn(逐則各回一次、history 寫入
# 交錯)。改為:以「最後一則」起算靜默視窗,期間有新訊息就重置計時;到期把
# 整批合併成一輪 turn、一次回覆(業主 2026-07-07 裁決,CR-0120)。

_DEBOUNCE_DEFAULT_SECONDS = 5.0
_DEBOUNCE_MAX_SECONDS = 30.0
_DEBOUNCE_MAX_BATCH = 10  # 防餓死:連傳不停時滿 N 則強制觸發,AI 不會永遠沉默


def _debounce_seconds() -> float:
    """讀 LINE_DEBOUNCE_SECONDS(每次重讀,測試可 monkeypatch;0=停用走直通)。"""
    raw = (os.environ.get("LINE_DEBOUNCE_SECONDS") or "").strip()
    if not raw:
        return _DEBOUNCE_DEFAULT_SECONDS
    try:
        val = float(raw)
    except ValueError:
        logger.warning(
            "LINE_DEBOUNCE_SECONDS 非數值({}),用預設 {}s", raw, _DEBOUNCE_DEFAULT_SECONDS
        )
        return _DEBOUNCE_DEFAULT_SECONDS
    return max(0.0, min(val, _DEBOUNCE_MAX_SECONDS))


class _TurnDebouncer:
    """per-session 訊息緩衝 + 靜默計時器(CR-0120)。

    - push():訊息進 buffer,重置該 session 計時器(計算最後一則的時間)。
    - 靜默滿 delay → 取走整批交給 fire;fire 以 per-session lock 串行——
      上一輪 turn 未完成時下一批排隊等,同時修掉原本併發 turn 的 race。
    - buffer 滿 max_batch → 立即強制觸發(防餓死)。
    - 狀態在記憶體(重啟即失),與 handover notice 節流器同等級 fail-soft。
    """

    def __init__(self, delay_getter, fire, max_batch: int = _DEBOUNCE_MAX_BATCH):
        self._delay_getter = delay_getter  # () -> float,每批到期時點重讀
        self._fire = fire  # async (key, items) -> None
        self._max_batch = max_batch
        self._buffers: dict[str, list[dict]] = {}
        self._timers: dict[str, asyncio.Task] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def push(self, key: str, item: dict) -> None:
        buf = self._buffers.setdefault(key, [])
        buf.append(item)
        old = self._timers.pop(key, None)
        if old is not None and not old.done():
            old.cancel()
        if len(buf) >= self._max_batch:
            # 強制觸發:不註冊回 _timers,之後的 push 不可取消進行中的合併輪
            asyncio.create_task(self._flush(key))
        else:
            self._timers[key] = asyncio.create_task(self._wait_then_flush(key))

    async def _wait_then_flush(self, key: str) -> None:
        try:
            await asyncio.sleep(self._delay_getter())
        except asyncio.CancelledError:
            return  # 新訊息重置計時,由新 timer 接手
        # 到期:讓出 timers 槽位再以獨立 task 執行 flush——此後的 push 屬
        # 「下一批」,不會取消進行中的合併輪(sleep 返回到此處無 await,
        # event loop 內原子,push 不可能插入)。
        if self._timers.get(key) is asyncio.current_task():
            self._timers.pop(key, None)
        asyncio.create_task(self._flush(key))

    async def _flush(self, key: str) -> None:
        items = self._buffers.pop(key, [])
        if not items:
            return
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:  # 串行:上一輪 turn 未完,下一批等它做完
            try:
                await self._fire(key, items)
            except Exception:  # noqa: BLE001 — 背景任務例外不可無聲蒸發
                logger.exception("debounce 合併輪處理失敗 key={}", key[:24])


def _encode_media_for_persist(media_paths: list[str] | None) -> dict:
    """CR-0119:把本輪照片(單張)編成 ingest payload 欄位。失敗回空 dict(fail-soft)。

    LINE 一則照片訊息恰一張圖 → 取 media_paths[0]。base64 原檔,mime 以 magic bytes
    重判(與下載時同一函式,不信副檔名)。
    """
    if not media_paths:
        return {}
    try:
        import base64

        from lockcore.utils.helpers import detect_image_mime

        data = Path(media_paths[0]).read_bytes()
        if not data:
            return {}
        return {
            "media_base64": base64.b64encode(data).decode("ascii"),
            "media_mime": detect_image_mime(data) or "image/jpeg",
        }
    except Exception:  # noqa: BLE001 — 照片編碼失敗不可阻斷文字持久化
        logger.warning("持久化照片編碼失敗(略過,僅送文字)", exc_info=True)
        return {}


async def _persist_turn_safe(
    tenant: str, user_id: str, user_text: str, assistant_text: str,
    media_paths: list[str] | None = None,
) -> None:
    """Fire-and-forget 旁路持久化一輪對話到 API。任何失敗只 log,不 raise。

    media_paths(CR-0119):本輪客人照片的本機路徑 → base64 隨 payload 送 API 落地
    media_service,讓對話管理頁能顯示照片(agent 本機檔案雲端重啟即失,不能只留路徑)。
    """
    base_url = os.environ.get("LOCK_API_BASE_URL")
    # .strip()：secret 值可能帶尾換行（openssl rand | gcloud secrets create 會留 \n），
    # 含換行的 token 放進 HTTP header 會被 httpx 拒（Illegal header value）。
    token = (os.environ.get("INTERNAL_API_TOKEN") or "").strip()
    if not (base_url and token):
        return  # 未設定 bridge → 安靜略過
    payload = {
        "tenant_id": tenant,
        "line_user_id": user_id,
        "session_id": f"{tenant}:{user_id}",
        "user_text": user_text or "",
        "assistant_text": assistant_text or "",
        **_encode_media_for_persist(media_paths),
    }
    try:
        import httpx

        async with httpx.AsyncClient(timeout=_PERSIST_TIMEOUT_SEC) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/api/v1/internal/conversations/ingest",
                json=payload,
                headers={"X-Internal-Token": token},
            )
            if resp.status_code >= 400:
                logger.warning(
                    "對話持久化回 {}:{}", resp.status_code, resp.text[:160]
                )
    except Exception as e:  # noqa: BLE001 — 持久化絕不可影響客服回覆
        logger.warning("對話持久化失敗(已略過,不影響客人): {!r}", e)


async def _handover_active_safe(tenant: str, user_id: str) -> bool:
    """查該對話是否處於人工接管中（CR-0024 Phase 1）。escalated → True 表 AI 應暫停。

    **fail-soft**：bridge env 未設、查不到、逾時或任何錯誤 → 回 False（AI 照常回，
    絕不因為查詢失敗就把客人晾著）。Phase 1 只看 escalated 旗標（全暫停）。
    """
    base_url = os.environ.get("LOCK_API_BASE_URL")
    # .strip()：secret 值可能帶尾換行（openssl rand | gcloud secrets create 會留 \n），
    # 含換行的 token 放進 HTTP header 會被 httpx 拒（Illegal header value）。
    token = (os.environ.get("INTERNAL_API_TOKEN") or "").strip()
    if not (base_url and token):
        return False
    try:
        import httpx

        async with httpx.AsyncClient(timeout=_HANDOVER_CHECK_TIMEOUT_SEC) as client:
            resp = await client.get(
                f"{base_url.rstrip('/')}/api/v1/internal/conversations/handover-state",
                params={"tenant_id": tenant, "session_id": f"{tenant}:{user_id}"},
                headers={"X-Internal-Token": token},
            )
            if resp.status_code >= 400:
                logger.warning("查接管狀態回 {}:{}", resp.status_code, resp.text[:160])
                return False
            return bool(resp.json().get("data", {}).get("escalated", False))
    except Exception as e:  # noqa: BLE001 — 查詢失敗不可阻斷客人，預設 AI 照常回
        logger.warning("查接管狀態失敗（已略過，AI 照常回）: {!r}", e)
        return False


def _latest_escalation_id(esc: Any, tenant: str, user_id: str) -> int:
    """取該 user 最新 escalation id(無則 0)。用來偵測本輪是否新增轉真人紀錄。"""
    if esc is None:
        return 0
    try:
        recs = esc.list_for_user(tenant, user_id, limit=1)
        return recs[0].id if recs else 0
    except Exception:  # noqa: BLE001
        return 0


async def _forward_escalation_safe(
    esc: Any, tenant: str, user_id: str, before_id: int, user_text: str = ""
) -> None:
    """CR-0022:若本輪 agent 觸發了 transfer_to_human(escalation 變新),旁路 POST 給 API
    建 AI 草擬問題卡。env 未設 → 略過;失敗 fail-soft(只 log,不影響客人)。

    **AI 不自轉工單**:這裡只送 escalation,API 端最多建 draft PC;confirm/convert 走客服。
    """
    base_url = os.environ.get("LOCK_API_BASE_URL")
    # .strip()：secret 值可能帶尾換行（openssl rand | gcloud secrets create 會留 \n），
    # 含換行的 token 放進 HTTP header 會被 httpx 拒（Illegal header value）。
    token = (os.environ.get("INTERNAL_API_TOKEN") or "").strip()
    if not (base_url and token) or esc is None:
        return
    try:
        recs = esc.list_for_user(tenant, user_id, limit=1)
    except Exception:  # noqa: BLE001
        return
    if not recs or recs[0].id <= before_id:
        return  # 本輪沒有新 escalation
    rec = recs[0]
    snapshot = dict(rec.facts_snapshot or {})
    # CR-0102：正常路徑（LLM 呼叫 transfer_to_human）的 snapshot 無 phone → 從本輪原話 /
    # facts_block / 原話摘要補抽台灣手機，讓 API 寫進 users.phone（只在空白時）。兜底路徑已自帶。
    if not snapshot.get("phone"):
        p = _extract_phone(
            user_text,
            snapshot.get("facts_block", ""),
            snapshot.get("user_input_excerpt", ""),
        )
        if p:
            snapshot["phone"] = p
    payload = {
        "tenant_id": tenant,
        "line_user_id": user_id,
        "session_id": f"{tenant}:{user_id}",
        "reason": rec.reason or "",
        "is_explicit": bool(rec.is_explicit),
        "facts_snapshot": snapshot,
    }
    try:
        import httpx

        async with httpx.AsyncClient(timeout=_PERSIST_TIMEOUT_SEC) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/api/v1/internal/escalations/ingest",
                json=payload,
                headers={"X-Internal-Token": token},
            )
            if resp.status_code >= 400:
                logger.warning("escalation 轉發回 {}:{}", resp.status_code, resp.text[:160])
    except Exception:  # noqa: BLE001 — 轉發絕不可影響客服回覆
        logger.warning("escalation 轉發失敗(已略過,不影響客人)", exc_info=True)


# CR-0097 方案 A 兜底：LLM tool-calling 不可靠 —— 會生成「已轉接/已安排師傅」話術卻
# 不呼叫 transfer_to_human，案子靜默蒸發（後台收不到問題卡）。偵測「AI 承諾轉接 + 本輪
# escalation 未新增（=沒呼叫工具）」→ 程式補一筆 escalation，讓既有 _forward_escalation
# 仍建問題卡。承諾話術用「完成式/指派式」字樣，降低純資訊提及的誤判。
_HANDOFF_PROMISE_MARKERS: tuple[str, ...] = (
    "已幫您轉接", "已為您轉接", "已轉接", "幫您轉接", "轉接給真人", "轉接給專員",
    "已為您安排", "已幫您安排", "為您安排專員", "安排專員",
    "已登記", "已為您登記",
    "專員會", "專員將", "由專員", "請專員", "真人專員", "專員聯繫", "專員與您",
    "會與您聯繫", "將與您聯繫",
    "安排師傅", "安排技師", "派師傅", "派技師", "師傅到府", "技師到府", "請師傅到",
)


def _promised_handoff(reply: str) -> bool:
    """AI 回應是否「承諾了轉接/安排師傅」（偵測說了卻沒呼叫工具的蒸發）。"""
    if not reply:
        return False
    return any(m in reply for m in _HANDOFF_PROMISE_MARKERS)


# CR-0097+：兜底品牌/型號補抽。CR-0098 自動填只在 LLM 正確呼叫 transfer_to_human(brand=,model=)
# 時生效；但兜底正是「LLM 沒呼叫工具」的情況 → 品牌型號會漏。改由程式從客人原話 / AI 回覆
# deterministic 補抽（不依賴 LLM），沿用既有 facts_snapshot.brand/model 路徑自動填問題卡。
# 品牌清單對齊 lockcore/skills/locksmith-product-knowledge/references/{Brand}/（品牌名穩定、少變）。
_KNOWN_BRANDS: tuple[str, ...] = (
    "Dormakaba", "Chatlock", "Kaadas", "Philips", "Milre", "3E",
)
# 型號 token：品牌後相鄰的英數/中文型號段（到空白或標點為止，上限 30）。
_MODEL_TOKEN_RE = re.compile(r"[A-Za-z0-9一-鿿()（）+.\-]{1,30}")


def _extract_brand_model(*texts: str) -> tuple[str, str]:
    """從客人原話 / AI 回覆找已知品牌 + 相鄰型號 token（CR-0097 兜底用）。

    deterministic、fail-soft：抽不到回 ('', '')。型號為盡力而為的草擬值（客服可更正），
    重點是避免「客人明說了品牌型號卻整欄空白」。
    """
    blob = " ".join(t for t in texts if t).strip()
    if not blob:
        return "", ""
    low = blob.lower()
    for brand in _KNOWN_BRANDS:
        idx = low.find(brand.lower())
        if idx < 0:
            continue
        after = blob[idx + len(brand):].lstrip(" :：-—／/、,，。\t")
        m = _MODEL_TOKEN_RE.match(after)
        return brand, (m.group(0).strip() if m else "")
    return "", ""


# CR-0097+：兜底症狀清洗。兜底時 LLM 沒呼叫工具 → 症狀原本直接用客人原話（含電話/品牌/
# 贅語，「把對話搬進來」）。改 deterministic 去噪：移除電話、品牌/型號（已另存）、開頭
# 「我的門鎖壞了/故障」類贅語，得精簡症狀。fail-soft：剝到太短就退回去噪版、再退原句。
# 註：真正精準的症狀仍由 LLM transfer_to_human(symptom=) 提供（CR-0098）；本函式是 LLM
# 未結構化時的保險，型號/症狀皆為盡力草擬值，客服可更正。
_PHONE_RE = re.compile(r"0?\d{8,}")
# 僅當「[招呼/我的…](門)鎖 + 壞了/故障/有問題/不能用 + 分隔符」整段才剝，避免吃掉
# 「鎖舌卡住」的「鎖」。
_SYMPTOM_LEAD_RE = re.compile(
    r"^(?:我的|我家的|我家|這|那|台|部|個|請問|你好|您好|哈囉|嗨|\s)*"
    r"(?:電子|智慧|智能)?(?:門)?鎖"
    r"(?:壞了|故障了?|有(?:點)?問題|不能用|出問題了?|無法使用)"
    r"(?:[\s，,。、:：!！?？-]+|$)"
)


def _clean_symptom(user_text: str, brand: str = "", model: str = "") -> str:
    """從客人原話去噪得精簡症狀（CR-0097 兜底用）。抽不出有效內容則退回原話。"""
    raw = (user_text or "").strip()
    if not raw:
        return ""
    s = _PHONE_RE.sub(" ", raw)
    for tok in (brand, model):
        if tok:
            s = re.sub(re.escape(tok), " ", s, flags=re.IGNORECASE)
    noise_stripped = " ".join(s.split()).strip("：:，,。、-—  ")
    lead_stripped = _SYMPTOM_LEAD_RE.sub("", noise_stripped, count=1)
    lead_stripped = " ".join(lead_stripped.split()).strip("：:，,。、-—  ")
    # 安全：去開頭後太短（<3 字）→ 用去噪版；再不行 → 原話。
    result = lead_stripped if len(lead_stripped) >= 3 else noise_stripped
    return (result or raw)[:200]


# CR-0102：兜底電話補抽。客人在 LINE 報修常一併留手機（「我電話 0912-345-678」），但
# transfer_to_human 只抽 brand/model/symptom（CR-0098）、兜底也只抽品牌型號（CR-0097），
# 電話從未進 facts → 轉工單時 customer_phone 永遠空。改 deterministic 從對話文字補抽台灣
# 手機，沿 facts_snapshot.phone 由 API 寫進 users.phone（只在空白時填）→ convert 既有邏輯
# 自動帶入。只認手機（09 開頭 10 碼，容 +886 與分隔符）；市話/分機不抽（誤判風險高）。
_PHONE_EXTRACT_RE = re.compile(r"(?:\+?886[\s-]?|0)9(?:[\s-]?\d){8}")


def _extract_phone(*texts: str) -> str:
    """從對話文字補抽台灣手機號 → 正規化 09xxxxxxxx；抽不到回空字串。"""
    for text in texts:
        if not text:
            continue
        m = _PHONE_EXTRACT_RE.search(text)
        if not m:
            continue
        digits = re.sub(r"\D", "", m.group(0))
        if digits.startswith("886"):  # +886 9... → 09...
            digits = "0" + digits[3:]
        if len(digits) == 10 and digits.startswith("09"):
            return digits
    return ""


def _apply_handoff_fallback_safe(
    esc: Any, tenant: str, user_id: str, user_text: str, reply: str, before_id: int
) -> None:
    """CR-0097 方案 A 兜底：AI 回應承諾轉接但本輪未呼叫 transfer_to_human
    （escalation 未新增）→ 補一筆 escalation，使後續 _forward_escalation 仍建問題卡。

    fail-soft：任何錯誤只 log，不影響客人。設計取捨——誤判（純資訊提及）寧可多建卡，
    也不讓真正的報修靜默蒸發（漏建卡 = 客人來過卻沒人知道，後果嚴重得多）。
    """
    if esc is None or not (reply or "").strip():
        return
    if _latest_escalation_id(esc, tenant, user_id) > before_id:
        return  # 本輪 AI 已正常呼叫工具 → 不重複補
    if not _promised_handoff(reply):
        return  # AI 沒承諾轉接 → 不兜底
    try:
        # CR-0097+：兜底也補抽品牌/型號（LLM 沒呼叫工具時的保險）。客人原話常已含裝置，
        # AI 回覆也常複述「品牌/型號：...」→ 兩者合併比對，沿用 CR-0098 自動填問題卡。
        fb_brand, fb_model = _extract_brand_model(user_text, reply)
        # 症狀：去噪後的精簡描述（非原話直搬，不含電話/品牌/開頭贅語）。
        fb_symptom = _clean_symptom(user_text, fb_brand, fb_model)
        fb_phone = _extract_phone(user_text, reply)  # CR-0102：兜底也補抽手機
        esc.log(
            tenant,
            user_id,
            "[兜底] AI 承諾轉接但未呼叫 transfer_to_human（CR-0097）",
            False,
            {
                "user_input_excerpt": (user_text or "")[:200],
                "assistant_excerpt": (reply or "")[:200],
                "fallback": True,
                "brand": fb_brand,
                "model": fb_model,
                "symptom": fb_symptom,
                "phone": fb_phone,
            },
        )
        logger.warning(
            "CR-0097 兜底觸發：AI 承諾轉接卻未呼叫工具，已補 escalation user={} brand={!r} model={!r} symptom={!r}",
            user_id[:8], fb_brand, fb_model, fb_symptom,
        )
    except Exception:  # noqa: BLE001 — 兜底絕不可影響客人
        logger.exception("CR-0097 兜底補 escalation 失敗（已略過，不影響客人）")


async def _route_quote_postback_safe(tenant: str, user_id: str, data: str) -> str | None:
    """CR-0095：解析 LINE 報價 postback（q:a|<quote_id> 同意 / q:r|<quote_id> 拒絕）
    → 旁路 POST 給 API（X-Internal-Token；API 端驗 line_user 擁有此報價 + 走狀態機）。

    回客戶確認文字（同意/拒絕）；非報價 postback 回 None（交由呼叫端略過）。
    fail-soft：bridge env 未設 / 失敗一律回友善訊息，絕不 raise。
    """
    parts = (data or "").split("|", 1)
    if len(parts) != 2 or parts[0] not in ("q:a", "q:r"):
        return None  # 非報價 postback（如 s:a/s:r scope_change，本 CR 未接，走網頁 fallback）
    decision = "accept" if parts[0] == "q:a" else "reject"
    quote_id = parts[1].strip()
    if not quote_id:
        return None

    base_url = os.environ.get("LOCK_API_BASE_URL")
    token = (os.environ.get("INTERNAL_API_TOKEN") or "").strip()
    if not (base_url and token):
        logger.warning("報價 postback 收到但 bridge 未設定（LOCK_API_BASE_URL/INTERNAL_API_TOKEN）")
        return "系統忙線中，請稍後再試或洽客服 🙏"
    try:
        import httpx

        async with httpx.AsyncClient(timeout=_PERSIST_TIMEOUT_SEC) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/api/v1/internal/quotes/{quote_id}:customer-respond",
                json={"tenant_id": tenant, "line_user_id": user_id, "decision": decision},
                headers={"X-Internal-Token": token},
            )
        if resp.status_code >= 400:
            logger.warning("報價回覆轉發回 {}:{}", resp.status_code, resp.text[:160])
            return "您的回覆可能未送達（報價或已失效），請稍後再試或洽客服 🙏"
    except Exception:  # noqa: BLE001 — 轉發絕不可影響客人
        logger.warning("報價回覆轉發失敗（已略過）", exc_info=True)
        return "系統忙線中，請稍後再試或洽客服 🙏"

    if decision == "accept":
        return "已收到您的同意 ✅ 我們將盡快為您安排技師到府服務，感謝您！"
    return "已收到您的回覆 🙏 如需調整報價內容，客服將盡快與您聯繫。"


def load_dotenv(path: str | Path) -> dict[str, str]:
    """極簡 .env 載入器(無外部依賴):把 KEY="value" 設進 os.environ(不覆蓋既有)。"""
    p = Path(path)
    loaded: dict[str, str] = {}
    if not p.exists():
        return loaded
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key:
            loaded[key] = val
            os.environ.setdefault(key, val)
    return loaded


def resolve_identity(channel: str, native_id: str, tenant: str) -> tuple[str, str]:
    """把通道原生身分映射成 (tenant, user_id)。

    LINE:user_id 直接用 LINE 的 userId。tenant 目前固定傳入值(單一店家);
    日後多租戶可在此依「哪個官方帳號收到」反推 tenant。
    """
    return tenant, native_id


async def handle_text_turn(
    loop: Any, tenant: str, user_id: str, text: str, media: list[str] | None = None
) -> str:
    """跑一輪客服 turn,回傳要回給客人的文字('' = 不回)。

    media:本輪附帶的本機圖片路徑(VLN 2026-07-03)。loop/context 既有 vision 管線
    (InboundMessage.media → _build_user_content base64 image_url)自動接手;
    history 重播只留 [image: path] 文字麵包屑,不重讀檔案。
    """
    if not (text or "").strip() and not media:
        return ""
    msg = InboundMessage(
        channel="line", sender_id=user_id, chat_id=user_id,
        content=text or "", media=list(media) if media else [],
    )
    out = await loop._process_message(msg, session_key=f"{tenant}:{user_id}")
    content = (getattr(out, "content", None) or "") if out is not None else ""
    if not content.strip():
        return ""
    if _ERROR_SENTINEL in content:
        logger.warning("LLM/provider 內部錯誤,改回友善訊息(不外洩):{}", content[:160])
        return _FALLBACK_REPLY
    return content[:_LINE_TEXT_LIMIT]


async def download_line_image(blob_api: Any, message_id: str) -> str | None:
    """以 LINE Blob API 下載圖片內容 → 落地 get_media_dir("line")。回本機路徑;失敗回 None。

    LINE 圖片不在 webhook body 內,須以 message_id 二次拉取(bytes)。副檔名依
    magic bytes 判定(detect_image_mime),供 context 讀取時再驗一次 mime。
    fail-soft:任何錯誤只 log,由呼叫端回友善訊息。
    """
    try:
        from lockcore.config.paths import get_media_dir
        from lockcore.utils.helpers import detect_image_mime

        raw = await blob_api.get_message_content(message_id=message_id)
        data = bytes(raw or b"")
        if not data:
            logger.warning("LINE 圖片下載為空 message_id={}", message_id)
            return None
        mime = detect_image_mime(data) or "image/jpeg"
        ext = {
            "image/png": ".png", "image/jpeg": ".jpg",
            "image/gif": ".gif", "image/webp": ".webp",
        }.get(mime, ".jpg")
        path = get_media_dir("line") / f"{message_id}{ext}"
        path.write_bytes(data)
        return str(path)
    except Exception:  # noqa: BLE001 — 下載失敗不可炸掉 webhook
        logger.exception("LINE 圖片下載失敗 message_id={}", message_id)
        return None


def build_webapp(
    loop: Any,
    tenant: str,
    channel_secret: str,
    channel_access_token: str,
    escalation_store: Any = None,
):
    """組 aiohttp app:POST /callback 收 LINE webhook。需要 line-bot-sdk(extra: line)。

    escalation_store:傳入則 CR-0022 啟用 —— 本輪 agent 轉真人時旁路建 AI 草擬問題卡。
    """
    from aiohttp import web
    from linebot.v3 import WebhookParser
    from linebot.v3.exceptions import InvalidSignatureError
    from linebot.v3.messaging import (
        AsyncApiClient,
        AsyncMessagingApi,
        AsyncMessagingApiBlob,
        Configuration,
        PushMessageRequest,
        ReplyMessageRequest,
        TextMessage,
    )
    from linebot.v3.webhooks import (
        ImageMessageContent,
        MessageEvent,
        PostbackEvent,
        TextMessageContent,
    )

    parser = WebhookParser(channel_secret)
    config = Configuration(access_token=channel_access_token)

    async def _send_text(user_id: str, reply_token: str | None, text: str) -> None:
        """優先 reply(免額度;token 一次性、約 1 分鐘失效),失敗改 push 兜底。

        CR-0120:debounce 視窗 + turn 的總耗時可能超過 reply token 效期;
        fire 發生在 webhook 返回之後,須自建 ApiClient(callback 的已關閉)。
        """
        async with AsyncApiClient(config) as api_client:
            line_api = AsyncMessagingApi(api_client)
            if reply_token:
                try:
                    await line_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=reply_token,
                            messages=[TextMessage(text=text)],
                        )
                    )
                    return
                except Exception:  # noqa: BLE001 — reply 失敗換 push,不放棄
                    logger.warning("LINE reply 失敗,改用 push", exc_info=True)
            await line_api.push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text=text)])
            )

    async def _run_merged_turn(key: str, items: list[dict]) -> None:
        """Debounce 到期:把一批訊息合併成一輪 turn、一次回覆(CR-0120)。

        items 依到達序;文字換行合併、照片依序全帶(vision 支援多圖);
        回覆用最後一則的 reply_token(最年輕)。旁路持久化維持逐則
        (對話管理一則一泡泡、照片各自顯示),AI 回覆附掛最後一則。
        """
        user_id = key.partition(":")[2] or key
        reply_token = items[-1].get("reply_token")
        merged_text = "\n".join(
            t for t in ((i.get("text") or "") for i in items) if t.strip()
        )
        all_media = [p for i in items for p in (i.get("media") or [])]

        async def _persist_items(assistant_text: str) -> None:
            for idx, it in enumerate(items):
                text_i = (it.get("text") or "").strip() or (
                    "[照片]" if it.get("media") else ""
                )
                await _persist_turn_safe(
                    tenant, user_id, text_i,
                    assistant_text if idx == len(items) - 1 else "",
                    media_paths=it.get("media") or None,
                )

        # CR-0024:接管中 → 不跑 turn,逐則持久化 + 節流「請稍候」安撫
        # (與原逐則路徑等價,僅延遲 debounce 視窗秒數)。
        if await _handover_active_safe(tenant, user_id):
            logger.info("對話接管中,AI 暫停回覆 user={}", user_id[:8])
            notice = ""
            if _should_notify_handover(key):
                notice = _HANDOVER_WAIT_REPLY
                try:
                    await _send_text(user_id, reply_token, notice)
                except Exception:  # noqa: BLE001 — 提示送失敗不可影響持久化
                    logger.warning("接管中『請稍候』提示送出失敗(已略過)", exc_info=True)
            await _persist_items(notice)
            return

        # CR-0022:記本輪前最新 escalation id,turn 後比對是否新增(觸發轉真人)。
        esc_before = _latest_escalation_id(escalation_store, tenant, user_id)
        try:
            reply = await handle_text_turn(
                loop, tenant, user_id, merged_text, media=all_media or None
            )
        except Exception:
            logger.exception("LINE turn 失敗")
            reply = "不好意思,系統忙線中,請稍後再試,或留言由專員與您聯繫 🙏"
        if reply:
            try:
                await _send_text(user_id, reply_token, reply)
            except Exception:  # noqa: BLE001 — 回覆失敗仍要持久化,客服才看得到斷點
                logger.exception("LINE 回覆送出失敗(reply+push 皆敗)")
        # 回覆送出後再旁路(皆 fail-soft):(1) 方案 A 對話持久化 (2) CR-0097
        # 兜底:AI 承諾轉接卻沒呼叫工具 → 補 escalation (3) CR-0022 轉真人
        # → 建 AI 草擬問題卡(以合併文字為快照)。
        await _persist_items(reply)
        merged_persist = merged_text or ("[照片]" if all_media else "")
        _apply_handoff_fallback_safe(
            escalation_store, tenant, user_id, merged_persist, reply, esc_before
        )
        await _forward_escalation_safe(
            escalation_store, tenant, user_id, esc_before, merged_persist
        )

    debouncer = _TurnDebouncer(_debounce_seconds, _run_merged_turn)

    async def callback(request):
        signature = request.headers.get("X-Line-Signature", "")
        body = await request.text()
        try:
            events = parser.parse(body, signature)
        except InvalidSignatureError:
            logger.warning("LINE webhook 簽章驗證失敗,拒絕")
            return web.Response(status=400, text="invalid signature")

        async with AsyncApiClient(config) as api_client:
            line_api = AsyncMessagingApi(api_client)
            for event in events:
                # CR-0095：客戶在 LINE 點報價「同意/拒絕」（postback）→ 旁路呼 api
                # 走報價狀態機，並用 reply_token 即時回覆確認（不阻塞、fail-soft）。
                if isinstance(event, PostbackEvent):
                    pb_native = getattr(event.source, "user_id", None)
                    if pb_native:
                        _, pb_user = resolve_identity("line", pb_native, tenant)
                        pb_reply = await _route_quote_postback_safe(
                            tenant, pb_user, getattr(event.postback, "data", "") or "",
                        )
                        if pb_reply and event.reply_token:
                            await line_api.reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[TextMessage(text=pb_reply)],
                                )
                            )
                    continue
                if not isinstance(event, MessageEvent):
                    continue
                native_id = getattr(event.source, "user_id", None)
                if not native_id:
                    continue
                _, user_id = resolve_identity("line", native_id, tenant)

                # ── 訊息型別分派(VLN 2026-07-03)──────────────────────
                # 文字 → 原有流程;照片 → 下載後走 vision 管線;其他型別 → 友善話術
                # (原本 471-472 對非文字一律 continue = 已讀不回,連對話管理都看不到)。
                media_paths: list[str] = []
                if isinstance(event.message, TextMessageContent):
                    user_text = event.message.text
                elif isinstance(event.message, ImageMessageContent):
                    blob_api = AsyncMessagingApiBlob(api_client)
                    img_path = await download_line_image(blob_api, event.message.id)
                    if img_path is None:
                        if event.reply_token:
                            await line_api.reply_message(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[TextMessage(text=_IMAGE_DOWNLOAD_FAIL_REPLY)],
                                )
                            )
                        continue
                    user_text = ""  # LINE 圖片訊息無 caption;persist 用 [照片] 標記
                    media_paths = [img_path]
                else:
                    kind = getattr(event.message, "type", "") or "unknown"
                    marker = _MEDIA_KIND_MARKERS.get(kind, f"[{kind}]")
                    logger.info("LINE 非支援型別 {} user={},回友善話術", kind, user_id[:8])
                    if event.reply_token:
                        await line_api.reply_message(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=_UNSUPPORTED_MEDIA_REPLY)],
                            )
                        )
                    # 讓後台對話管理看得到「客人傳過東西」(fail-soft)
                    await _persist_turn_safe(
                        tenant, user_id, marker, _UNSUPPORTED_MEDIA_REPLY
                    )
                    continue

                # CR-0120:連續訊息合併——訊息進 per-user buffer,以最後一則
                # 起算靜默視窗(新訊息重置計時),到期才合併成一輪 turn 一次
                # 回覆。接管檢查/持久化/escalation 全在 _run_merged_turn 內。
                # 視窗 0 = 停用 → 直通單則(等同原逐則行為,測試/回退用)。
                item = {
                    "text": user_text,
                    "media": media_paths,
                    "reply_token": event.reply_token,
                }
                session_key = f"{tenant}:{user_id}"
                if _debounce_seconds() <= 0:
                    await _run_merged_turn(session_key, [item])
                else:
                    debouncer.push(session_key, item)
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_post("/callback", callback)
    return app
