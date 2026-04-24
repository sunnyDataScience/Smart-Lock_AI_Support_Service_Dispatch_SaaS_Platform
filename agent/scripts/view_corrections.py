"""查看 data_corrections 表中使用者提出的資料修正紀錄。

用法：
    python scripts/view_corrections.py                     # 顯示最近 20 筆 pending
    python scripts/view_corrections.py --all               # 顯示全部（含已處理）
    python scripts/view_corrections.py --user {user_id}    # 查看特定使用者
    python scripts/view_corrections.py --export            # 匯出為 JSON
    python scripts/view_corrections.py --export out.json   # 匯出至指定檔案
    python scripts/view_corrections.py --clear             # 清空全部紀錄（需確認）
"""

import os
import sys
import json
import asyncio
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"))


def format_timestamp(ts):
    if ts is None:
        return "—"
    try:
        if isinstance(ts, datetime):
            return ts.strftime("%Y-%m-%d %H:%M:%S")
        return str(ts)[:19]
    except Exception:
        return str(ts)


def truncate(text: str, max_len: int = 80) -> str:
    if not text:
        return ""
    first_line = text.split("\n")[0]
    if len(first_line) > max_len:
        return first_line[:max_len] + "..."
    return first_line


async def view_corrections(user_id=None, show_all=False, export_path=None):
    pg_uri = os.getenv("POSTGRES_URI")
    if not pg_uri:
        print("\n[錯誤] 環境變數 POSTGRES_URI 未設定。")
        return

    try:
        from psycopg import AsyncConnection

        conn = await AsyncConnection.connect(pg_uri)

        # 組裝查詢
        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = %s")
            params.append(user_id)
        if not show_all:
            conditions.append("status = 'pending'")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = (
            f"SELECT id, user_id, note, conversation_context, user_facts, status, created_at "
            f"FROM data_corrections {where} "
            f"ORDER BY created_at DESC"
        )

        cursor = await conn.execute(query, params or None)
        rows = await cursor.fetchall()
        await conn.close()

        if not rows:
            label = "pending " if not show_all else ""
            print(f"\n[!] 目前尚無{label}資料修正紀錄。")
            return

        # 匯出 JSON
        if export_path is not None:
            records = []
            for rid, uid, note, context, facts, status, created_at in rows:
                facts_parsed = json.loads(facts) if isinstance(facts, str) else (facts or {})
                records.append({
                    "id": rid,
                    "user_id": uid,
                    "note": note or "",
                    "conversation_context": context,
                    "user_facts": facts_parsed,
                    "status": status,
                    "created_at": format_timestamp(created_at),
                })

            output = export_path if export_path else "data_corrections.json"
            with open(output, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            print(f"\n[OK] 已匯出 {len(records)} 筆紀錄至 {output}")
            return

        # 終端顯示
        mode = "全部紀錄" if show_all else "Pending 紀錄"
        user_label = f" — 使用者: {user_id}" if user_id else ""
        print(f"\n{'='*120}")
        print(f"  Data Corrections — {mode}{user_label}")
        print(f"{'='*120}")

        for rid, uid, note, context, facts, status, created_at in rows:
            facts_parsed = json.loads(facts) if isinstance(facts, str) else (facts or {})

            # 狀態顏色
            if status == "pending":
                status_display = "\033[93m PENDING \033[0m"
            elif status == "resolved":
                status_display = "\033[92m RESOLVED\033[0m"
            else:
                status_display = f" {status:<8}"

            print(f"\n  #{rid}  |  {status_display}  |  {format_timestamp(created_at)}")
            print(f"  User: {uid}")

            if facts_parsed:
                facts_str = ", ".join(f"{k}={v}" for k, v in facts_parsed.items() if v)
                print(f"  Facts: {facts_str}")

            if note:
                print(f"  Note: {note}")

            print(f"  {'─'*100}")

            # 對話歷史
            if context:
                lines = context.strip().split("\n")
                for line in lines[-20:]:  # 最多顯示最近 20 行
                    if line.startswith("用戶:"):
                        print(f"    \033[94m{line}\033[0m")
                    elif line.startswith("客服:"):
                        print(f"    \033[92m{truncate(line, 100)}\033[0m")
                    else:
                        print(f"    {truncate(line, 100)}")
                if len(lines) > 20:
                    print(f"    ... 共 {len(lines)} 行（僅顯示最後 20 行）")

            print(f"  {'─'*100}")

        print(f"\n{'='*120}")
        print(f">>> 共 {len(rows)} 筆紀錄。")

        # 統計
        pending_count = sum(1 for r in rows if r[5] == "pending")
        resolved_count = sum(1 for r in rows if r[5] == "resolved")
        if show_all:
            print(f">>> {pending_count} 筆待處理 / {resolved_count} 筆已處理。")

    except Exception as e:
        if "data_corrections" in str(e) and "does not exist" in str(e):
            print("\n[錯誤] data_corrections 表不存在。")
            print("請先啟動 server 讓 data_correction.init_db() 建立表。")
        else:
            print(f"\n[錯誤] 發生意外：{e}")


async def clear_corrections():
    """清空 data_corrections 表中的所有紀錄。"""
    pg_uri = os.getenv("POSTGRES_URI")
    if not pg_uri:
        print("\n[錯誤] 環境變數 POSTGRES_URI 未設定。")
        return

    try:
        from psycopg import AsyncConnection

        conn = await AsyncConnection.connect(pg_uri)

        # 先查筆數
        cursor = await conn.execute("SELECT COUNT(*) FROM data_corrections")
        count = (await cursor.fetchone())[0]

        if count == 0:
            print("\n[!] 表中沒有任何紀錄，無需清空。")
            await conn.close()
            return

        confirm = input(f"\n⚠️  確定要刪除全部 {count} 筆資料修正紀錄嗎？此操作無法復原。(y/N): ")
        if confirm.strip().lower() != "y":
            print("已取消。")
            await conn.close()
            return

        await conn.execute("DELETE FROM data_corrections")
        await conn.commit()
        await conn.close()
        print(f"\n[OK] 已清空 {count} 筆紀錄。")

    except Exception as e:
        print(f"\n[錯誤] 發生意外：{e}")


if __name__ == "__main__":
    target_user = None
    show_all = False
    export_path = None
    do_clear = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--user" and i + 1 < len(args):
            target_user = args[i + 1]
            i += 2
        elif args[i] == "--all":
            show_all = True
            i += 1
        elif args[i] == "--export":
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                export_path = args[i + 1]
                i += 2
            else:
                export_path = ""
                i += 1
        elif args[i] == "--clear":
            do_clear = True
            i += 1
        else:
            i += 1

    if do_clear:
        asyncio.run(clear_corrections())
    else:
        asyncio.run(view_corrections(user_id=target_user, show_all=show_all, export_path=export_path))
