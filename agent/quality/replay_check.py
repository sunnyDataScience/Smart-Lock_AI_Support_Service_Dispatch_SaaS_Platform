"""對話重放壓測 — 模擬 LINE 生產情境多輪對話跑 agent。

跟 quality_check 不同：
- quality_check：單輪 / 雙輪 fresh thread、檢核答案內容
- replay_check：多輪同 thread、檢核**對話流程行為**（重複詢問／純追問／過早派工）

⚠️ 狀態：從 agent_v2/quality/replay_check.py 移植過來的引擎，imports 仍指向 v2 模組
（build_agent / agent_tools._context / harness.checkpoint_cleanup 等）。本檔
保留偵測規則 + 重放編排邏輯供階段 1 Turn Cycle 整合後重新接上 dev 的 agent。
直接執行會 ImportError；需等 dev 的 agent core 重構完才能跑。

用法（重新接上後）：
    # 1. 先抽重放案例
    python chat_log_pipeline/scripts/build_replay_tests.py --sample 30 --min-turns 8

    # 2. 跑重放壓測（每場跑 user turns 個 round）
    python -m quality.replay_check                # 全部
    python -m quality.replay_check --limit 5      # 只跑前 5 場
    python -m quality.replay_check --max-turns 6  # 每場最多跑 6 輪 user turns

輸出：
- quality/replay_report.json（每場每輪的 AI 回覆 + 偵測到的問題）
- quality/replay_report.html（互動式查看每場對話）

偵測項目：
- repeated_question: AI 兩輪內問了相同／相似的問題
- pure_followup: AI 只追問沒給答案（句末 ? 且無實質內容）
- premature_transfer: 第 1-2 輪就直接 transfer_to_human 沒先試答
- topic_mismatch: AI 回覆與用戶上輪訊息語意明顯不相關（弱規則：keyword 重疊度）
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from dotenv import load_dotenv


_AGENT_V2_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _AGENT_V2_DIR.parent
load_dotenv(_PROJECT_ROOT / ".env")
sys.path.insert(0, str(_AGENT_V2_DIR))

from langgraph.checkpoint.memory import InMemorySaver

import product_info as pi
from agent import build_agent
from agent_tools._context import set_request_context
from core import db_pool
from core.config import load_config
from core.vertex_credentials import ensure_vertex_credentials
from harness import memory_manager
from harness.checkpoint_cleanup import cleanup_tool_messages
from llms import get_llm
from profiles import (
    build_user_context_block,
    extract_and_store_facts,
    get_brand_model_index,
    upsert_fact_scd2,
)


_REF_MARKER_RE = re.compile(r"\s*\[已參考(?:技能|產品資料)?:[^\]]*\][\s,，]*")


def _strip_ref_markers(text: str) -> str:
    return _REF_MARKER_RE.sub("", text).strip()


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts) if parts else str(content)
    return str(content)


def _last_ai_text(messages) -> str:
    for m in reversed(messages):
        if type(m).__name__ == "AIMessage":
            content = getattr(m, "content", "") or ""
            if content:
                return _strip_ref_markers(_extract_text(content))
    return ""


def _collected_tools(messages) -> list[str]:
    """從 ToolMessage 收集本輪用了哪些 tool（含 transfer / web_search / load_product_info）。"""
    tools: list[str] = []
    for m in messages:
        if type(m).__name__ != "ToolMessage":
            continue
        name = getattr(m, "name", "") or ""
        if name and name not in tools:
            tools.append(name)
    return tools


# ─────────────────────────────────────────────
# 偵測規則
# ─────────────────────────────────────────────

_QUESTION_KEYWORDS = ("型號", "品牌", "電話", "地址", "照片", "拍照", "材質", "尺寸", "種類", "車型", "幾號", "幾點")


def _is_question(text: str) -> bool:
    """判斷一段話是否含問句。"""
    return bool(re.search(r"[？\?]", text))


def _has_substantial_answer(text: str) -> bool:
    """判斷回覆是否有實質內容（不只追問）。

    粗略規則：
    - 移除問句後，剩下字數 > 25 → 有實質內容
    - 含「步驟 / 1. / 2. / 建議 / 可以 / 請」這類引導字眼 → 有實質內容
    """
    no_q = re.sub(r"[^。！!]*[？\?]", "", text).strip()
    if len(no_q) > 25:
        return True
    keywords = ("步驟", "建議", "可以", "請您", "請先", "麻煩", "如下", "1.", "2.", "好的")
    return any(k in text for k in keywords)


def _detect_repeated_question(prev_ai_texts: list[str], current_ai: str) -> bool:
    """偵測 AI 是否兩輪內問了相同問題（重複追問）。

    粗略：current 含問句，且問句中的關鍵詞在前 2 輪 AI 回覆中也出現過。
    """
    if not _is_question(current_ai):
        return False
    last_two = prev_ai_texts[-2:]
    for kw in _QUESTION_KEYWORDS:
        if kw in current_ai and kw in "".join(last_two):
            # 前面也問過同一類資訊
            return True
    return False


def _detect_pure_followup(text: str, user_text: str = "", turn_idx: int = -1) -> bool:
    """偵測純追問（句末 ? 且無實質內容）。

    例外（第 0 輪打招呼模式）：客戶剛自介／打招呼但未提需求時，
    AI 反問「請問需要什麼協助」是正常行為，不算 pure_followup。
    """
    if not _is_question(text):
        return False
    if _has_substantial_answer(text):
        return False
    # Turn 0 用戶只是自介／打招呼（沒明顯需求關鍵字）→ AI 反問合法
    if turn_idx == 0 and user_text:
        need_keywords = ("壞", "鎖", "印章", "鑰匙", "開鎖", "安裝", "故障", "維修", "卡", "怎麼", "請問", "想刻", "可以", "能不能")
        if not any(k in user_text for k in need_keywords):
            return False
    return True


def _detect_premature_transfer(turn_idx: int, tools_this_turn: list[str], tools_so_far: list[str]) -> bool:
    """第 1-2 輪就 transfer_to_human、且過往**和當輪**都沒 load 過 product_info。

    若 AI 當輪同時 load + transfer（先答再轉），算合法動作，不視為過早轉接。
    """
    if turn_idx >= 2:
        return False
    if "transfer_to_human" not in tools_this_turn:
        return False
    # 過往或當輪有載入過 product_info → 已先試圖回答，不算 premature
    if "load_product_info" in tools_so_far:
        return False
    if "load_product_info" in tools_this_turn:
        return False
    return True


def _detect_topic_mismatch(user_text: str, ai_text: str) -> bool:
    """弱規則：AI 回覆與 user 訊息 keyword 重疊度太低 → 文不對題。

    收緊條件以降低誤報：
    - 只在 user 訊息較長（>=30 字）時生效
    - AI 回覆也要夠短（<80 字才檢查；長答覆 bigram 重疊本就低）
    - 中文 bigram 重疊 < 1 才視為偏離
    """
    if len(user_text) < 30:
        return False
    if len(ai_text) >= 80:
        return False
    def bigrams(text: str) -> set[str]:
        text = re.sub(r"[\W\s]+", "", text)
        return {text[i:i+2] for i in range(len(text)-1)}
    user_bg = bigrams(user_text)
    ai_bg = bigrams(ai_text)
    if not user_bg or not ai_bg:
        return False
    overlap = len(user_bg & ai_bg)
    return overlap < 1


# ─────────────────────────────────────────────
# 重放執行
# ─────────────────────────────────────────────

@dataclass
class TurnResult:
    turn_idx: int
    user_text: str
    real_service_text: str
    ai_text: str
    tools: list[str]
    elapsed_sec: float
    issues: list[str]


async def replay_one_case(
    case: dict,
    *,
    agent,
    pool,
    index,
    max_turns: int = 0,
) -> dict:
    """重放一場對話。

    Args:
        case: {"id", "turns": [{"role": "user|service", "content"}, ...]}
        max_turns: 最多跑 N 個 user turns（0 = 全跑）

    Returns:
        {"id", "turn_results": [...], "summary": {...}}
    """
    case_id = case["id"]
    user_id = f"replay-{case_id}"
    thread_id = f"replay-thread-{case_id}"

    turn_results: list[TurnResult] = []
    prev_ai_texts: list[str] = []
    tools_so_far: list[str] = []
    user_turn_idx = 0

    turns = case["turns"]
    i = 0
    while i < len(turns):
        if turns[i]["role"] != "user":
            i += 1
            continue

        # 找對應的 service turn（下一個非 user 的 turn）
        user_text = turns[i]["content"]
        real_service_text = ""
        for j in range(i + 1, len(turns)):
            if turns[j]["role"] == "service":
                real_service_text = turns[j]["content"]
                break
            elif turns[j]["role"] == "user":
                # 連續 user turn — 不正常，但繼續
                break

        if max_turns and user_turn_idx >= max_turns:
            break

        t0 = time.time()
        # 跑 agent（同 thread_id 維持多輪 context）
        try:
            extract_result = await extract_and_store_facts(user_id, user_text, pool, index)
        except Exception:
            extract_result = {"mismatch_warning": None}

        mismatch = extract_result.get("mismatch_warning") if isinstance(extract_result, dict) else None
        supported_brands = list(index.brands) if index and getattr(index, "brands", None) else None
        context_block = await build_user_context_block(
            user_id, pool,
            mismatch_warning=mismatch,
            supported_brands=supported_brands,
        )
        set_request_context(user_id, user_text)

        config = {"configurable": {"thread_id": thread_id}}
        summary = memory_manager.get_summary(thread_id)
        summary_prefix = memory_manager.build_summary_prefix(summary) if summary else ""

        message_content = summary_prefix
        if context_block:
            message_content += f"{context_block}\n\n"
        message_content += user_text

        try:
            result = await asyncio.wait_for(
                agent.ainvoke(
                    {"messages": [{"role": "user", "content": message_content}]},
                    config,
                ),
                timeout=120.0,
            )
            messages = result.get("messages", [])
            ai_text = _last_ai_text(messages) or "(no reply)"
            tools_this_turn = _collected_tools(messages)

            try:
                await cleanup_tool_messages(agent, config, messages)
            except Exception:
                pass
        except Exception as e:
            ai_text = f"[AGENT ERROR] {type(e).__name__}: {e}"
            tools_this_turn = []

        elapsed = round(time.time() - t0, 1)

        # 偵測問題
        issues: list[str] = []
        if _detect_repeated_question(prev_ai_texts, ai_text):
            issues.append("repeated_question")
        if _detect_pure_followup(ai_text, user_text=user_text, turn_idx=user_turn_idx):
            issues.append("pure_followup")
        if _detect_premature_transfer(user_turn_idx, tools_this_turn, tools_so_far):
            issues.append("premature_transfer")
        if _detect_topic_mismatch(user_text, ai_text):
            issues.append("topic_mismatch")

        turn_results.append(TurnResult(
            turn_idx=user_turn_idx,
            user_text=user_text,
            real_service_text=real_service_text,
            ai_text=ai_text,
            tools=tools_this_turn,
            elapsed_sec=elapsed,
            issues=issues,
        ))

        prev_ai_texts.append(ai_text)
        tools_so_far.extend(t for t in tools_this_turn if t not in tools_so_far)
        user_turn_idx += 1

        # 跳過已對應的 service turn 與後續同 user 連續訊息
        i += 1
        while i < len(turns) and turns[i]["role"] == "service":
            i += 1

    # 統計
    issue_counter: dict[str, int] = {}
    for tr in turn_results:
        for iss in tr.issues:
            issue_counter[iss] = issue_counter.get(iss, 0) + 1
    total_issues = sum(issue_counter.values())

    if total_issues == 0:
        verdict = "clean"
    elif total_issues <= 2:
        verdict = "minor_issues"
    else:
        verdict = "major_issues"

    return {
        "id": case_id,
        "source": case.get("source", ""),
        "turn_count_replayed": len(turn_results),
        "turn_results": [asdict(tr) for tr in turn_results],
        "issue_counter": issue_counter,
        "total_issues": total_issues,
        "verdict": verdict,
    }


# ─────────────────────────────────────────────
# 清理測試殘留
# ─────────────────────────────────────────────

async def _cleanup_test_facts(pool) -> int:
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM user_facts WHERE user_id LIKE 'replay-%'")
            return cur.rowcount


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(description="agent_v2 對話重放壓測")
    p.add_argument("--limit", type=int, default=0, help="只跑前 N 場（0=全跑）")
    p.add_argument("--max-turns", type=int, default=0, help="每場最多跑 N 個 user turns（0=全跑）")
    return p.parse_args()


async def main() -> None:
    args = _parse_args()
    base_dir = Path(__file__).resolve().parent
    cases_path = base_dir / "replay_cases.json"
    json_path = base_dir / "replay_report.json"
    html_path = base_dir / "replay_report.html"

    if not cases_path.is_file():
        print(f"  ERROR: {cases_path} not found.")
        print(f"  請先跑：python chat_log_pipeline/scripts/build_replay_tests.py --sample 30")
        return

    ensure_vertex_credentials()
    os.chdir(_AGENT_V2_DIR)
    cfg = load_config()

    pool = await db_pool.get_pool()
    print("[*] DB pool ready")
    deleted = await _cleanup_test_facts(pool)
    if deleted:
        print(f"[*] Cleaned {deleted} stale replay-* user_facts rows")

    docs = await pi.load_all_docs(pool)
    print(f"[*] product_info cache: {len(docs)} docs")
    index = await get_brand_model_index(pool)
    print(f"[*] Brand index: {len(index.brands)} brands, {len(index.models)} models")

    model = get_llm(cfg.llm)
    print(f"[*] LLM: {cfg.llm.get('model')}")

    checkpointer = InMemorySaver()
    agent = build_agent(model, cfg, checkpointer=checkpointer)
    memory_manager.init(model, cfg.memory)

    cases_data = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = cases_data.get("cases", [])
    if args.limit:
        cases = cases[: args.limit]

    print(f"\n========== Replay {len(cases)} 場對話 ==========")

    results: list[dict] = []
    for i, case in enumerate(cases, 1):
        case_id = case["id"]
        n_user = case.get("user_turns", 0)
        print(f"\n[{i:03d}/{len(cases)}] {case_id} ({n_user} user turns) ...")
        try:
            r = await replay_one_case(case, agent=agent, pool=pool, index=index, max_turns=args.max_turns)
        except Exception as e:
            print(f"  ! 失敗: {type(e).__name__}: {e}")
            r = {
                "id": case_id, "verdict": "error",
                "total_issues": 0, "issue_counter": {},
                "turn_results": [], "error": str(e),
            }
        results.append(r)

        ic = r.get("issue_counter", {})
        ic_str = ", ".join(f"{k}:{v}" for k, v in ic.items()) if ic else "no issues"
        print(f"     [{r.get('verdict','?')}] turns={r.get('turn_count_replayed', '?')}, {ic_str}")

        await asyncio.sleep(0.5)

    # 摘要
    verdict_counter = {"clean": 0, "minor_issues": 0, "major_issues": 0, "error": 0}
    issue_counter_total: dict[str, int] = {}
    for r in results:
        verdict_counter[r["verdict"]] = verdict_counter.get(r["verdict"], 0) + 1
        for k, v in r.get("issue_counter", {}).items():
            issue_counter_total[k] = issue_counter_total.get(k, 0) + v

    report = {
        "ran_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_cases": len(results),
        "verdict_counter": verdict_counter,
        "issue_counter_total": issue_counter_total,
        "results": results,
    }
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[*] JSON saved: {json_path}")

    _save_html(report, html_path)
    print(f"[*] HTML saved: {html_path}")

    print(f"\n========== Summary ==========")
    print(f"  Total: {len(results)}")
    print(f"  Clean: {verdict_counter['clean']}")
    print(f"  Minor issues: {verdict_counter['minor_issues']}")
    print(f"  Major issues: {verdict_counter['major_issues']}")
    print(f"  Errors: {verdict_counter['error']}")
    if issue_counter_total:
        print(f"  Issue breakdown:")
        for k, v in sorted(issue_counter_total.items(), key=lambda x: -x[1]):
            print(f"    {k}: {v}")

    await db_pool.close_pool()


def _save_html(report: dict, path: Path) -> None:
    data_json = json.dumps(report, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>agent_v2 — Replay Report</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,"Microsoft JhengHei",sans-serif;background:#0f172a;color:#e2e8f0;padding:24px}}
  h1{{font-size:1.5rem;margin-bottom:8px}}
  .sub{{color:#94a3b8;margin-bottom:24px;font-size:.85rem}}
  .cards{{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
  .card{{background:#1e293b;border-radius:10px;padding:16px 24px;min-width:120px;text-align:center}}
  .card .n{{font-size:2rem;font-weight:700}}
  .card .l{{font-size:.75rem;color:#94a3b8;margin-top:2px}}
  .card.clean .n{{color:#4ade80}}.card.minor .n{{color:#fbbf24}}.card.major .n{{color:#f87171}}.card.error .n{{color:#a78bfa}}.card.total .n{{color:#38bdf8}}
  .sec{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:24px}}
  .sec h2{{font-size:1rem;margin-bottom:14px}}
  .case{{background:#15203a;border-radius:8px;padding:14px;margin-bottom:14px}}
  .case h3{{font-size:.95rem;margin-bottom:8px}}
  .turn{{margin-bottom:10px;padding:8px;background:#1e293b;border-radius:6px;border-left:3px solid #334155}}
  .turn.has-issue{{border-left-color:#f87171}}
  .role{{font-size:.7rem;color:#94a3b8;margin-bottom:4px}}
  .text{{white-space:pre-wrap;word-break:break-word}}
  .user{{color:#fbbf24}}.real{{color:#94a3b8}}.ai{{color:#4ade80}}
  .issue{{display:inline-block;background:#7f1d1d;color:#f87171;padding:2px 8px;border-radius:4px;font-size:.7rem;margin:2px}}
  .tool{{display:inline-block;background:#1e3a8a;color:#93c5fd;padding:1px 6px;border-radius:3px;font-size:.7rem;margin:1px}}
</style>
</head>
<body>
<h1>agent_v2 — Replay Stress Test</h1>
<p class="sub" id="sub"></p>
<div class="cards" id="cards"></div>
<div class="sec"><h2>Issue Breakdown</h2><div id="issues"></div></div>
<div class="sec"><h2>Cases</h2><div id="cases"></div></div>
<script>
const D={data_json};
const verd=D.verdict_counter||{{}};
const tot=D.total_cases||0;
document.getElementById('sub').textContent=tot+' cases | clean: '+(verd.clean||0)+' / minor: '+(verd.minor_issues||0)+' / major: '+(verd.major_issues||0);
document.getElementById('cards').innerHTML=[
['total',tot,'Total'],['clean',verd.clean||0,'Clean'],['minor',verd.minor_issues||0,'Minor'],['major',verd.major_issues||0,'Major'],['error',verd.error||0,'Error']
].map(c=>'<div class="card '+c[0]+'"><div class="n">'+c[1]+'</div><div class="l">'+c[2]+'</div></div>').join('');
const ic=D.issue_counter_total||{{}};
document.getElementById('issues').innerHTML=Object.keys(ic).length?Object.entries(ic).map(([k,v])=>'<span class="issue">'+k+': '+v+'</span>').join(' '):'<span style="color:#94a3b8">無偵測到問題</span>';
function e(s){{const d=document.createElement('div');d.textContent=s||'';return d.innerHTML}}
document.getElementById('cases').innerHTML=(D.results||[]).map(r=>{{
  const turns=(r.turn_results||[]).map(t=>{{
    const issues=(t.issues||[]).map(i=>'<span class="issue">'+i+'</span>').join(' ');
    const tools=(t.tools||[]).map(tn=>'<span class="tool">'+tn+'</span>').join(' ');
    return '<div class="turn '+(t.issues&&t.issues.length?'has-issue':'')+'">'+
      '<div class="role">Turn '+t.turn_idx+'</div>'+
      '<div class="text user">[user] '+e(t.user_text)+'</div>'+
      '<div class="text real">[real] '+e(t.real_service_text)+'</div>'+
      '<div class="text ai">[ai] '+e(t.ai_text)+'</div>'+
      '<div>'+tools+' '+issues+'</div></div>';
  }}).join('');
  const v=r.verdict||'?';
  const ic=r.issue_counter||{{}};
  const ics=Object.entries(ic).map(([k,v])=>k+':'+v).join(', ')||'no issues';
  return '<div class="case"><h3>'+e(r.id)+' ['+v+'] · '+ics+'</h3>'+turns+'</div>';
}}).join('');
</script>
</body>
</html>"""
    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
