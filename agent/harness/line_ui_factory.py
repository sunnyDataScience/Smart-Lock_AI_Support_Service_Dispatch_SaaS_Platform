"""LINE Flex Message 工廠 — 偵測 AI 回覆中的 URL 並轉換為卡片。

支援：
  - Google Drive PDF → DOWNLOAD_CARD（說明書下載卡片）
  - YouTube 影片 → VIDEO_CARD（影片預覽卡片）
"""

import re

from linebot.v3.messaging import (
    FlexMessage, TextMessage,
    QuickReply, QuickReplyItem, MessageAction,
)

from core.logging_config import get_logger

log = get_logger(__name__)


# ── URL 偵測正則 ──

_GDRIVE_PATTERN = re.compile(
    r'https?://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)(?:/[^\s)]*)?'
)

_YOUTUBE_PATTERN = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})'
)

_URL_PATTERN = re.compile(r'https?://[^\s)\]]+')


# ── Quick Reply 快速回覆 ──

_quick_reply_config: dict = {}
_brand_items: list[dict] = []
_brand_models: dict[str, list[str]] = {}


def init_quick_reply(config: dict) -> None:
    """初始化 Quick Reply — 從 config 讀取品牌與型號清單。"""
    global _quick_reply_config, _brand_items, _brand_models

    _quick_reply_config = config
    _brand_items = config.get("brands", [])
    _brand_models = {
        b["text"]: b["models"]
        for b in _brand_items
        if b.get("models")
    }
    log.info("quick_reply_init", brands=[b["text"] for b in _brand_items])


def _build_quick_reply(brand: str | None = None, model: str | None = None) -> QuickReply | None:
    """依用戶 fact 狀態決定是否掛上品牌或型號快速回覆按鈕。

    - 品牌未知 → 品牌按鈕
    - 品牌已知、型號未知、且該品牌有型號專屬技能 → 型號按鈕
    """
    if not _quick_reply_config.get("enabled", False):
        return None

    # 品牌未知 → 品牌按鈕
    if not brand and _brand_items:
        items = [
            QuickReplyItem(action=MessageAction(label=b["label"], text=b["text"]))
            for b in _brand_items[:13]
        ]
        return QuickReply(items=items)

    # 品牌已知、型號未知、該品牌有特定型號 → 型號按鈕（最多 12 個 + 「其他型號」）
    if brand and not model and brand in _brand_models:
        models = _brand_models[brand][:12]
        items = [
            QuickReplyItem(action=MessageAction(label=m, text=m))
            for m in models
        ]
        items.append(
            QuickReplyItem(action=MessageAction(label="其他型號", text="其他型號，請直接回覆"))
        )
        return QuickReply(items=items)

    return None


def match_brand(text: str) -> str | None:
    """檢查文字是否完全匹配某個品牌名（不區分大小寫）。"""
    text_lower = text.strip().lower()
    for b in _brand_items:
        if text_lower == b["text"].lower():
            return b["text"]
    return None


def match_model(brand: str, text: str) -> str | None:
    """檢查文字是否完全匹配某個品牌的型號名。"""
    models = _brand_models.get(brand, [])
    text_stripped = text.strip()
    for m in models:
        if text_stripped == m:
            return m
    return None


def get_brand_models(brand: str) -> list[str]:
    """取得指定品牌的型號清單。"""
    return _brand_models.get(brand, [])


def get_all_brand_models() -> dict[str, list[str]]:
    """取得全部品牌的型號清單（dict[brand → list[model]]）。"""
    return dict(_brand_models)


def infer_brand_from_text(text: str) -> tuple[str | None, str | None]:
    """從自由文字中掃描已知型號或品牌名，反向推論品牌。

    優先匹配型號（更精確），其次匹配品牌名。

    Returns:
        (brand, model) 或 (None, None)
    """
    # 優先：型號匹配（同時得到品牌+型號）
    for brand, models in _brand_models.items():
        for m in models:
            if m in text:
                return brand, m
    # 其次：品牌名匹配（只得到品牌）
    text_lower = text.lower()
    for b in _brand_items:
        if b["text"].lower() in text_lower:
            return b["text"], None
    return None, None


def is_quick_reply_enabled() -> bool:
    """Quick Reply 是否啟用。"""
    return _quick_reply_config.get("enabled", False)


def _strip_markdown(text: str) -> str:
    """移除常見 Markdown 標記，保留換行與純文字。"""
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'(?<!\w)\*([^*]+?)\*(?!\w)', r'\1', text)
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text.strip()


def _clean_after_url_removal(text: str) -> str:
    """移除 URL 後，清理包含 URL 的那整行（如果該行移除 URL 後只剩殘留引導句）。"""
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # 跳過空行
        if not stripped:
            continue
        # 跳過只剩標點或極短殘留的行（移除 URL 後的空殼）
        no_punct = re.sub(r'[，。、：:；！？\s]', '', stripped)
        if len(no_punct) < 3:
            continue
        cleaned.append(stripped)
    return '\n'.join(cleaned)


def _build_download_bubble(title: str, url: str) -> dict:
    """建構單張下載按鈕 Bubble。"""
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "📄 官方說明書",
                    "weight": "bold",
                    "color": "#1DB446",
                    "size": "sm",
                },
                {
                    "type": "text",
                    "text": title,
                    "weight": "bold",
                    "size": "lg",
                    "margin": "md",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": "點擊下方按鈕即可開啟或下載 PDF 檔案",
                    "size": "xs",
                    "color": "#aaaaaa",
                    "wrap": True,
                    "margin": "md",
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": "📥 立即下載",
                        "uri": url,
                    },
                }
            ],
            "flex": 0,
        },
    }


