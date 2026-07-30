#!/usr/bin/env python3
"""稽核 media_files 列與 MEDIA_ROOT 實檔是否一致（UAT-D-005）。

WHY 需要這支：
  UAT-D-005 原判定寫「seed 不一致」，但查證後 **repo 內沒有任何 SQL 在 INSERT
  media_files** —— 那些列是過去真實 API 上傳留下的，檔案後來被清掉
  （DB volume 持久、media volume 曾被 reset）。所以真因是**兩個 volume 的
  生命週期不同步**，不是 seed 寫錯。

  這種不一致沒有任何測試會抓到（上傳與讀取各自都正常），只會在有人拿到 dangling
  列去驗 UI 時得到誤導性的 404，然後花時間懷疑是掛載或權限問題。與其每輪靠人踩，
  不如給一支能跑的稽核。

刻意保留的例外：
  `docs/uat/uat-results/local-testability-*.json` 需要一個**真 404** 來驗
  「照片載入失敗」佔位路徑。故白名單內的 id 允許 dangling，不計為缺陷。
  新增白名單項時務必在此註明用途，否則下一個人會把它「修好」。

用法：
  python scripts/ops/audit_media_consistency.py            # 只報告
  python scripts/ops/audit_media_consistency.py --strict   # 有問題就 exit 1（CI 用）
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app/api" if Path("/app/api").exists() else ".")

import core.db as db_module  # noqa: E402
from core.db import _ensure_conn  # noqa: E402

# id → 為什麼允許它 dangling
ALLOWED_DANGLING = {
    "71318627-4182-42d8-901d-4f3fbdfacff9":
        "UAT 負向測試 fixture：驗『照片載入失敗』佔位需要一個真 404（勿補檔）",
}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="發現『DB 有列但缺檔』就 exit 1（孤兒檔預設不計，見 --include-orphans）")
    ap.add_argument("--include-orphans", action="store_true",
                    help="把孤兒檔也計入 --strict 的失敗條件")
    args = ap.parse_args()

    media_root = Path(os.environ.get("MEDIA_ROOT", "/app/api/data/media"))
    if not await _ensure_conn():
        print("❌ DB 連不上", file=sys.stderr)
        return 2

    cur = await db_module._conn.execute(
        "SELECT id, storage_path, purpose, content_type "
        "FROM media_files WHERE deleted_at IS NULL ORDER BY created_at"
    )
    rows = await cur.fetchall()

    dangling, allowed, ok = [], [], 0
    for mid, spath, purpose, ct in rows:
        mid = str(mid)
        if (media_root / str(spath)).exists():
            ok += 1
        elif mid in ALLOWED_DANGLING:
            allowed.append((mid, ALLOWED_DANGLING[mid]))
        else:
            dangling.append((mid, spath, purpose, ct))

    # 反向：檔案存在但 DB 無列（孤兒檔）
    #
    # ⚠️ 必須排除 kyc-registration/：那些檔由**技師庫**的
    #    technician_registration_document 管理（CR-0115 §8-7 刻意與 tenant media
    #    隔離），本來就不會出現在 media_files。不排除的話這支會穩定報假警，
    #    而穩定的假警等於沒有警報。
    known = {str(r[1]) for r in rows}
    NOT_MEDIA_FILES_MANAGED = ("kyc-registration/",)
    orphans = []
    for p in media_root.rglob("*"):
        if not p.is_file() or p.name.endswith(".superseded"):
            continue
        rel = str(p.relative_to(media_root))
        if rel.startswith(NOT_MEDIA_FILES_MANAGED) or rel in known:
            continue
        orphans.append(rel)

    print(f"media_files 列：{len(rows)}（有檔 {ok} / 允許 dangling {len(allowed)} / "
          f"缺檔 {len(dangling)}）")
    print(f"孤兒檔（有檔無列）：{len(orphans)}")

    for mid, why in allowed:
        print(f"  📌 {mid[:8]} 允許 dangling — {why}")
    for mid, spath, purpose, ct in dangling:
        print(f"  ❌ {mid[:8]} 缺檔 purpose={purpose} ct={ct}\n       {spath}")
    for rel in orphans[:20]:
        print(f"  ⚠️  孤兒檔 {rel}")
    if len(orphans) > 20:
        print(f"  …另有 {len(orphans) - 20} 個孤兒檔未列出")

    # 「DB 有列但缺檔」是真缺陷：UI 會拿到誤導性 404。
    # 「孤兒檔」在本機是常態（DB reset 過但 media volume 沒清），無 DB 列指向、
    # API 讀不到，屬佔空間而非功能問題 → 預設只報告不算失敗，避免這支變成
    # 「永遠紅」而被忽略。要納入請帶 --include-orphans。
    blocking = len(dangling) + (len(orphans) if args.include_orphans else 0)
    if not dangling and not orphans:
        print("\n✅ 完全一致")
    elif not dangling:
        print(f"\n✅ 無缺檔（DB 列全部有檔）；另有 {len(orphans)} 個孤兒檔僅佔空間，"
              f"確認無用後可清理")
    else:
        print(f"\n❌ {len(dangling)} 列缺檔（會讓 UI 得到誤導性 404）")
    return 1 if (args.strict and blocking) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
