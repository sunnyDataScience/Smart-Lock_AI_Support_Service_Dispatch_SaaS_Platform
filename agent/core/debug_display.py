"""執行流程可視化工具 — 路徑樹、ProblemCard、Harness 狀態。

供 main.py (CLI) 和 debounce.py (webhook) 共用。
"""


def _is_agent_step(item):
    parts = item.split(":", 1)
    return len(parts) == 2 and parts[1] in ("agent_llm", "tool_node")


def format_history_tree(history):
    seen = set()
    steps = []
    for item in history:
        if _is_agent_step(item) or item not in seen:
            steps.append(item)
            if not _is_agent_step(item):
                seen.add(item)

    blocks = []
    i = 0
    while i < len(steps):
        item = steps[i]
        if _is_agent_step(item):
            agent = item.split(":", 1)[0]
            subs = []
            while i < len(steps) and _is_agent_step(steps[i]) and steps[i].split(":", 1)[0] == agent:
                subs.append(steps[i].split(":", 1)[1])
                i += 1
            blocks.append(("agent", agent, subs))
        elif item.startswith("router:"):
            router_label = item.split(":", 1)[1]
            if not blocks or blocks[-1][0] != "router" or blocks[-1][1] != router_label:
                blocks.append(("router", router_label, None))
            i += 1
        elif item.startswith("manage_memory:"):
            blocks.append(("memory", item.split(":", 1)[1], None))
            i += 1
        elif item in ("topic_resolved", "guardrail_triggered"):
            blocks.append(("flag", item, None))
            i += 1
        else:
            blocks.append(("node", item, None))
            i += 1

    lines = []
    for idx, (btype, name, subs) in enumerate(blocks):
        is_last = idx == len(blocks) - 1
        branch = "└── " if is_last else "├── "
        indent = "    " if is_last else "│   "

        if btype == "agent":
            lines.append(f"{branch}{name}")
            for j, sub in enumerate(subs):
                sub_branch = "└── " if j == len(subs) - 1 else "├── "
                lines.append(f"{indent}{sub_branch}{sub}")
        elif btype == "router":
            lines.append(f"{branch}router → {name}")
        elif btype == "memory":
            lines.append(f"{branch}manage_memory → {name}")
        elif btype == "flag":
            lines.append(f"{branch}[FLAG] {name}")
        else:
            lines.append(f"{branch}{name}")

    return "\n".join(lines)


def show_problem_card(final: dict):
    """顯示 ProblemCard 狀態，驗證跨層資料流。"""
    pc = final.get("task", {}).get("problem_card", {})
    if not pc or not pc.get("card_id"):
        print("[ProblemCard] (未建立)")
        return

    print(f"[ProblemCard]")
    print(f"  card_id:    {pc.get('card_id')}")
    print(f"  status:     {pc.get('status')}")
    print(f"  score:      {pc.get('completeness_score', 0)}")
    print(f"  symptom:    {pc.get('symptom_summary', '')[:60]}")
    print(f"  category:   {pc.get('category', '')}")

    domain = pc.get("domain_attributes", {})
    if domain:
        filled = {k: v for k, v in domain.items() if v}
        print(f"  domain:     {filled}")

    attempts = pc.get("attempts", [])
    if attempts:
        print(f"  attempts:   {len(attempts)} 筆")
        for i, a in enumerate(attempts):
            print(f"    [{i+1}] {a.get('agent_name', '?')} / {a.get('strategy', '?')} "
                  f"→ {a.get('result', '?')} (score={a.get('quality_score', '?')})")


def show_harness_state(final: dict):
    """顯示 Harness 各層狀態，驗證 8 層框架是否真的運作。"""
    task = final.get("task", {})
    safety = final.get("safety", {})
    feedback = final.get("feedback", {})
    entropy = final.get("entropy", {})
    context_meta = final.get("context_meta", {})

    print(f"[Harness 狀態]")

    # L1 Task
    diag_status = task.get("diagnosis_status", "")
    diag_round = task.get("diagnostic_round", 0)
    symptoms = task.get("extracted_symptoms", [])
    intents = task.get("intents", [])
    if diag_status:
        print(f"  L1 Task:    status={diag_status}, round={diag_round}, "
              f"symptoms={symptoms}, intents={intents}")
    elif intents:
        print(f"  L1 Task:    not_hardware, intents={intents}")
    else:
        print(f"  L1 Task:    skip")

    # L2 Context
    if context_meta:
        budget = context_meta.get("budget_used", 0)
        remaining = context_meta.get("budget_remaining", 0)
        print(f"  L2 Context: budget={budget}/{budget+remaining}")
    else:
        print(f"  L2 Context: skip")

    # L6 Safety
    if safety:
        level = safety.get("sentiment_level", "normal")
        red = safety.get("red_code", False)
        esc = safety.get("escalation_required", False)
        risks = len(safety.get("flagged_risks", []))
        print(f"  L6 Safety:  sentiment={level}, red_code={red}, escalation={esc}, risks={risks}")
    else:
        print(f"  L6 Safety:  skip")

    # L5 Feedback
    if feedback:
        v_status = feedback.get("verification_status", "")
        scores = feedback.get("quality_scores", {})
        overall = scores.get("overall", "") if scores else ""
        print(f"  L5 Feedback: status={v_status}, overall={overall}")
    else:
        print(f"  L5 Feedback: skip")

    # L8 Entropy
    if entropy:
        novel = entropy.get("novel_resolution", False)
        sop_count = len(entropy.get("sop_candidates", []))
        print(f"  L8 Entropy: novel={novel}, sop_candidates={sop_count}")
    else:
        print(f"  L8 Entropy: skip")
