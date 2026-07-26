"""CR-0136 可觀測性基線＋migration drift-check（WBS 1.4.1 / 1.6.1）。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_observability_noop_without_endpoint(monkeypatch):
    """未設 OTLP endpoint → setup 回 False（no-op，單機行為不變）。"""
    from fastapi import FastAPI
    from core import observability

    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    app = FastAPI()
    assert observability.setup_observability(app) is False


def test_observability_failsoft_on_bad_config(monkeypatch):
    """設了 endpoint 但套件缺/初始化失敗 → 降級 False，不 raise（不癱瘓服務）。"""
    from fastapi import FastAPI
    from core import observability

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector.invalid:4317")
    app = FastAPI()
    # 套件裝了會嘗試連（Batch processor 背景不阻塞）→ 仍回 bool，關鍵是不 raise
    result = observability.setup_observability(app)
    assert isinstance(result, bool)


def test_migration_drift_check_passes():
    """migration drift-check（**檔案層**守門）退出碼 0。

    只驗檔案層（編號/登記/死列）——刻意剔除 DB URI env，避免對本機 pytest 庫（常
    落後數支 migration）做 DB 真值對照而假紅（LOCK-62 多庫 DB 對照屬部署/opt-in 段）。
    """
    import os
    root = Path(__file__).resolve().parents[2]
    env = {k: v for k, v in os.environ.items()
           if k not in ("POSTGRES_URI", "TECH_POSTGRES_URI", "PLATFORM_POSTGRES_URI")}
    r = subprocess.run(
        ["python", str(root / "scripts" / "ci" / "migration-drift-check.py")],
        capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
