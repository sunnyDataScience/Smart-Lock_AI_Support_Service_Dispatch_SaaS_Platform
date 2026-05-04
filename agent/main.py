"""Product info 架構自檢腳本 — 不打 LLM/DB，純驗證 mega-doc 載入與 profile gating。

此腳本為清掉舊 skills/data 後的 smoke test：
  1. product_info loader 能讀完所有 mega-doc
  2. filter_loadable() 在 4 種 profile 組合下回傳正確清單
  3. 抽查 studio_results 真實案例的關鍵字是否落在對應 mega-doc 內

執行：cd agent && python main.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from product_info import all_docs, filter_loadable, get_doc, has_brand, load_all_docs

ROOT = Path(__file__).parent / "product_info"

# studio_results_20260504_1507.json 的 6 個對話案例對應的最低覆蓋關鍵字
# 每個 tuple = (案例 ID, 預期載入的 doc 名稱, 必須命中的關鍵字 list)
STUDIO_CASES = [
    ("3 Chatlock A90 設掌紋（無 App）", "Chatlock/A90", ["新增掌靜脈", "新增普通用戶", "管理員模式"]),
    ("4 Chatlock A90 設指紋（無 App）", "Chatlock/A90", ["新增指紋", "新增普通用戶"]),
    ("5 Dormakaba AS850 設指紋", "Dormakaba/AS850", ["指紋設定", "註冊", "管理者密碼"]),
    ("6 Dormakaba AS850 設卡片", "Dormakaba/AS850", ["卡片設定", "註冊", "RFID"]),
    ("7 Dormakaba AS850 WiFi", "Dormakaba/AS850", ["WiFi", "drive.google.com"]),
    ("8 _common dispatch 想換電子鎖", "_common/dispatch", ["安裝預約", "照片"]),
]

PROFILE_MATRIX = [
    # (label, brand, model, expected names contains)
    ("D 全未知", None, None, ["_common/troubleshoot", "_common/dispatch"]),
    ("C brand-only Chatlock", "Chatlock", None, ["_common/troubleshoot"]),  # B 路徑只載 _common
    ("A Chatlock/A90", "Chatlock", "A90", ["Chatlock/A90", "_common/troubleshoot"]),
    ("A Dormakaba/AS850", "Dormakaba", "AS850", ["Dormakaba/AS850", "_common/dispatch"]),
    ("A Dormakaba/FA9000", "Dormakaba", "FA9000", ["Dormakaba/FA9000", "_common/store-info"]),
]

KNOWN_BRANDS = ["Chatlock", "Dormakaba", "Philips", "Kaadas", "Milre", "AiLock", "3E"]


def section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def ok(label: str) -> None:
    print(f"  ✓ {label}")


def fail(label: str) -> None:
    print(f"  ✗ {label}")


def main() -> int:
    failed = 0

    # 1. loader 自檢
    section("1. Product info loader")
    docs = load_all_docs(ROOT)
    print(f"  載入 {len(docs)} 份 mega-doc")
    if len(docs) == 0:
        fail("沒有任何 mega-doc 被載入")
        return 1
    ok(f"目錄 {ROOT.relative_to(Path.cwd().parent)} 可讀")

    # 2. brand 覆蓋檢查（對應 brand_model_list.md）
    section("2. 品牌覆蓋（對齊 docs/brand_model_list.md）")
    for brand in KNOWN_BRANDS:
        present = has_brand(brand)
        (ok if present else fail)(f"{brand}: {'有 product_info' if present else '缺 product_info'}")
        if not present:
            failed += 1

    # 3. profile gating 矩陣
    section("3. filter_loadable() 矩陣")
    for label, brand, model, must_contain in PROFILE_MATRIX:
        loaded = filter_loadable(brand, model)
        names = {d.name for d in loaded}
        missing = [n for n in must_contain if n not in names]
        if not missing:
            ok(f"{label}: 載入 {len(loaded)} 份，含 {must_contain}")
        else:
            fail(f"{label}: 缺 {missing}（實際載入 {sorted(names)[:5]}...）")
            failed += 1

        # 額外驗證：brand+model 齊備時，不能載入其他品牌的 mega-doc
        if brand and model:
            other_brand_docs = [d.name for d in loaded if d.brand not in (brand, "_common")]
            if other_brand_docs:
                fail(f"  └ gating 失效：載入了 {other_brand_docs}")
                failed += 1
            else:
                ok(f"  └ gating OK：未載入其他品牌")

    # 4. studio_results 案例關鍵字命中
    section("4. studio_results 案例覆蓋")
    for case_id, doc_name, keywords in STUDIO_CASES:
        doc = get_doc(doc_name)
        if doc is None:
            fail(f"{case_id}: doc {doc_name} 不存在")
            failed += 1
            continue
        body = doc.body
        missing_kw = [kw for kw in keywords if kw not in body]
        if not missing_kw:
            ok(f"{case_id} → {doc_name} 命中 {keywords}")
        else:
            fail(f"{case_id} → {doc_name} 缺關鍵字 {missing_kw}")
            failed += 1

    # 5. 確認舊 skills/data 已清空
    section("5. 舊 skills/data 已清空")
    skills_data = Path(__file__).parent / "skills" / "data"
    if skills_data.exists():
        fail(f"{skills_data} 仍存在")
        failed += 1
    else:
        ok("agent/skills/data 已刪除")

    # 6. agent build 不出錯
    section("6. build_agent() 仍可建構")
    try:
        from agent import build_agent  # noqa: F401
        ok("agent.py 可 import")
    except Exception as e:
        fail(f"build_agent import 失敗：{e}")
        failed += 1

    section("結果")
    if failed:
        print(f"  ✗ {failed} 個檢查失敗")
        return 1
    print("  ✓ 全部通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
