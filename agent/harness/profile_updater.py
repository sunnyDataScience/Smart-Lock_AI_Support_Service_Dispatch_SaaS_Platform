"""用戶輪廓自動萃取模組 — 每次對話後用 LLM 萃取個資並更新。

由 debounce.agent_and_reply() 在取得 AI 回覆後呼叫。
不影響回覆速度（背景非阻塞執行）。

hard_facts → PostgreSQL user_facts（SCD Type 2）
soft_profile → 制式化 MD 檔案（data/profiles/）
"""

from __future__ import annotations

import json
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage

from core.config import load_prompt
from harness.llm_metrics import log_simple

# 模組層級狀態（由 init() 初始化）
_llm = None
_config: dict = {}
_profile_mgr = None

# ── 軟輪廓欄位定義 ──

_ALLOWED_UNLOCK_METHODS = {"指紋", "密碼", "卡片", "人臉", "APP", "鑰匙", "掌靜脈"}
_ALLOWED_LIVING_ENV = {"大樓", "透天", "公寓", "套房"}
_ALLOWED_DOOR_TYPE = {"推拉式", "下壓式"}

_SOFT_FIELD_LABELS = {
    "door_type": "門鎖類型",
    "install_date": "安裝日期",
    "unlock_methods": "解鎖方式",
    "living_env": "居住環境",
    "communication_note": "備註",
}

_SOFT_DEFAULTS = {
    "door_type": "未知",
    "install_date": "未知",
    "unlock_methods": "未知",
    "living_env": "未知",
    "communication_note": "無",
}

_SECTION_MAP = {
    "設備環境": ["door_type", "install_date", "unlock_methods", "living_env"],
    "溝通偏好": ["communication_note"],
}


def init(llm, config: dict, profile_mgr):
    """注入依賴，由 app.py startup 呼叫。"""
    global _llm, _config, _profile_mgr
    _llm = llm
    _config = config
    _profile_mgr = profile_mgr


# ── 軟輪廓 MD 解析 / 渲染 / 合併 ──

def _parse_soft_profile(md_text: str) -> dict:
    """從現有 MD 解析出各欄位值。"""
    fields = dict(_SOFT_DEFAULTS)
    if not md_text:
        return fields

    for line in md_text.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        line = line[2:]  # 去掉 "- "
        for key, label in _SOFT_FIELD_LABELS.items():
            prefix = f"{label}："
            if line.startswith(prefix):
                val = line[len(prefix):].strip()
                if val:
                    fields[key] = val
                break

    return fields


def _render_soft_profile(fields: dict) -> str:
    """用模板渲染完整 MD。"""
    lines = []
    for section_name, section_keys in _SECTION_MAP.items():
        lines.append(f"## {section_name}")
        for key in section_keys:
            label = _SOFT_FIELD_LABELS[key]
            val = fields.get(key, _SOFT_DEFAULTS[key])
            lines.append(f"- {label}：{val}")
        lines.append("")  # section 間空行

    return "\n".join(lines).rstrip() + "\n"


def _merge_soft_profile(existing: dict, new_facts: dict) -> dict:
    """合併：新值覆蓋舊值，null 保留舊值。"""
    merged = dict(existing)
    for key, val in new_facts.items():
        if key not in _SOFT_FIELD_LABELS:
            continue
        if val is None:
            continue
        val = str(val).strip()
        if not val:
            continue
        merged[key] = val
    return merged


def _validate_soft_facts(facts: dict) -> dict:
    """驗證並清洗軟輪廓欄位值。"""
    cleaned = {}
    for key, val in facts.items():
        if val is None or not str(val).strip():
            continue
        val = str(val).strip()

        if key == "door_type":
            if val not in _ALLOWED_DOOR_TYPE:
                continue
        elif key == "living_env":
            if val not in _ALLOWED_LIVING_ENV:
                continue
        elif key == "unlock_methods":
            methods = [m.strip() for m in val.split(",")]
            methods = [m for m in methods if m in _ALLOWED_UNLOCK_METHODS]
            if not methods:
                continue
            val = ", ".join(methods)
        elif key == "install_date":
            # 驗證 YYYY-MM 格式
            if not re.match(r"^\d{4}-\d{2}$", val):
                continue
        elif key == "communication_note":
            val = val[:15]

        cleaned[key] = val
    return cleaned


