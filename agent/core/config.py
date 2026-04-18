"""設定載入器 — 讀取 config.toml 並提供全域常數。

Usage:
    from core.config import load_config
    cfg = load_config()
    cfg.llm["model_name"]   # "gemini-2.5-flash"
    cfg.store_info["phone"] # "02-8601-9952"
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class AppConfig:
    """所有 config.toml 區段的型別化容器。"""
    system: dict = field(default_factory=dict)
    llm: dict = field(default_factory=dict)
    line_bot: dict = field(default_factory=dict)
    memory: dict = field(default_factory=dict)
    skills: dict = field(default_factory=dict)
    prompts: dict = field(default_factory=dict)
    safety: dict = field(default_factory=dict)
    storage: dict = field(default_factory=dict)
    debounce: dict = field(default_factory=dict)
    multimodal: dict = field(default_factory=dict)
    templates: dict = field(default_factory=dict)
    user_profile: dict = field(default_factory=dict)
    output_validator: dict = field(default_factory=dict)
    quick_reply: dict = field(default_factory=dict)


def load_config(file_path: str | None = None) -> AppConfig:
    """載入 config.toml 並回傳 AppConfig。

    預設路徑：agent_skills/config.toml
    """
    if file_path is None:
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.toml",
        )

    with open(file_path, "rb") as f:
        data = tomllib.load(f)

    return AppConfig(
        system=data.get("system", {}),
        llm=data.get("llm", {}),
        line_bot=data.get("line_bot", {}),
        memory=data.get("memory", {}),
        skills=data.get("skills", {}),
        prompts=data.get("prompts", {}),
        safety=data.get("safety", {}),
        storage=data.get("storage", {}),
        debounce=data.get("debounce", {}),
        multimodal=data.get("multimodal", {}),
        templates=data.get("templates", {}),
        user_profile=data.get("user_profile", {}),
        output_validator=data.get("output_validator", {}),
        quick_reply=data.get("quick_reply", {}),
    )


def load_prompt(prompt_path: str, **kwargs) -> str:
    """讀取 .md 提示詞模板並填入變數。

    Args:
        prompt_path: 相對於 agent_skills/ 的路徑（如 "prompts/system.md"）
        **kwargs: 模板變數
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_dir, prompt_path)

    with open(full_path, "r", encoding="utf-8") as f:
        template = f.read()

    return template.format(**kwargs)


