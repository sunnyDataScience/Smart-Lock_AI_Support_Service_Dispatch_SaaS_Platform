"""生成後 grounding guardrail（CS Agent 驗證框架 — 對抗品牌型號幻覺）。

問題（L1 揪出）：agent 會把客戶**未提供**的具體型號當作已知講出來
（如「您的 Yale YDM4109」）——純模型 confabulation,SOP 文字擋不住。

策略：偵測回覆中出現、但**客戶對話從未提到**的「具體型號代碼」(如 YDM4109、SHP-DP609)。
型號代碼是最明確的幻覺訊號(agent 不該自己生出一組型號)。偵測為**確定性**(regex),
可作為可靠的幻覺率指標,亦可掛在 loop 後做攔截/重生(整合屬 architecture change,另議)。

純函式、可攜、無相依。
"""

from __future__ import annotations

import re

# 具體型號代碼：≥2 個大寫字母 + 可選分隔 + ≥3 位數字（YDM4109 / SHP-DP609 / WV-200）。
# 排除純年份/數量等(需字母前綴),降誤判。
_MODEL_CODE = re.compile(r"\b([A-Z]{2,}[A-Z0-9]*[- ]?\d{3,}[A-Z0-9]*)\b")

# 台灣常見電子鎖品牌（中英）。品牌單獨出現(舉例用)不算幻覺,只有「客戶未提且被當其鎖」才算。
_BRANDS = [
    "Yale", "Samsung", "三星", "Gateman", "美樂", "Milre", "Philips", "飛利浦",
    "Dormakaba", "Panasonic", "國際牌", "TaiTan", "台菱", "一德", "加安", "GUARD",
]


def _codes(text: str) -> set[str]:
    return {m.group(1).upper().replace(" ", "").replace("-", "") for m in _MODEL_CODE.finditer(text or "")}


def unsourced_model_codes(reply: str, customer_text: str) -> list[str]:
    """回覆中出現、但客戶對話從未提到的具體型號代碼 → 視為幻覺。"""
    in_reply = _codes(reply)
    in_cust = _codes(customer_text)
    return sorted(in_reply - in_cust)


def unsourced_brands(reply: str, customer_text: str) -> list[str]:
    """回覆以『您的 <品牌>』口吻講出、但客戶從未提到的品牌（次要訊號）。"""
    out = []
    for b in _BRANDS:
        if b in (customer_text or ""):
            continue
        # 只抓「您的/你的 + 品牌」這種把品牌當客戶既有事實的講法
        if re.search(rf"(您的|你的|貴|手上的)\s*{re.escape(b)}", reply or ""):
            out.append(b)
    return out


def check(reply: str, customer_text: str) -> dict:
    codes = unsourced_model_codes(reply, customer_text)
    brands = unsourced_brands(reply, customer_text)
    return {"fabricated": bool(codes or brands), "model_codes": codes, "brands": brands}


# ── 對既有 sim_transcripts.json 量目前幻覺率（確定性,不花 LLM）──────────────
def _measure() -> int:
    import json
    from pathlib import Path

    p = Path(__file__).resolve().parent.parent / "evals" / "sim_transcripts.json"
    if not p.exists():
        print("找不到 evals/sim_transcripts.json,請先跑 multiturn_sim_eval.py")
        return 1
    data = json.loads(p.read_text(encoding="utf-8"))
    total_agent_turns = 0
    fab_turns = 0
    for sc in data:
        cust_text = " ".join(t["text"] for t in sc["transcript"] if t["role"] == "customer")
        # 累進的客戶上下文：判斷某 agent turn 時,客戶「在那之前」講過什麼
        seen_cust = ""
        for t in sc["transcript"]:
            if t["role"] == "customer":
                seen_cust += " " + t["text"]
                continue
            total_agent_turns += 1
            r = check(t["text"], seen_cust)
            if r["fabricated"]:
                fab_turns += 1
                print(f"  [{sc['id']}] 幻覺: codes={r['model_codes']} brands={r['brands']}")
    rate = fab_turns / total_agent_turns if total_agent_turns else 0
    print(f"\n幻覺率: {fab_turns}/{total_agent_turns} agent turns = {rate:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_measure())
