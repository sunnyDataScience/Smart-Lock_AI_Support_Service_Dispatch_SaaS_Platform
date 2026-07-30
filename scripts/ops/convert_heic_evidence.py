#!/usr/bin/env python3
"""把既有 HEIC 完工證據轉為 JPEG（CR-0194 §6 業主裁決選項 1）。

WHY：
  瀏覽器 <img> 無法解碼 HEIC → 品牌端審核完工證據時是破圖，而完工硬閘仍算
  「有照片」＝閘門過了、證據看不到。CR-0194 已擋住未來上傳，但既有列不追溯
  （`routers/media.py` 直接回 DB 存的 content_type）。本腳本處理存量。

  業主裁決選「伺服器端一次性轉檔」而非「請師傅補拍」，理由是師傅早已離場、
  補拍成本高；**條件是必須留下轉檔痕跡**——平台改動了完工證據，爭議時要能還原
  這件事是誰在何時做的、原檔的雜湊是什麼。故每筆轉檔都寫一筆 work_order_events
  （`other` + `payload.kind='media_converted'`，附原始 sha256 與原尺寸）。

執行位置：**容器內**（需要 core.media_crypto 的金鑰與 MEDIA_ROOT）。
  HEIC 解碼不在容器內（無 pillow-heif），故 JPEG 由外部先備妥放進 --staging-dir，
  本腳本負責：驗證 → 加密落盤 → 更新 DB → 寫事件 → 刪原檔。

  若日後在 image 內裝了 pillow-heif，可把 decode 併進來省掉 staging 步驟。

用法：
  python scripts/ops/convert_heic_evidence.py --staging-dir /tmp/jpeg --dry-run
  python scripts/ops/convert_heic_evidence.py --staging-dir /tmp/jpeg --apply

安全性：
  - `--dry-run` 為預設；不帶 `--apply` 絕不寫入。
  - 每筆都先驗 staging JPEG 的 magic bytes，不符就跳過該筆（不動 DB）。
  - 原檔改名為 `.heic.superseded` 而非直接刪除（保留人工回復餘地）。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app/api" if Path("/app/api").exists() else ".")

import core.db as db_module  # noqa: E402
from core.db import _ensure_conn  # noqa: E402

JPEG_MAGIC = b"\xff\xd8\xff"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staging-dir", required=True,
                    help="放置已轉好的 {media_id}.jpg 的目錄")
    ap.add_argument("--apply", action="store_true", help="真的寫入（預設 dry-run）")
    args = ap.parse_args()

    staging = Path(args.staging_dir)
    media_root = Path(os.environ.get("MEDIA_ROOT", "/app/api/data/media"))

    if not await _ensure_conn():
        print("❌ DB 連不上", file=sys.stderr)
        return 1

    from core import media_crypto
    from services.work_order_service import _insert_wo_event

    cur = await db_module._conn.execute(
        "SELECT id, tenant_id, work_order_id, purpose, storage_path, "
        "       size_bytes, sha256, filename "
        "FROM media_files WHERE content_type = 'image/heic' AND deleted_at IS NULL "
        "ORDER BY created_at"
    )
    rows = await cur.fetchall()
    print(f"待轉筆數：{len(rows)}（模式：{'APPLY' if args.apply else 'DRY-RUN'}）\n")
    if not rows:
        print("沒有 image/heic 列，無事可做。")
        return 0

    converted = skipped = 0
    for mid, tid, woid, purpose, spath, old_size, old_sha, old_name in rows:
        mid, spath = str(mid), str(spath)
        tag = mid[:8]
        jpg_src = staging / f"{mid}.jpg"
        if not jpg_src.exists():
            print(f"⏭  {tag} staging 缺 {jpg_src.name} → 跳過（不動 DB）")
            skipped += 1
            continue

        new_bytes = jpg_src.read_bytes()
        if not new_bytes.startswith(JPEG_MAGIC):
            print(f"⏭  {tag} staging 檔頭不是 JPEG → 跳過（不動 DB）")
            skipped += 1
            continue

        new_sha = hashlib.sha256(new_bytes).hexdigest()
        new_rel = spath.rsplit(".", 1)[0] + ".jpg"
        new_abs = media_root / new_rel
        old_abs = media_root / spath

        print(f"→  {tag} {purpose}")
        print(f"     {old_size:>9,} bytes .heic  →  {len(new_bytes):>9,} bytes .jpg")
        print(f"     {spath}")
        print(f"  →  {new_rel}")

        if not args.apply:
            continue

        # 落盤：比照 media_service 的寫入路徑加密（sha256 仍算明文）
        new_abs.parent.mkdir(parents=True, exist_ok=True)
        new_abs.write_bytes(media_crypto.encrypt_bytes(new_bytes))

        await db_module._conn.execute(
            "UPDATE media_files SET content_type = 'image/jpeg', "
            "  storage_path = %s, size_bytes = %s, sha256 = %s, "
            "  filename = %s "
            "WHERE id = %s::uuid",
            (new_rel, len(new_bytes), new_sha,
             (old_name or f"{mid}.heic").rsplit(".", 1)[0] + ".jpg", mid),
        )

        # 轉檔痕跡：這是業主同意轉檔的**條件**。
        # ⚠️ 措辭要準確：HEIC → JPEG 是**有損轉碼**，不是單純換容器格式。
        # 所以留痕不是為了主張「內容沒變」，而是為了讓爭議時能還原：
        # 誰在何時轉的、原檔雜湊與尺寸是什麼、原檔還在哪（.heic.superseded）。
        if woid:
            await _insert_wo_event(
                wo_id=str(woid), tenant_id=str(tid), actor_user_id=None,
                event_type="other",
                payload={
                    "kind": "media_converted",
                    "reason": "HEIC 無法在瀏覽器預覽（CR-0194 §6 業主裁決一次性轉檔）",
                    # 明說是有損轉碼，不讓後人誤讀為無損換殼
                    "transcode": "lossy (HEIC→JPEG q90, full resolution retained)",
                    "original_retained_as": spath + ".superseded",
                    "media_id": mid,
                    "purpose": purpose,
                    "from": {"content_type": "image/heic",
                             "storage_path": spath,
                             "size_bytes": old_size,
                             "sha256": old_sha},
                    "to": {"content_type": "image/jpeg",
                           "storage_path": new_rel,
                           "size_bytes": len(new_bytes),
                           "sha256": new_sha},
                },
            )

        # 原檔改名保留（不直接刪，留人工回復餘地）
        if old_abs.exists():
            old_abs.rename(old_abs.with_suffix(".heic.superseded"))
        converted += 1

    print(f"\n完成：轉換 {converted} 筆、跳過 {skipped} 筆")
    if not args.apply:
        print("（DRY-RUN，未寫入。加 --apply 才真的執行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