def _build_video_bubble(title: str, url: str, thumbnail: str) -> dict:
    """建構單張影片預覽 Bubble。"""
    return {
        "type": "bubble",
        "hero": {
            "type": "image",
            "url": thumbnail,
            "size": "full",
            "aspectRatio": "16:9",
            "aspectMode": "cover",
            "action": {"type": "uri", "uri": url},
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": title,
                    "weight": "bold",
                    "size": "md",
                    "wrap": True,
                    "maxLines": 2,
                }
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "uri", "label": "觀看影片", "uri": url},
                    "style": "primary",
                    "color": "#FF0000",
                }
            ],
        },
    }


def _extract_context_title(text: str, url: str) -> str:
    """從 URL 前後文嘗試提取型號名稱作為標題。"""
    # 嘗試從全文提取品牌+型號模式（如 "Dormakaba DP850", "Chatlock AI-99"）
    model_match = re.search(
        r'(Dormakaba|Chatlock|Philips|Kaadas|Milre|AiLock|Chainlock)'
        r'\s*'
        r'([A-Z]{0,3}[-\s]?\d{2,4}[A-Za-z]?)',
        text, re.IGNORECASE
    )
    if model_match:
        return f"{model_match.group(1)} {model_match.group(2).strip()} 說明書"

    # fallback: 取 URL 前面那行
    idx = text.find(url)
    if idx > 0:
        before = text[:idx].rstrip()
        lines = before.split("\n")
        last_line = lines[-1].strip().rstrip("：:：，,")
        if 3 <= len(last_line) <= 30:
            return last_line
    return ""


def build_line_messages(answer: str, brand: str | None = None, model: str | None = None, skip_quick_reply: bool = False) -> list:
    """將 AI 回覆轉換為 LINE Message 物件列表。

    偵測回覆中的 URL 並自動轉換：
    - Google Drive 連結 → DOWNLOAD_CARD
    - YouTube 連結 → VIDEO_CARD
    - 其他 → 純文字

    Args:
        answer: AI 回覆文字
        brand: 當前用戶品牌（用於判斷是否掛上 Quick Reply）
        model: 當前用戶型號（用於判斷是否掛上型號 Quick Reply）

    Returns:
        LINE Message 物件列表（TextMessage + 可選的 FlexMessage）
    """
    messages = None

    # ── 偵測 Google Drive 下載連結 ──
    gdrive_matches = _GDRIVE_PATTERN.finditer(answer)
    download_bubbles = []
    seen_ids = set()

    for match in gdrive_matches:
        file_id = match.group(1)
        if file_id in seen_ids:
            continue
        seen_ids.add(file_id)

        full_url = match.group(0).rstrip(".,;!?]）」】》")
        # 確保 URL 合法：Google Drive /view 結尾或純 file ID
        if not full_url.startswith("https://"):
            full_url = "https://" + full_url.lstrip("http://")
        log.debug("ui_factory_gdrive_url", url=full_url)
        title = _extract_context_title(answer, match.group(0)) or "電子鎖說明書"
        download_bubbles.append(_build_download_bubble(title, full_url))

    if download_bubbles:
        download_bubbles = download_bubbles[:10]
        # 移除 URL + 殘留引導句 + Markdown
        clean_text = _GDRIVE_PATTERN.sub("", answer)
        clean_text = _clean_after_url_removal(clean_text)
        clean_text = _strip_markdown(clean_text)

        contents = download_bubbles[0] if len(download_bubbles) == 1 else {"type": "carousel", "contents": download_bubbles}
        flex_msg = FlexMessage.from_dict({
            "type": "flex",
            "altText": "說明書下載連結",
            "contents": contents,
        })
        log.debug("ui_factory_download_card", count=len(download_bubbles))
        messages = [flex_msg]
        if clean_text:
            messages.insert(0, TextMessage(text=clean_text))

    # ── 偵測 YouTube 連結 ──
    if messages is None:
        youtube_matches = _YOUTUBE_PATTERN.finditer(answer)
        video_bubbles = []
        seen_ids = set()

        for match in youtube_matches:
            video_id = match.group(1)
            if video_id in seen_ids:
                continue
            seen_ids.add(video_id)

            full_url = f"https://www.youtube.com/watch?v={video_id}"
            thumbnail = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            title = _extract_context_title(answer, match.group(0)) or "教學影片"
            video_bubbles.append(_build_video_bubble(title, full_url, thumbnail))

        if video_bubbles:
            video_bubbles = video_bubbles[:10]
            clean_text = _YOUTUBE_PATTERN.sub("", answer)
            clean_text = _URL_PATTERN.sub("", clean_text)
            clean_text = _clean_after_url_removal(clean_text)
            clean_text = _strip_markdown(clean_text)

            contents = video_bubbles[0] if len(video_bubbles) == 1 else {"type": "carousel", "contents": video_bubbles}
            flex_msg = FlexMessage.from_dict({
                "type": "flex",
                "altText": "教學影片推薦",
                "contents": contents,
            })
            log.debug("ui_factory_video_card", count=len(video_bubbles))
            messages = [flex_msg]
            if clean_text:
                messages.insert(0, TextMessage(text=clean_text))

    # ── 純文字 ──
    if messages is None:
        log.debug("ui_factory_text_only")
        messages = [TextMessage(text=_strip_markdown(answer))]

    # ── 掛上 Quick Reply（品牌/型號追問） ──
    if not skip_quick_reply:
        quick_reply = _build_quick_reply(brand=brand, model=model)
        if quick_reply and messages:
            messages[-1].quick_reply = quick_reply

    return messages
