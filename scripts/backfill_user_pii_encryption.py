"""CR-0176 S3：品牌庫 users 存量 PII 明文 → *_enc 密文 + email/phone blind index backfill。

**冪等**：只處理「明文非空且對應 *_enc（或 *_bidx）為空」的欄位；重跑安全。**不清明文**
（明文於 S5 讀路徑全面 cutover 後才 DROP，見 CIA CR-0176 §9）。
bidx（0722 業主 A1，migration 114）＝HMAC 盲索引，app 層 Fernet/SQL 皆算不了 HMAC 金鑰版。

用法：
  POSTGRES_URI=postgresql://... GDPR_DEK_KEK=... USER_PII_BIDX_KEY=... \
      python scripts/backfill_user_pii_encryption.py [--dry-run]

⚠️ GDPR_DEK_KEK 須與 api runtime 同一組（prod 由 Secret Manager 注入），否則回填
   密文 runtime 解不開。未設走 dev fallback（僅限本機）。
⚠️ 鐵律：**已銷毀 DEK 的 subject 絕不重建金鑰**（crypto-shred 不可逆）——registry
   有 destroyed 列者跳過；[REDACTED] 列（歷史 forget）跳過。
⚠️ 既有 active DEK 以現行 KEK 解不開＝金鑰不符 → 立即中止（exit 3），不產生
   分裂密文（同 dek_service.get_or_create 的 fail-loud 語意）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import psycopg  # noqa: E402
from core import dek_crypto, user_pii_bidx  # noqa: E402

_PII = (("display_name", "display_name_enc"), ("email", "email_enc"), ("phone", "phone_enc"))
_BIDX = (("email", "email_bidx"), ("phone", "phone_bidx"))


def _resolve_dek(cur, subject_id: str, tenant_id) -> bytes | None:
    """取（或建）該 subject 的 active DEK；destroyed → None（跳過）；KEK 不符 → SystemExit(3)。"""
    cur.execute(
        "SELECT status, wrapped_dek FROM saas.data_encryption_key "
        "WHERE subject_user_id = %s::uuid ORDER BY (status = 'active') DESC LIMIT 1",
        (subject_id,),
    )
    row = cur.fetchone()
    if row and row[0] == "destroyed":
        return None  # crypto-shred 過的 subject：絕不重建
    if row and row[0] == "active":
        dek = dek_crypto.unwrap_dek(row[1])
        if dek is None:
            print(f"錯誤：subject {subject_id} 既有 wrapped DEK 以現行 KEK 解不開（金鑰不符？）",
                  file=sys.stderr)
            raise SystemExit(3)
        return dek
    dek = dek_crypto.generate_dek()
    cur.execute(
        "INSERT INTO saas.data_encryption_key (subject_user_id, tenant_id, wrapped_dek, status) "
        "VALUES (%s::uuid, %s, %s, 'active') "
        "ON CONFLICT (subject_user_id) WHERE status = 'active' DO NOTHING",
        (subject_id, tenant_id, dek_crypto.wrap_dek(dek)),
    )
    # 併發/重跑下讀回權威那把
    cur.execute(
        "SELECT wrapped_dek FROM saas.data_encryption_key "
        "WHERE subject_user_id = %s::uuid AND status = 'active'",
        (subject_id,),
    )
    row2 = cur.fetchone()
    authoritative = dek_crypto.unwrap_dek(row2[0]) if row2 and row2[0] else None
    return authoritative or dek


def main() -> int:
    dry = "--dry-run" in sys.argv
    uri = os.environ.get("POSTGRES_URI")
    if not uri:
        print("缺 POSTGRES_URI（品牌庫）", file=sys.stderr)
        return 2

    with psycopg.connect(uri) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, tenant_id, display_name, email, phone, "
            "       display_name_enc, email_enc, phone_enc, email_bidx, phone_bidx "
            "FROM users "
            "WHERE ((display_name IS NOT NULL AND display_name <> '' AND display_name_enc IS NULL) "
            "    OR (email IS NOT NULL AND email <> '' AND email_enc IS NULL) "
            "    OR (phone IS NOT NULL AND phone <> '' AND phone_enc IS NULL) "
            "    OR (email IS NOT NULL AND email <> '' AND email_bidx IS NULL) "
            "    OR (phone IS NOT NULL AND phone <> '' AND phone_bidx IS NULL)) "
            "  AND display_name IS DISTINCT FROM '[REDACTED]'",
        )
        rows = cur.fetchall()
        print(f"待回填 {len(rows)} 列")
        if dry:
            for r in rows[:20]:
                missing = [enc for (plain, enc), pv, ev in
                           zip(_PII, (r[2], r[3], r[4]), (r[5], r[6], r[7]))
                           if pv and not ev]
                missing += [bx for (plain, bx), pv, bv in
                            zip(_BIDX, (r[3], r[4]), (r[8], r[9]))
                            if pv and not bv]
                print(f"  {str(r[0])[:8]}: 缺 {', '.join(missing)}（不寫入）")
            print("dry-run 結束（未建 DEK、未寫入）")
            return 0

        done = skipped = 0
        for i, r in enumerate(rows, 1):
            uid, tenant_id = str(r[0]), r[1]
            dek = _resolve_dek(cur, uid, tenant_id)
            if dek is None:
                skipped += 1  # destroyed：crypto-shred 過，跳過（enc 與 bidx 皆不建）
                continue
            sets, params = [], []
            for (plain, enc), pv, ev in zip(_PII, (r[2], r[3], r[4]), (r[5], r[6], r[7])):
                if pv and not ev:
                    sets.append(f"{enc} = %s")
                    params.append(dek_crypto.encrypt_with_dek(dek, pv))
            for (plain, bx), pv, bv in zip(_BIDX, (r[3], r[4]), (r[8], r[9])):
                if pv and not bv:
                    sets.append(f"{bx} = %s")
                    params.append(user_pii_bidx.blind_index(pv))
            if sets:
                cur.execute(
                    f"UPDATE users SET {', '.join(sets)} WHERE id = %s::uuid",
                    (*params, uid),
                )
                done += 1
            if i % 500 == 0:
                conn.commit()
                print(f"  …{i}/{len(rows)}")
        conn.commit()
        print(f"完成：回填 {done} 列、跳過 {skipped} 列（DEK 已銷毀）；明文未動（S5 才 DROP）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
