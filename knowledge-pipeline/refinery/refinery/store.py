"""Draft Queue 存取層 — knowledge_drafts 表(migration 094/CR-0139 D2)。

冪等:UNIQUE(tenant_id, draft_key) ON CONFLICT DO NOTHING → 重跑不重複。
re_refine 重煉:寫入新 draft 前把該卡的 re_refine 舊 draft 標 superseded
(append-only 精神——不刪列,留完整審核軌跡)。
"""

import json

import psycopg


def supersede_rerefine(conn: psycopg.Connection, tenant: str, card_id: str) -> int:
    """該卡被審核者退回重煉的舊 draft → superseded。回異動列數。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE knowledge_drafts
            SET status = 'superseded', updated_at = now()
            WHERE tenant_id = %s AND source_problem_card_id = %s::uuid
              AND status = 're_refine'
            """,
            (tenant, card_id),
        )
        return cur.rowcount


def insert_drafts(conn: psycopg.Connection, tenant: str, drafts: list[dict]) -> int:
    """冪等寫入,回實際新增筆數。"""
    written = 0
    with conn.cursor() as cur:
        for d in drafts:
            cur.execute(
                """
                INSERT INTO knowledge_drafts
                    (tenant_id, draft_key, draft_type,
                     source_problem_card_id, source_conversation_id,
                     brand, model, category, title,
                     payload, provenance, confidence)
                VALUES (%s, %s, %s, %s::uuid, %s::uuid, %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s)
                ON CONFLICT (tenant_id, draft_key) DO NOTHING
                """,
                (
                    tenant, d["draft_key"], d["draft_type"],
                    d["source_problem_card_id"], d.get("source_conversation_id"),
                    d.get("brand"), d.get("model"), d.get("category"), d["title"],
                    json.dumps(d["payload"], ensure_ascii=False),
                    json.dumps(d["provenance"], ensure_ascii=False),
                    d.get("confidence"),
                ),
            )
            written += cur.rowcount
    conn.commit()
    return written


def queue_counts(conn: psycopg.Connection, tenant: str) -> dict[str, int]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status, count(*) FROM knowledge_drafts WHERE tenant_id = %s GROUP BY status",
            (tenant,),
        )
        return {status: n for status, n in cur.fetchall()}
