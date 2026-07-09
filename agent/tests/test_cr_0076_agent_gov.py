"""CR-0076 / TI-A04-02 + TI-A03-03 — RAG bronze-only 來源治理 + Agent KPI gate。

A04-02：references 嚴格限 bronze；GDrive PDF 不可信，只引 URL 不抄內容（bronze/gdrive
JSON link-only）。A03-03：KPI gate 門檻純邏輯（指標由 live eval 蒐集，本測門檻判定）。
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT / "scripts"))
from governance_checks import scan_references_sourcing, compute_agent_kpi_gate  # noqa: E402

REFS = AGENT_ROOT / "lockcore" / "skills" / "locksmith-product-knowledge" / "references"
BRONZE = AGENT_ROOT.parent / "knowledge-pipeline" / "storage" / "bronze"  # 2026-07-09 data/ 改名(ADR-029)


# ── 真實 references 全 bronze 合規（0 violation）──
def test_real_references_bronze_compliant():
    r = scan_references_sourcing(REFS, BRONZE)
    assert r["scanned_files"] >= 40 and r["total_urls"] > 100
    assert r["by_kind"].get("gdrive", 0) > 0    # 確實有引 GDrive
    assert r["violations"] == [], f"bronze 來源治理違規：{r['violations'][:3]}"


# ── scanner 偵測 GDrive bronze 缺失（種一個壞 URL）──
def test_scanner_detects_missing_bronze(tmp_path):
    refs = tmp_path / "references" / "Test"
    refs.mkdir(parents=True)
    (refs / "X.md").write_text(
        "# 測試\n見 https://drive.google.com/file/d/NONEXISTENT_FILE_ID_999/view\n", encoding="utf-8")
    (tmp_path / "bronze" / "gdrive").mkdir(parents=True)
    r = scan_references_sourcing(tmp_path / "references", tmp_path / "bronze")
    kinds = {v["kind"] for v in r["violations"]}
    assert "gdrive_bronze_missing" in kinds


# ── scanner 偵測非 link-only（bronze JSON 含正文 = 抄錄嫌疑）──
def test_scanner_detects_non_link_only(tmp_path):
    fid = "ABC123"
    refs = tmp_path / "references" / "Test"
    refs.mkdir(parents=True)
    (refs / "X.md").write_text(
        f"見 https://drive.google.com/file/d/{fid}/view\n", encoding="utf-8")
    bg = tmp_path / "bronze" / "gdrive"
    bg.mkdir(parents=True)
    # 含 transcript 正文 → 非 link-only
    (bg / f"{fid}.json").write_text(json.dumps(
        {"file_id": fid, "title": "X", "url": "u", "transcript": "抄錄的 PDF 全文..."}), encoding="utf-8")
    r = scan_references_sourcing(tmp_path / "references", tmp_path / "bronze")
    kinds = {v["kind"] for v in r["violations"]}
    assert "gdrive_not_link_only" in kinds


# ── KPI gate 邊界 pass ──
def test_kpi_gate_boundary_pass():
    g = compute_agent_kpi_gate(auto_resolve_rate=0.70, eval_pass_rate=0.85,
                               escalation_correct_rate=0.95, latency_p95_ms=8000)
    assert g["passed"] is True and not any(g["breaches"].values())


# ── KPI gate 各指標 breach → fail ──
@pytest.mark.parametrize("kw,breach_key", [
    ({"auto_resolve_rate": 0.69, "eval_pass_rate": 0.85, "escalation_correct_rate": 0.95, "latency_p95_ms": 8000}, "auto_resolve_rate"),
    ({"auto_resolve_rate": 0.70, "eval_pass_rate": 0.80, "escalation_correct_rate": 0.95, "latency_p95_ms": 8000}, "eval_pass_rate"),
    ({"auto_resolve_rate": 0.70, "eval_pass_rate": 0.85, "escalation_correct_rate": 0.90, "latency_p95_ms": 8000}, "escalation_correct_rate"),
    ({"auto_resolve_rate": 0.70, "eval_pass_rate": 0.85, "escalation_correct_rate": 0.95, "latency_p95_ms": 9000}, "latency_p95_ms"),
])
def test_kpi_gate_breaches(kw, breach_key):
    g = compute_agent_kpi_gate(**kw)
    assert g["passed"] is False and g["breaches"][breach_key] is True