# ── 主流程 ──

async def extract_and_update(user_id: str, question: str, answer: str):
    """從對話中萃取個資並更新 user profile。"""
    if not _llm or not _profile_mgr:
        return
    if not _profile_mgr.enabled and not _profile_mgr.facts_enabled:
        return

    try:
        # 軟輪廓 init/load（僅在 enabled=true 時）
        if _profile_mgr.enabled:
            existing_md = await _profile_mgr.load_profile(user_id)
            if not existing_md:
                default_md = _render_soft_profile(_SOFT_DEFAULTS)
                await _profile_mgr.save_profile(user_id, default_md)
            existing_profile = await _profile_mgr.load_full_profile(user_id)
        else:
            existing_profile = "(empty - new user)"

        domain = _config.get("domain", "電子鎖、智慧門鎖")
        fact_attrs = ", ".join(_config.get("fact_attributes", ["phone", "address", "device_model", "device_brand"]))

        prompt_path = _config.get("update_profile_prompt", "prompts/update_profile.md")
        prompt = load_prompt(
            prompt_path,
            domain=domain,
            existing_profile=existing_profile if existing_profile else "(empty - new user)",
            question=question,
            answer=answer,
            fact_attributes=fact_attrs,
        )

        model_name = _config.get("model_name") or _config.get("extractor_model") or "unknown"
        t0 = time.monotonic()
        try:
            response = await _llm.ainvoke([
                SystemMessage(content=prompt),
                HumanMessage(content=f"使用者: {question}\n客服: {answer}"),
            ])
            log_simple(
                user_id=user_id,
                call_site="profile_extraction",
                model=model_name,
                response=response,
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
        except Exception as e:
            log_simple(
                user_id=user_id,
                call_site="profile_extraction",
                model=model_name,
                latency_ms=int((time.monotonic() - t0) * 1000),
                success=False,
                error_type=type(e).__name__,
            )
            raise
        raw_text = response.content.strip()

        # 清除 code fence
        cleaned = re.sub(r'^```(?:json)?\s*', '', raw_text)
        cleaned = re.sub(r'\s*```$', '', cleaned)

        try:
            parsed = json.loads(cleaned)

            # 寫入 hard_facts（PostgreSQL SCD Type 2）
            # device_brand / device_model 由 update_user_info 工具專責更新，不在此處寫入
            if _profile_mgr.facts_enabled:
                _SKIP_HARD_FACTS = {"device_brand", "device_model"}
                hard_facts = parsed.get("hard_facts", {})
                if hard_facts and isinstance(hard_facts, dict):
                    for key, val in hard_facts.items():
                        if key in _SKIP_HARD_FACTS:
                            continue
                        if val is not None and str(val).strip():
                            await _profile_mgr.update_fact(user_id, key, str(val).strip())
                            print(f"  [Profile] fact 寫入: {key}={val}")

            # 寫入 soft_profile（制式化 MD 檔案）
            if _profile_mgr.enabled:
                soft_profile = parsed.get("soft_profile", {})
                if soft_profile and isinstance(soft_profile, dict):
                    validated = _validate_soft_facts(soft_profile)
                    if validated:
                        existing_md = await _profile_mgr.load_profile(user_id)
                        existing_fields = _parse_soft_profile(existing_md)
                        merged = _merge_soft_profile(existing_fields, validated)
                        rendered = _render_soft_profile(merged)
                        await _profile_mgr.save_profile(user_id, rendered)
                        print(f"  [Profile] 已更新 {user_id} 的軟輪廓: {list(validated.keys())}")

        except json.JSONDecodeError:
            print("  [Profile] JSON 解析失敗，跳過")

    except Exception as e:
        print(f"  [Profile] 更新輪廓失敗: {e}")
