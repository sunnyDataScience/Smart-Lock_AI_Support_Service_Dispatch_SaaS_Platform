#!/usr/bin/env python3
"""品牌開站 provisioning 自動化（CR-0166 R5 / WBS 3.3.1 / ADR-002）。

把「核准品牌申請 → 開站」的手動步驟（原 _onboarding_guide 只產文字）腳本化：
  1. 產生品牌部署參數檔 scripts/deploy/brands/<slug>.env（自 locksmart.env 模板改值）
  2. 設定租戶 License（plan_tier + 開通模組）—— 走平台庫 tenant.entitled_modules
  3. 輸出開站 checklist（Casdoor org / secrets / compose 起站 / LINE 綁定）

用法：
  # dry-run（只驗證與顯示，不寫檔/不動 DB）
  uv run python scripts/deploy/provision_brand.py --slug acme --dry-run

  # 實際產出（寫 .env + 設 License；需 PLATFORM_POSTGRES_URI）
  PLATFORM_POSTGRES_URI=... uv run python scripts/deploy/provision_brand.py \
      --slug acme --tenant-id <uuid> --plan-tier pro --modules refinery

退出碼：0 成功；1 參數/驗證錯誤；2 DB 操作失敗。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATE = _ROOT / "scripts" / "deploy" / "brands" / "locksmart.env"
_BRANDS_DIR = _ROOT / "scripts" / "deploy" / "brands"

_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{2,29}$")
_KNOWN_MODULES = ("core", "refinery", "studio", "compiler")
_VALID_TIERS = ("free", "standard", "pro", "enterprise")


def render_brand_env(slug: str, *, tenant_id: str | None = None) -> str:
    """自 locksmart.env 模板產生新品牌 .env（改 PROJECT_ID / service 名 / AGENT_TENANT_ID）。"""
    template = _TEMPLATE.read_text(encoding="utf-8")
    # 逐行替換品牌專屬值（保守：只改明確的部署識別，其餘沿用模板註解）
    lines = []
    for line in template.splitlines():
        s = line.strip()
        if s.startswith("PROJECT_ID="):
            lines.append(f'PROJECT_ID="lock-ai-{slug}"')
        elif s.startswith("REPO="):
            lines.append(f'REPO="lock-ai-{slug}-repo"')
        elif s.startswith("SERVICE_ACCOUNT="):
            lines.append(f'SERVICE_ACCOUNT="lock-ai@lock-ai-{slug}.iam.gserviceaccount.com"')
        elif s.startswith("AGENT_TENANT_ID="):
            # 有帶 tenant_id 就替換模板值；否則保留佔位提醒手動填
            lines.append(f'AGENT_TENANT_ID="{tenant_id}"' if tenant_id
                         else 'AGENT_TENANT_ID=""  # ← 填新租戶 UUID')
        else:
            lines.append(line)
    header = (
        f"# brands/{slug}.env — 由 provision_brand.py 產生（CR-0166 R5）\n"
        f"# 品牌代號：{slug}\n"
        + (f"# 租戶 UUID（AGENT_TENANT_ID）：{tenant_id}\n" if tenant_id else "")
        + "#\n"
    )
    body = "\n".join(lines)
    return header + body + "\n"


def set_license(tenant_id: str, plan_tier: str, modules: list[str]) -> None:
    """設定租戶 License（平台庫 tenant.entitled_modules）。需 PLATFORM_POSTGRES_URI。"""
    import json

    import psycopg

    uri = os.getenv("PLATFORM_POSTGRES_URI") or os.getenv("POSTGRES_URI")
    if not uri:
        raise RuntimeError("需要 PLATFORM_POSTGRES_URI（或 POSTGRES_URI）設定 License")
    mods = list(dict.fromkeys(["core"] + [m for m in modules if m]))
    with psycopg.connect(uri) as conn:
        cur = conn.execute(
            "UPDATE tenant SET plan_tier=%s, entitled_modules=%s::jsonb, updated_at=NOW() "
            "WHERE id=%s::uuid RETURNING slug",
            (plan_tier, json.dumps(mods), tenant_id))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"租戶 {tenant_id} 不存在於平台庫")
        conn.commit()


def checklist(slug: str, tenant_id: str | None, plan_tier: str, modules: list[str]) -> str:
    return "\n".join([
        f"品牌開站 checklist — {slug}（plan={plan_tier}, modules={','.join(['core', *modules])}）",
        "",
        f"[1] ✅ 部署參數檔 scripts/deploy/brands/{slug}.env 已產生",
        f"[2] {'✅' if tenant_id else '⬜'} 租戶 License 已設定" + (f"（tenant={tenant_id}）" if tenant_id else "（--tenant-id 未帶，略過）"),
        "[3] ⬜ Casdoor org 同步：",
        f"      uv run python scripts/idp/casdoor_bootstrap.py --org {slug}",
        "[4] ⬜ Secret Manager 建 secrets（POSTGRES_URI/API_JWT_SECRET_KEY/",
        "      INTERNAL_API_TOKEN/LINE_CHANNEL_SECRET/LINE_CHANNEL_ACCESS_TOKEN）",
        "[5] ⬜ compose 起站（本機/自架）：",
        f"      BRAND={slug} docker compose -f web/brand-portal/docker-compose.yml up -d --build",
        f"      BRAND={slug} docker compose -f web/brand-portal/docker-compose.yml --profile init run --rm db-init",
        "[6] ⬜ LINE 綁定：webhook URL 填入 LINE console，rich menu 建立",
        # CR-0186：原 [7] 只寫「建 Admin」且無工具，且**完全漏了品牌庫 saas.tenant 列**——
        # 那是 24 個 FK 的 target，缺它則該品牌任何 per-tenant 寫入都 FK violation
        # （本腳本把平台庫 tenant UUID 寫進 AGENT_TENANT_ID，但品牌庫並沒有這一列）。
        "[7] ⬜ 品牌庫租戶列 + Admin 帳號（缺租戶列 → per-tenant 寫入全部 FK violation）：",
        "      ./scripts/db/provision-brand-tenant.sh \\",
        f"        --tenant-id {tenant_id or '<租戶UUID>'} --name '<品牌名>' \\",
        "        --email admin@<brand>.com --admin-name '<管理員>'",
        "      （密碼互動輸入或 export BRAND_ADMIN_PASSWORD；須先跑完 [5] 的 db-init）",
        "[8] ⬜ 通知申請人開通",
    ])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--slug", required=True, help="品牌代號（3-30 小寫英數連字號，字母開頭）")
    p.add_argument("--tenant-id", default=None, help="租戶 UUID（設 License 用；未帶則略過 License）")
    p.add_argument("--plan-tier", default="standard", choices=_VALID_TIERS)
    p.add_argument("--modules", default="", help="開通附加模組（逗號分隔，core 自動含）")
    p.add_argument("--dry-run", action="store_true", help="只驗證與顯示，不寫檔/不動 DB")
    args = p.parse_args(argv)

    if not _SLUG_RE.match(args.slug):
        print(f"❌ slug 格式錯誤：{args.slug}（需 3-30 小寫英數連字號、字母開頭）", file=sys.stderr)
        return 1
    modules = [m.strip() for m in args.modules.split(",") if m.strip()]
    unknown = [m for m in modules if m not in _KNOWN_MODULES]
    if unknown:
        print(f"❌ 未知模組：{', '.join(unknown)}（合法：{', '.join(_KNOWN_MODULES)}）", file=sys.stderr)
        return 1

    env_content = render_brand_env(args.slug, tenant_id=args.tenant_id)
    env_path = _BRANDS_DIR / f"{args.slug}.env"

    if args.dry_run:
        print(f"[dry-run] 將產生 {env_path}（{len(env_content.splitlines())} 行）")
        if args.tenant_id:
            print(f"[dry-run] 將設 License：tenant={args.tenant_id} tier={args.plan_tier} "
                  f"modules={['core', *modules]}")
        print()
        print(checklist(args.slug, args.tenant_id, args.plan_tier, modules))
        return 0

    if env_path.exists():
        print(f"⚠️  {env_path} 已存在，不覆蓋（手動處理避免蓋掉既有品牌設定）", file=sys.stderr)
        return 1
    env_path.write_text(env_content, encoding="utf-8")
    print(f"✅ 已產生 {env_path}")

    if args.tenant_id:
        try:
            set_license(args.tenant_id, args.plan_tier, modules)
            print(f"✅ 已設 License：tenant={args.tenant_id} tier={args.plan_tier} "
                  f"modules={['core', *modules]}")
        except Exception as e:  # noqa: BLE001
            print(f"❌ 設 License 失敗：{e}", file=sys.stderr)
            return 2

    print()
    print(checklist(args.slug, args.tenant_id, args.plan_tier, modules))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
