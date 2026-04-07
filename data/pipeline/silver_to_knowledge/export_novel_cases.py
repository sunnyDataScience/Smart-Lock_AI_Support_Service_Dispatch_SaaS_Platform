"""匯出新案例 ProblemCards 至 silver 格式。

從 PostgreSQL problem_cards 表撈取 is_novel=true 且已結案的 ProblemCard，
轉為 silver JSON 格式輸出到 data/storage/silver/problem_cards/，
讓 enrich_fault_trees.py / generate_fault_trees.py 可以消費這些真實案例。

用法：
    cd data
    python pipeline/silver_to_knowledge/export_novel_cases.py --verbose
    python pipeline/silver_to_knowledge/export_novel_cases.py --since 2026-04-01 --limit 50
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from pipeline.silver_to_knowledge._loaders import SILVER_DIR

OUTPUT_DIR = SILVER_DIR / "problem_cards"


def get_db_connection():
    """建立同步 PostgreSQL 連線。"""
    uri = os.getenv("POSTGRES_URI")
    if not uri:
        print("[export] 缺少 POSTGRES_URI 環境變數")
        return None
    try:
        from psycopg import Connection
        return Connection.connect(uri)
    except Exception as e:
        print(f"[export] 資料庫連線失敗: {e}")
        return None


def check_table_exists(conn) -> bool:
    """檢查 problem_cards 表是否存在。"""
    cursor = conn.execute(
        "SELECT EXISTS ("
        "  SELECT FROM information_schema.tables "
        "  WHERE table_name = 'problem_cards'"
        ")"
    )
    row = cursor.fetchone()
    return bool(row and row[0])


def fetch_novel_cards(conn, limit: int, since: str) -> list[dict]:
    """撈取 is_novel=true 且已結案的 ProblemCard。"""
    query = (
        "SELECT card_id, status, symptom_summary, category, "
        "completeness_score, domain_attributes, diagnosis_status, "
        "diagnostic_round, confidence_score, attempts, "
        "resolution_summary, is_novel, sop_generated, created_at "
        "FROM problem_cards "
        "WHERE is_novel = true "
        "AND status IN ('resolved', 'escalated') "
    )
    params: list = []

    if since:
        query += "AND created_at >= %s "
        params.append(since)

    query += "ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    cursor = conn.execute(query, params)
    columns = [
        "card_id", "status", "symptom_summary", "category",
        "completeness_score", "domain_attributes", "diagnosis_status",
        "diagnostic_round", "confidence_score", "attempts",
        "resolution_summary", "is_novel", "sop_generated", "created_at",
    ]
    rows = cursor.fetchall()
    return [dict(zip(columns, row)) for row in rows]


def card_to_silver_doc(card: dict) -> dict:
    """將 ProblemCard 轉為 silver 文件格式。"""
    domain = card.get("domain_attributes") or {}
    if isinstance(domain, str):
        domain = json.loads(domain)

    # 組裝 page_content：故障摘要 + 診斷過程 + 解決方案
    parts = []
    if card.get("symptom_summary"):
        parts.append(f"故障摘要：{card['symptom_summary']}")
    if card.get("category"):
        parts.append(f"故障分類：{card['category']}")
    if card.get("diagnosis_status"):
        parts.append(f"診斷狀態：{card['diagnosis_status']}")
    if card.get("diagnostic_round"):
        parts.append(f"診斷輪次：{card['diagnostic_round']}")
    if card.get("confidence_score"):
        parts.append(f"信心分數：{card['confidence_score']:.2f}")
    if card.get("resolution_summary"):
        parts.append(f"解決方案：{card['resolution_summary']}")

    # 解析 attempts 中的驗證問答（對 fault tree enrichment 有價值）
    attempts = card.get("attempts") or []
    if isinstance(attempts, str):
        attempts = json.loads(attempts)
    for i, att in enumerate(attempts, 1):
        if isinstance(att, dict):
            snippet = att.get("answer_snippet", "")
            strategy = att.get("strategy", "")
            if snippet:
                parts.append(f"診斷嘗試 {i}（{strategy}）：{snippet}")

    return {
        "page_content": "\n".join(parts),
        "metadata": {
            "brand": domain.get("device_brand", ""),
            "model": domain.get("device_model", ""),
            "category": "troubleshoot",
            "source_type": "problem_card",
            "card_id": card.get("card_id", ""),
            "status": card.get("status", ""),
            "is_novel": True,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="匯出新案例 ProblemCards 至 silver 格式")
    parser.add_argument("--limit", type=int, default=100, help="最多匯出筆數")
    parser.add_argument("--since", default="", help="起始日期 YYYY-MM-DD（篩選 created_at）")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    # 連線
    conn = get_db_connection()
    if not conn:
        sys.exit(1)

    try:
        # 檢查表是否存在
        if not check_table_exists(conn):
            print("[export] problem_cards 表不存在，請先執行 SQL/Schema.sql 建表")
            sys.exit(0)

        # 撈資料
        cards = fetch_novel_cards(conn, args.limit, args.since)
        if not cards:
            print("[export] 沒有找到符合條件的新案例 (is_novel=true, status=resolved/escalated)")
            sys.exit(0)

        if args.verbose:
            print(f"[export] 找到 {len(cards)} 筆新案例")

        # 轉為 silver 格式
        silver_docs = []
        for card in cards:
            doc = card_to_silver_doc(card)
            silver_docs.append(doc)
            if args.verbose:
                print(f"  [{card['card_id']}] {card.get('symptom_summary', '')[:50]}...")

        # 寫入
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = OUTPUT_DIR / f"novel_export_{timestamp}.json"
        out_path.write_text(
            json.dumps(silver_docs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"\n[export] 完成！匯出 {len(silver_docs)} 筆至 {out_path}")
        print(f"[export] 下一步：cd data && python pipeline/silver_to_knowledge/enrich_fault_trees.py --verbose")

    finally:
        conn.close()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
