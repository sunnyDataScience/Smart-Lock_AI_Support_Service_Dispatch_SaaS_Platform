"""CR-0166 R5：provision_brand.py 純邏輯 smoke test（不需 DB/部署）。

跑法：uv run pytest scripts/deploy/test_provision_brand.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import provision_brand as pb  # noqa: E402


def test_render_brand_env_substitutes_slug():
    env = pb.render_brand_env("acme", tenant_id="11111111-2222-3333-4444-555555555555")
    assert 'PROJECT_ID="lock-ai-acme"' in env
    assert 'REPO="lock-ai-acme-repo"' in env
    assert "AGENT_TENANT_ID=" in env
    assert "11111111-2222-3333-4444-555555555555" in env


def test_render_without_tenant_placeholder_agent_tenant():
    env = pb.render_brand_env("beta")
    assert 'PROJECT_ID="lock-ai-beta"' in env
    # 未帶 tenant → AGENT_TENANT_ID 留空佔位提醒手動填（不沿用模板的預設租戶）
    assert 'AGENT_TENANT_ID=""' in env
    assert "00000000-0000-0000-0000-000000000001" not in env


def test_bad_slug_rejected():
    assert pb.main(["--slug", "AB", "--dry-run"]) == 1  # 太短＋大寫
    assert pb.main(["--slug", "1acme", "--dry-run"]) == 1  # 數字開頭


def test_unknown_module_rejected():
    assert pb.main(["--slug", "acme", "--modules", "bogus", "--dry-run"]) == 1


def test_dry_run_ok(capsys):
    rc = pb.main(["--slug", "acme", "--tenant-id",
                  "11111111-2222-3333-4444-555555555555",
                  "--plan-tier", "pro", "--modules", "refinery", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "checklist" in out
    assert "refinery" in out
    assert "Casdoor org 同步" in out
