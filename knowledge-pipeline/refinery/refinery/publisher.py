"""Publisher — 核可後才落地(ADR-018 步驟④/CR-0140 D3、D5)。

事實軌 case_entry:embed(symptom) + INSERT 併形後 case_entries(095),
  source='refinery'、verified=TRUE(已過 HITL)、embedding_status='ready'。
行為軌 behavior:產 patch artifact(target_path + content 存回 draft provenance),
  實際落檔走 `python -m refinery.apply_behavior`(repo checkout 內執行,人 git commit)
  ——服務容器無 skills 檔案系統,git 寫入本質是 repo 操作(CIA D5)。
"""

import json
from datetime import datetime, timezone
from typing import Callable

import psycopg

# 行為軌落檔目標(append-only 新檔;product-knowledge references 鎖定不受影響)
BEHAVIOR_TARGET_DIR = "agent/lockcore/skills/locksmith-cs-sop/references/refined"


def publish_case_entry(
    conn: psycopg.Connection,
    tenant: str,
    draft: dict,
    *,
    reviewer_id: str,
    embed_fn: Callable[[str], list[float]],
    embed_model_name: str,
) -> str:
    """draft(case_entry 軌)→ case_entries 一列;回 case_entry id。不 commit(由呼叫端交易)。"""
    payload = draft["payload"]
    symptom = payload["symptom"]
    vec = embed_fn(symptom)
    vec_literal = "[" + ",".join(f"{v:.7g}" for v in vec) + "]"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO case_entries
                (tenant_id, title, problem_description, solution, brand, model,
                 source, approved_by, verified, is_active,
                 embedding, embedding_model, embedding_status, source_problem_card_id)
            VALUES (%s, %s, %s, %s, %s, %s,
                    'refinery', %s::uuid, TRUE, TRUE,
                    %s::vector, %s, 'ready', %s::uuid)
            RETURNING id
            """,
            (
                tenant, draft["title"], symptom, payload["resolution"],
                draft.get("brand"), draft.get("model"),
                reviewer_id, vec_literal, embed_model_name,
                draft.get("source_problem_card_id"),
            ),
        )
        return str(cur.fetchone()[0])


def behavior_patch_artifact(draft: dict) -> dict:
    """行為軌核可 → patch artifact(存回 provenance,apply CLI 消費)。"""
    payload = draft["payload"]
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    target_path = f"{BEHAVIOR_TARGET_DIR}/{day}-{draft['draft_key']}.md"
    prov = draft.get("provenance") or {}
    content = (
        f"# {draft['title']}\n\n"
        f"{payload['proposal']}\n\n"
        f"---\n"
        f"- 依據:{payload.get('rationale', '')}\n"
        f"- 來源:問題卡 {prov.get('problem_card_id', '')}"
        f"(HITL 核可,knowledge-refinery draft {draft['draft_key']})\n"
    )
    return {"target_path": target_path, "content": content}


def record_publish_result(
    conn: psycopg.Connection, tenant: str, draft_id: int, published: dict
) -> None:
    """把落地結果併入 draft provenance(audit 溯源)。不 commit。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE knowledge_drafts
            SET provenance = provenance || %s::jsonb, updated_at = now()
            WHERE tenant_id = %s AND id = %s
            """,
            (json.dumps({"published": published}, ensure_ascii=False), tenant, draft_id),
        )
