"""安全閘門 (H6) — 攔截危險指令，保護使用者安全。

在使用者訊息進入 Agent 之前，比對 config.toml [safety] 中的
dangerous_keywords，命中時直接回傳拒絕訊息，跳過 LLM 處理。
"""

import re

_pattern: re.Pattern | None = None
_block_response: str = ""
_enabled: bool = False


def init(config: dict):
    """初始化安全閘門。由 app.py startup() 呼叫。"""
    global _pattern, _block_response, _enabled
    _enabled = config.get("enabled", True)
    keywords = config.get("dangerous_keywords", [])
    if keywords:
        _pattern = re.compile("|".join(re.escape(k) for k in keywords))
    _block_response = config.get(
        "block_response",
        "為了您的安全，我無法提供這類操作指導。如需協助，請聯繫專業技術人員。",
    )
    kw_count = len(keywords) if keywords else 0
    print(f"[*] 初始化安全閘門: enabled={_enabled}, keywords={kw_count}")


def check(text: str) -> str | None:
    """檢查文字是否包含危險關鍵字。

    Returns:
        命中 → 拒絕訊息字串；安全 → None
    """
    if not _enabled or not _pattern:
        return None
    match = _pattern.search(text)
    if match:
        print(f"  [Safety Gate] 攔截危險關鍵字: {match.group()}")
        return _block_response
    return None
