"""K3' 負面情緒識別 eval gate（合約 4.4(a)，≥90%）——CR-0166 R2。

對 evals/sentiment_corpus.json 逐題跑 classify_sentiment，判定「是否為負面」的
二元準確率（negative/very_negative → 負面；neutral/positive → 非負面）。反諷類
單獨統計（K3 最難類）。≥90% 通過。

用法（需 Vertex 憑證 / config model=vertex_ai/）：
    cd agent && uv run python scripts/sentiment_eval.py
    uv run python scripts/sentiment_eval.py --dry   # 只驗 corpus 結構，不打 LLM
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lockcore.agent.sentiment import classify_sentiment  # noqa: E402
from lockcore.app_config import build_provider, load_config  # noqa: E402

CORPUS = ROOT / "evals" / "sentiment_corpus.json"
THRESHOLD = 0.90
_NEG = {"very_negative", "negative"}


def _load() -> list[dict]:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    return data["cases"] if isinstance(data, dict) else data


def _validate(cases: list[dict]) -> list[str]:
    errs = []
    if len(cases) < 100:
        errs.append(f"corpus 題數 {len(cases)} < 100")
    labels = {"very_negative", "negative", "neutral", "positive"}
    for i, c in enumerate(cases):
        if not c.get("text"):
            errs.append(f"case[{i}] 缺 text")
        if c.get("label") not in labels:
            errs.append(f"case[{i}] label 非法：{c.get('label')}")
    neg = sum(1 for c in cases if c.get("label") in _NEG)
    if neg < 90:
        errs.append(f"負面題數 {neg} < 90（K3 需 100 負面含 20 反諷）")
    return errs


def _dry() -> int:
    cases = _load()
    errs = _validate(cases)
    if errs:
        print("❌ corpus 結構驗證失敗：")
        for e in errs:
            print("  -", e)
        return 1
    print(f"✅ dry：corpus {len(cases)} 題結構完整（負面 "
          f"{sum(1 for c in cases if c['label'] in _NEG)}）")
    return 0


async def _live() -> int:
    cases = _load()
    errs = _validate(cases)
    if errs:
        print("❌ corpus 結構驗證失敗：", errs)
        return 1
    cfg = load_config(None)
    provider = build_provider(cfg)

    correct = 0
    sarcasm_total = sarcasm_correct = 0
    fails = []
    for c in cases:
        exp_neg = c["label"] in _NEG
        res = await classify_sentiment(provider, c["text"], model=cfg.model)
        ok = res.is_negative == exp_neg
        correct += ok
        is_sarcasm = "反諷" in (c.get("note") or "") or c.get("group") == "sarcasm"
        if is_sarcasm:
            sarcasm_total += 1
            sarcasm_correct += ok
        if not ok:
            fails.append({"text": c["text"][:40], "expected": c["label"],
                          "got": res.label, "conf": res.confidence})

    acc = correct / len(cases) if cases else 0.0
    print(f"\nK3' 負面情緒 eval — model={cfg.model}  ({len(cases)} 題)")
    print(f"  二元準確率（負面 vs 非負面）: {acc:.2%}  threshold={THRESHOLD:.0%}")
    if sarcasm_total:
        print(f"  反諷類（最難）: {sarcasm_correct}/{sarcasm_total} = "
              f"{sarcasm_correct / sarcasm_total:.2%}")
    if fails:
        print(f"  誤判 {len(fails)} 題（前 10）:")
        for f in fails[:10]:
            print(f"    「{f['text']}」expected={f['expected']} got={f['got']} ({f['conf']})")
    passed = acc >= THRESHOLD
    print(f"\n{'✅ K3 GATE 通過' if passed else '❌ K3 GATE 未過'}：{acc:.2%}")
    (CORPUS.parent / "sentiment_eval_result.json").write_text(
        json.dumps({"accuracy": acc, "passed": passed, "total": len(cases),
                    "sarcasm_acc": (sarcasm_correct / sarcasm_total) if sarcasm_total else None,
                    "fails": fails}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return 0 if passed else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry", action="store_true", help="只驗 corpus 結構，不打 LLM")
    args = ap.parse_args()
    return _dry() if args.dry else asyncio.run(_live())


if __name__ == "__main__":
    raise SystemExit(main())
