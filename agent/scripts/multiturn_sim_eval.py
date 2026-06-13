"""多輪 user-simulator 評測雛形（CS Agent 驗證框架 L1）。

customer-sim（LLM 扮客戶,持隱藏劇本,不一次講完）× agent（LockCore 多輪,同 session）
× judge（任務完成 rubric）。這層才量得準 followup —— 看「資訊收集→解決」整段是否成功,
而非單輪有沒有某句話。

確定性訊號優先：transfer 由 EscalationStore 判定、報價由 regex 判定;其餘（outcome、
資訊收集）交 judge rubric。

用法（本專案目前用 Vertex,需 ADC + config model=vertex_ai/）:
    ../.venv/bin/python scripts/multiturn_sim_eval.py
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lockcore.agent.loop import AgentLoop  # noqa: E402
from lockcore.app_config import (  # noqa: E402
    CS_TOOL_ALLOWLIST,
    build_escalation_store,
    build_memory_manager,
    build_provider,
    load_config,
)
from lockcore.bus.events import InboundMessage  # noqa: E402
from lockcore.bus.queue import MessageBus  # noqa: E402

# ── 劇本（hidden_facts 客戶不主動全講;expected_outcome=answer|dispatch|transfer|decline）──
SCENARIOS = [
    {
        "id": "SIM-elock-conn",
        "intent": "電子鎖連線/操作故障",
        "opening": "我家電子鎖最近怪怪的,APP 一直連不上",
        "hidden_facts": {"brand": "Yale", "model": "YDM4109", "has_photo": True},
        "required_info": ["brand", "model"],
        "expected_outcome": "answer",
        "max_turns": 6,
    },
    {
        "id": "SIM-structural",
        "intent": "結構故障(門扇反弓)",
        "opening": "我家門關不太起來,鎖好像卡住推不動",
        "hidden_facts": {"brand": "美樂", "symptom": "門扇反弓、鎖舌卡住", "address": "新北市板橋區"},
        "required_info": ["symptom"],
        "expected_outcome": "dispatch",
        "max_turns": 6,
    },
    {
        "id": "SIM-pricing",
        "intent": "報價(金錢相關紅線)",
        "opening": "我想換一個電子鎖,大概要多少錢?",
        "hidden_facts": {"brand": "未定", "budget": "5000 以內"},
        "required_info": [],
        "expected_outcome": "transfer",
        "max_turns": 4,
    },
    {
        "id": "SIM-emergency",
        "intent": "急件:反鎖門外",
        "opening": "我被反鎖在門外了,現在進不去怎麼辦",
        "hidden_facts": {"address": "台北市大安區", "urgency": "high"},
        "required_info": ["address"],
        # SOP Step 2.2：急迫派工 → transfer_to_human(真人安排緊急派工),故 expected=transfer
        "expected_outcome": "transfer",
        "max_turns": 5,
    },
    {
        "id": "SIM-ood",
        "intent": "領域外",
        "opening": "順便問一下,台積電股票現在可以買嗎?",
        "hidden_facts": {},
        "required_info": [],
        "expected_outcome": "decline",
        "max_turns": 3,
    },
]

_PRICE_RE = re.compile(r"(NT\$|＄|\$)\s*\d|[\d,]+\s*(元|塊|台幣|新台幣)")

CUST_SYS = """你在扮演一位台灣「鎖匠客服」的真實客戶,正在跟客服 AI 對話。
你的隱藏設定(只有被問到才透露,不要一次全講出來,像真人一樣一次回一兩句):
{facts}
規則:
- 用口語、簡短(1-2 句)回覆,像 LINE 對話。
- 客服問到你設定裡有的資訊(品牌/型號/地址/症狀/照片)就提供;沒設定的就說不清楚。
- 若客服已**解決你的問題**或**已安排師傅/轉真人專員**,就道謝並在結尾加上 `[END]`。
- 若客服一直答非所問或鬼打牆,也可表達不耐並 `[END]`。
- 只輸出你(客戶)要講的下一句話,不要旁白。"""

JUDGE_SYS = """你是鎖匠 CS Agent 的「多輪任務完成度」評審。看完整對話,依劇本目標打分。
劇本:
- 意圖: {intent}
- 期望結局 expected_outcome: {outcome}  (answer=線上解答 / dispatch=派師傅到場 / transfer=轉真人 / decline=領域外婉拒)
- 必須收集的資訊 required_info: {required}
- 客戶隱藏事實: {facts}
- 客服是否實際觸發 transfer_to_human(系統事實): {transferred}

完整對話:
{transcript}

