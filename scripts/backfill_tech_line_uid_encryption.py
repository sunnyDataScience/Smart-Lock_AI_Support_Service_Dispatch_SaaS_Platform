#!/usr/bin/env python3
"""CR-0173：回填既有明文 technicians.line_user_id → 加密欄，並清空明文。

app 層 Fernet（SQL 無法跑）。**冪等**：只處理 line_user_id 非空且 line_user_id_enc
為空者；重跑安全。app 端 dual-read 期間可先不回填（legacy 明文仍可讀），本腳本用於
把存量明文 PII 就地加密、為日後 DROP 明文欄鋪路。

用法（技師權威庫）：
  TECH_POSTGRES_URI=postgresql://user:pw@host:5434/lock_tech \\
  LINE_UID_ENC_KEY=... LINE_UID_BIDX_KEY=... \\
  python scripts/backfill_tech_line_uid_encryption.py [--dry-run]

⚠️ 金鑰須與 app runtime 同一組（LINE_UID_ENC_KEY / LINE_UID_BIDX_KEY），否則回填後
   app 解不開／bidx 對不上。prod 由 Secret Manager 注入同一組。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 讓 script 能 import api/core/line_uid_crypto.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import psycopg  # noqa: E402

from core import line_uid_crypto  # noqa: E402


def main() -> int:
    dry = "--dry-run" in sys.argv
    uri = os.environ.get("TECH_POSTGRES_URI") or os.environ.get("POSTGRES_URI")
    if not uri:
        print("需設 TECH_POSTGRES_URI 或 POSTGRES_URI", file=sys.stderr)
        return 2

    with psycopg.connect(uri) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, line_user_id FROM technicians "
            "WHERE line_user_id IS NOT NULL AND line_user_id_enc IS NULL"
        )
        rows = cur.fetchall()
        print(f"待回填 {len(rows)} 列" + (" (dry-run)" if dry else ""))
        n = 0
        for tid, uid in rows:
            enc = line_uid_crypto.encrypt(uid)
            bidx = line_uid_crypto.blind_index(uid)
            if dry:
                print(f"  {str(tid)[:8]}: {str(uid)[:6]}… → enc/bidx（不寫入）")
                continue
            cur.execute(
                "UPDATE technicians SET line_user_id_enc = %s, line_user_id_bidx = %s, "
                "line_user_id = NULL WHERE id = %s",
                (enc, bidx, tid),
            )
            n += 1
        if not dry:
            conn.commit()
        print(f"完成：回填 {n} 列（明文已清空）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
