"""組裝要注入 agent prompt 的用戶背景區塊。

純函式：讀記憶體中的 product_info cache + user facts dict → 純文字輸出。
不打 LLM、不寫 DB。caller 自行決定塞進 system message 或 prepend user message。

從 agent_v2/profiles/context.py 移植（catalog 動態注入機制）。
"""

from __future__ import annotations


# `_brand`、`_common/*` 排前面（通用），`{Brand}/{Model}` 排後面（具體）
def format_catalog_section(facts: dict[str, str]) -> str:
    """組「可載入產品資料」清單，附上 status header。

    從 product_info 記憶體 cache 即時讀，動態反映 DB 變動。
    LLM 看到清單就知道該對哪個 mega-doc 下 load_product_info()。

    Args:
        facts: user facts dict（至少含 device_brand / device_model 兩 key 可選）

    Returns:
        多行文字區塊，或當 product_info cache 為空時回傳空字串。
    """
    # late import 避免 circular（profiles 與 product_info 都被 run_agent import）
    from product_info import all_docs

    docs = sorted(all_docs(), key=lambda d: (d.brand != "_common", d.brand, d.model or ""))
    if not docs:
        return ""

    brand = facts.get("device_brand", "").strip()
    model = facts.get("device_model", "").strip()
    if brand and model:
        header_status = f"已記錄：{brand} {model}"
    elif brand:
        header_status = f"已記錄：{brand}（型號未知）"
    else:
        header_status = "尚未記錄客戶品牌型號"

    lines = [
        "[可用產品資料]",
        f"（{header_status}）",
        "（請依客戶實際品牌型號選擇 mega-doc 載入；不要載錯品牌的文件）",
    ]
    for d in docs:
        lines.append(f"- {d.name}: {d.description}")
    return "\n".join(lines)