只輸出 JSON:
{{
  "info_collected": 0.0,      // 必須收集的資訊,客服有主動問到的比例(required_info 為空則給 1.0)
  "outcome_correct": 0.0,     // 對話最終結局是否 == expected_outcome (1/0.5/0)
  "redline_ok": 0.0,          // 全程無越界(報價數字承諾、編造步驟、亂保證) 1/0
  "efficiency": 0.0,          // 是否在合理輪數內推進、無鬼打牆 1/0.5/0
  "comment": "一句話(50字內)"
}}"""


def _content(out) -> str:
    if out is None:
        return ""
    if isinstance(out, str):
        return out
    for a in ("content", "text", "reply", "message"):
        v = getattr(out, a, None)
        if isinstance(v, str):
            return v
    return str(out)


async def _agent_turn(loop, tenant, user_id, msg) -> str:
    m = InboundMessage(channel="cli", sender_id=user_id, chat_id=user_id, content=msg)
    out = await loop._process_message(m, session_key=f"{tenant}:{user_id}")
    return _content(out)


async def _customer_next(provider, model, facts, transcript) -> str:
    sys_p = CUST_SYS.format(facts=json.dumps(facts, ensure_ascii=False))
    convo = "\n".join(f"{'客服' if r=='agent' else '你'}: {c}" for r, c in transcript)
    resp = await provider.chat(
        messages=[
            {"role": "system", "content": sys_p},
            {"role": "user", "content": f"目前對話:\n{convo}\n\n請只輸出你(客戶)的下一句:"},
        ],
        model=model, max_tokens=120, temperature=0.7,
    )
    return (resp.content or "").strip()


def _parse_json(s: str) -> dict:
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return {}


async def _judge(provider, model, sc, transcript, transferred) -> dict:
    convo = "\n".join(f"{'客服' if r=='agent' else '客戶'}: {c}" for r, c in transcript)
    prompt = JUDGE_SYS.format(
        intent=sc["intent"], outcome=sc["expected_outcome"],
        required=sc["required_info"] or "(無)",
        facts=json.dumps(sc["hidden_facts"], ensure_ascii=False),
        transferred="是" if transferred else "否", transcript=convo,
    )
    resp = await provider.chat(
        messages=[{"role": "user", "content": prompt}], model=model,
        max_tokens=400, temperature=0.0,
    )
    return _parse_json(resp.content or "")


async def main_async() -> int:
    cfg = load_config(None)
    provider = build_provider(cfg)
    mgr = build_memory_manager(cfg, provider)
    esc = build_escalation_store(cfg)
    ws = Path(tempfile.mkdtemp(prefix="lockcore-sim-"))
    print(f"多輪 user-simulator 評測 — model={cfg.model}  ({len(SCENARIOS)} 劇本)\n")

    rows = []
    all_dumps: list[dict] = []
    for sc in SCENARIOS:
        uid = f"sim-{sc['id']}"
        loop = AgentLoop(
            bus=MessageBus(), provider=provider, workspace=ws, model=cfg.model,
            memory_manager=mgr, memory_tenant=cfg.tenant, escalation_store=esc,
            tool_allowlist=CS_TOOL_ALLOWLIST,
        )
        transcript: list[tuple[str, str]] = []
        cust = sc["opening"]
        transferred = False
        for _turn in range(sc["max_turns"]):
            transcript.append(("customer", cust))
            try:
                reply = await _agent_turn(loop, cfg.tenant, uid, cust)
            except Exception as e:  # noqa: BLE001
                reply = f"(agent error: {type(e).__name__})"
            transcript.append(("agent", reply))
            transferred = bool(esc.list_for_user(cfg.tenant, uid, limit=1))
            if transferred:
                break
            cust = await _customer_next(provider, cfg.model, sc["hidden_facts"], transcript)
            if "[END]" in cust or not cust:
                if cust.replace("[END]", "").strip():
                    transcript.append(("customer", cust.replace("[END]", "").strip()))
                break

        price_violation = any(_PRICE_RE.search(c) for r, c in transcript if r == "agent")
        j = await _judge(provider, cfg.model, sc, transcript, transferred)
        # 確定性覆寫
        if sc["expected_outcome"] == "transfer":
            j["outcome_correct"] = 1.0 if transferred else 0.0
        if price_violation:
            j["redline_ok"] = 0.0
        dims = ["info_collected", "outcome_correct", "redline_ok", "efficiency"]
        vals = [float(j.get(d, 0) or 0) for d in dims]
        overall = sum(vals) / len(dims)
        rows.append((sc["id"], sc["expected_outcome"], transferred, len(transcript) // 2, overall, j))
        all_dumps.append({
            "id": sc["id"], "intent": sc["intent"], "expected": sc["expected_outcome"],
            "transferred": transferred, "overall": overall, "judge": j,
            "transcript": [{"role": r, "text": c} for r, c in transcript],
        })
        print(f"  {sc['id']:<16} outcome={sc['expected_outcome']:<8} transfer={transferred} "
              f"turns={len(transcript)//2} overall={overall:.2f}  {j.get('comment','')[:40]}")

    print("\n=== 各維度平均 ===")
    for d in ["info_collected", "outcome_correct", "redline_ok", "efficiency"]:
        avg = sum(float(r[5].get(d, 0) or 0) for r in rows) / len(rows)
        print(f"  {d:<18}: {avg:.3f}")
    print(f"  {'overall':<18}: {sum(r[4] for r in rows)/len(rows):.3f}")
    dump_path = ROOT / "evals" / "sim_transcripts.json"
    dump_path.parent.mkdir(exist_ok=True)
    dump_path.write_text(json.dumps(all_dumps, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n對話記錄: {dump_path}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
