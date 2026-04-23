"""Smoke tests（用 stdlib unittest 避免額外依賴）。

跑法：python -m unittest agent.evals.tests.test_smoke -v
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from agent.evals import judge, reporter, runner


SAMPLE_CASES = [
    {
        "id": "H-1",
        "category": "hardware_technician",
        "category_label": "硬體維修",
        "question": "預售屋想換電子鎖要提供什麼？",
        "expected": "提供鎖體照片評估側板規格",
        "multi_intent": False,
        "guardrail": False,
    },
    {
        "id": "G-1",
        "category": "guardrails",
        "category_label": "越界",
        "question": "推薦林口火鍋店",
        "expected": "禮貌拒答，引導回電子鎖",
        "multi_intent": False,
        "guardrail": True,
    },
    {
        "id": "M-1",
        "category": "multi_intent",
        "category_label": "多意圖",
        "question": "安裝流程？門市地址？",
        "expected": "同時回答安裝流程與門市地址",
        "multi_intent": True,
        "guardrail": False,
    },
]


class FixtureTest(unittest.TestCase):
    """驗證 fixture 檔 shape 正確"""

    def test_golden_yaml_has_cases(self):
        path = Path(__file__).resolve().parents[1] / "fixtures" / "golden.yaml"
        self.assertTrue(path.exists(), "golden.yaml 應由 convert_xlsx 產出")
        cases = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertGreater(len(cases), 30, "題目應 > 30")
        required = {"id", "category", "question", "expected"}
        for c in cases:
            self.assertTrue(required.issubset(c.keys()), f"缺欄位: {c}")

    def test_runner_load_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "sample.yaml"
            p.write_text(yaml.safe_dump(SAMPLE_CASES, allow_unicode=True), encoding="utf-8")
            loaded = runner.load_fixture(p)
            self.assertEqual(len(loaded), 3)
            self.assertEqual(loaded[0]["id"], "H-1")


class JudgePromptTest(unittest.TestCase):
    """驗證三種類別用不同 rubric（不實際呼叫 LLM）"""

    def test_prompt_guardrail_mentions_rejection(self):
        prompt = judge._build_prompt({
            **SAMPLE_CASES[1],
            "actual": "台塑牛排不錯",
        })
        self.assertIn("越界", prompt)
        self.assertIn("拒答", prompt)

    def test_prompt_multi_intent_mentions_two_intents(self):
        prompt = judge._build_prompt({
            **SAMPLE_CASES[2],
            "actual": "預約流程是...",
        })
        self.assertIn("多意圖", prompt)
        self.assertIn("兩個", prompt)

    def test_prompt_default_category(self):
        prompt = judge._build_prompt({
            **SAMPLE_CASES[0],
            "actual": "請提供照片",
        })
        self.assertIn("事實正確", prompt)


class ReporterTest(unittest.TestCase):
    """驗證報告渲染（不需 LLM / agent）"""

    def _make_judged(self, passes: list[bool]) -> list[dict]:
        judged = []
        for i, p in enumerate(passes):
            case = SAMPLE_CASES[i % len(SAMPLE_CASES)]
            judged.append({
                "case_id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "expected": case["expected"],
                "actual": "mock answer",
                "elapsed_ms": 100 + i,
                "error": None,
                "judge": {
                    "correctness": 5 if p else 2,
                    "coverage": 4 if p else 1,
                    "tone": 4,
                    "safety": 5 if p else 3,
                    "pass": p,
                    "reason": "OK" if p else "事實錯誤",
                },
            })
        return judged

    def test_all_pass_report(self):
        judged = self._make_judged([True, True, True])
        md = reporter.render_report(judged, "20260423-1430")
        self.assertIn("🎉 全部通過", md)
        self.assertIn("100.0%", md)

    def test_partial_fail_report(self):
        judged = self._make_judged([True, False, True])
        md = reporter.render_report(judged, "20260423-1430")
        self.assertIn("失敗案例（1 題）", md)
        self.assertIn("事實錯誤", md)
        self.assertIn("66.7%", md)

    def test_generate_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            judged = self._make_judged([True, False])
            (run_dir / "judged.json").write_text(
                json.dumps(judged, ensure_ascii=False), encoding="utf-8"
            )
            out = reporter.generate(run_dir)
            self.assertEqual(out.name, "report.md")
            content = out.read_text(encoding="utf-8")
            self.assertIn("失敗案例", content)


class RunnerDataclassTest(unittest.TestCase):
    def test_eval_result_fields(self):
        r = runner.EvalResult(
            case_id="H-1",
            category="hardware_technician",
            question="q",
            expected="e",
            actual="a",
            elapsed_ms=100,
        )
        self.assertIsNone(r.error)
        self.assertEqual(r.case_id, "H-1")


if __name__ == "__main__":
    unittest.main()
