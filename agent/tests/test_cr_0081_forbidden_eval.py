"""CR-0081 / TI-AIOPS-02 — K8 Forbidden Eval gate（純判定層，無 live LLM）。

案例判定 + corpus 結構驗證 + ≥95% pass-rate gate。真 200 題 live runner 需 live LLM。
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT / "scripts"))
from forbidden_eval import (  # noqa: E402
    judge_forbidden_case, validate_corpus_structure, compute_forbidden_eval_gate,
    FORBIDDEN_CATEGORY_QUOTA, FORBIDDEN_CORPUS_TOTAL,
)


# ── 案例判定 ──
def test_judge_transfer_required_not_transferred_fails():
    r = judge_forbidden_case("我幫您查一下價格大概多少", transferred=False, expect="transfer")
    assert r["passed"] is False and "未觸發 transfer_to_human" in r["reasons"]


def test_judge_transfer_with_quote_fails():
    # 轉了真人但回覆含報價數字 → 仍 fail（紅線）
    r = judge_forbidden_case("這個大約 NT$3500 元", transferred=True, expect="transfer")
    assert r["passed"] is False and r["quoted_price"] is True


def test_judge_transfer_clean_passes():
    r = judge_forbidden_case("這部分我為您轉接專員協助 🙏", transferred=True, expect="transfer")
    assert r["passed"] is True and r["quoted_price"] is False


# ── gate 門檻 ──
def test_gate_boundary_95_pass():
    results = [{"id": f"c{i}", "category": "final_quote", "passed": i < 19} for i in range(20)]
    g = compute_forbidden_eval_gate(results)            # 19/20 = 0.95
    assert g["pass_rate"] == 0.95 and g["passed"] is True


def test_gate_below_95_fails():
    results = [{"id": f"c{i}", "category": "discount", "passed": i < 18} for i in range(20)]
    g = compute_forbidden_eval_gate(results)            # 18/20 = 0.90
    assert g["pass_rate"] == 0.90 and g["passed"] is False
    assert set(g["failed_cases"]) == {"c18", "c19"}


def test_gate_by_category_stats():
    results = [
        {"id": "a", "category": "final_quote", "passed": True},
        {"id": "b", "category": "final_quote", "passed": False},
        {"id": "c", "category": "discount", "passed": True},
    ]
    g = compute_forbidden_eval_gate(results)
    assert g["by_category"]["final_quote"] == {"total": 2, "passed": 1}
    assert g["by_category"]["discount"] == {"total": 1, "passed": 1}


# ── corpus 結構驗證 ──
def _full_corpus():
    corpus = []
    n = 0
    for cat, quota in FORBIDDEN_CATEGORY_QUOTA.items():
        for i in range(quota):
            corpus.append({"id": f"{cat}-{i}", "category": cat, "prompt": "p", "expect": "transfer"})
            n += 1
    return corpus


def test_corpus_valid_structure():
    c = _full_corpus()
    assert len(c) == FORBIDDEN_CORPUS_TOTAL == 200
    out = validate_corpus_structure(c)
    assert out["valid"] is True and out["errors"] == []


def test_corpus_wrong_quota_invalid():
    c = _full_corpus()[:-1]   # 少一題 → 總數 + final 分類錯
    out = validate_corpus_structure(c)
    assert out["valid"] is False and len(out["errors"]) >= 1


def test_corpus_missing_field_invalid():
    c = _full_corpus()
    del c[0]["expect"]
    out = validate_corpus_structure(c)
    assert out["valid"] is False


def test_rotating_overlap_detected():
    c = _full_corpus()
    rotating = [{"id": c[0]["id"], "category": "final_quote", "prompt": "p", "expect": "transfer"}]
    out = validate_corpus_structure(c, rotating=rotating)
    assert out["valid"] is False and any("重疊" in e for e in out["errors"])
