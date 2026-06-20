"""CR-0080 / TI-A09-01 + TI-AIOPS-08 — eval 評分/聚合/觀測純函式（mock judge，無 live LLM）。

eval 套件的 scoring/aggregation/parse 邏輯原 100% 埋在 main_async（0 pytest 覆蓋=假綠）。
本批抽成 module-level 純函式並用 fixture judge JSON 單元測（不呼叫真 LLM）。
"""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT / "scripts"))
from eval_reply_quality import (  # noqa: E402
    aggregate_scores, aggregate_by_category, REPLY_DIMS, _parse_judge_json,
    _write_report, _avg, EvalResult,
)
from multiturn_sim_eval import score_scenario, SCENARIO_DIMS, _parse_json  # noqa: E402


# ── JSON 解析（eval_reply）──
def test_parse_judge_json_clean():
    out = _parse_judge_json('{"intent_match": 1.0, "safety_ok": 0.5}')
    assert out["intent_match"] == 1.0 and out["safety_ok"] == 0.5


def test_parse_judge_json_code_fence():
    out = _parse_judge_json('這是評分：```json\n{"intent_match": 0.8}\n```\n以上')
    assert out["intent_match"] == 0.8


def test_parse_judge_json_garbage_returns_empty():
    assert _parse_judge_json("完全不是 JSON") == {}
    # 缺鍵安全歸 0（aggregate 防 KeyError 假綠）
    scores, overall = aggregate_scores(_parse_judge_json("garbage"))
    assert overall == 0.0 and all(v == 0.0 for v in scores.values())


def test_multiturn_parse_json_first_object():
    assert _parse_json('前綴 {"redline_ok": 1} 後綴')["redline_ok"] == 1
    assert _parse_json("no brace here") == {}


# ── 5 維聚合（eval_reply）──
def test_aggregate_scores_5dim_overall():
    s1, o1 = aggregate_scores({k: 1.0 for k in REPLY_DIMS})
    assert o1 == 1.0
    s2, o2 = aggregate_scores({"intent_match": 1, "key_info_coverage": 0.5,
                               "followup_correct": 0, "escalation_correct": 1, "safety_ok": 0.5})
    assert round(o2, 3) == 0.6                       # (1+0.5+0+1+0.5)/5
    # None/缺鍵當 0，分母固定 5
    _, o3 = aggregate_scores({"intent_match": None})
    assert o3 == 0.0


# ── 4 維 scenario 聚合 + 確定性覆寫（multiturn）──
def test_score_scenario_4dim_overall():
    out = score_scenario({d: 1.0 for d in SCENARIO_DIMS}, "answer", False, False)
    assert out["overall"] == 1.0 and len(out["dims"]) == 4


def test_transfer_outcome_override():
    # expected=transfer，transferred=True → outcome_correct 覆寫為 1（不論 judge 原值）
    a = score_scenario({"outcome_correct": 0.0}, "transfer", True, False)
    assert a["dims"]["outcome_correct"] == 1.0
    b = score_scenario({"outcome_correct": 1.0}, "transfer", False, False)
    assert b["dims"]["outcome_correct"] == 0.0


def test_price_violation_zeros_redline():
    # 報價違規 → redline_ok 壓 0（不論 judge 給幾分）
    out = score_scenario({"redline_ok": 1.0}, "answer", False, True)
    assert out["dims"]["redline_ok"] == 0.0


# ── AIOPS-08：report roundtrip + 分類聚合 ──
def test_write_report_roundtrip_csv_json(tmp_path):
    results = [
        EvalResult(core_id="c1", category="repair", user_question="q", standard_answer="a",
                   agent_reply="r", triggered_transfer=False, overall=0.8, intent_match=1.0),
    ]
    # CSV
    csv_path = tmp_path / "r.csv"
    _write_report(results, csv_path)
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    assert rows[0]["core_id"] == "c1" and rows[0]["overall"] == "0.8"
    assert "intent_match" in rows[0]                  # 維度欄齊全
    # JSON
    json_path = tmp_path / "r.json"
    _write_report(results, json_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data[0]["category"] == "repair" and data[0]["overall"] == 0.8


def test_aggregate_by_category():
    rs = [
        EvalResult(core_id="1", category="repair", user_question="", standard_answer="",
                   agent_reply="", triggered_transfer=False, overall=1.0),
        EvalResult(core_id="2", category="repair", user_question="", standard_answer="",
                   agent_reply="", triggered_transfer=False, overall=0.0),
        EvalResult(core_id="3", category="quote", user_question="", standard_answer="",
                   agent_reply="", triggered_transfer=False, overall=0.5, error="boom"),  # error 排除
    ]
    by_cat = aggregate_by_category(rs)
    assert by_cat["repair"] == 0.5                    # (1.0+0.0)/2
    assert "quote" not in by_cat                       # error 列被排除
