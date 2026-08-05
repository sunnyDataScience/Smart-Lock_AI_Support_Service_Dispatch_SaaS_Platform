"""Step 2: 語料治理稽核 — 落地前品質 gate（最小評測 harness）。

檢查（任一違規 exit 1，可入 CI）：
  1. provenance 完整：facts/behavior 每 chunk 有 bronze_path + sha256
  2. 來源未漂移：bronze 檔存在且 sha256 相符
  3. 紅線：facts 語料內不得出現 gdrive 來源（quarantine 軌才准）
  4. 基本欄位：id/brand/model/category/text 非空
  5. id 唯一

稽核結論同時寫入 `storage/corpus/_audit.json`（run_at / passed / 全量 violations），
供事後追溯——CI log 會輪替，只印在 stdout 等於沒保留（NFR-Rep-002「保留稽核」）。

用法：
  cd knowledge-pipeline && uv run python -m pipeline.silver_to_knowledge.audit_corpus
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.silver_to_knowledge._provenance import ROOT_DIR, sha256_file  # noqa: E402

CORPUS_DIR = ROOT_DIR / "storage" / "corpus"


def _load(name: str) -> list[dict]:
    fp = CORPUS_DIR / name
    if not fp.exists():
        return []
    return [json.loads(line) for line in fp.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    violations: list[str] = []
    facts = _load("facts.jsonl")
    behavior = _load("behavior_candidates.jsonl")

    if not facts:
        violations.append("facts.jsonl 不存在或為空——先跑 emit_corpus")

    seen: set[str] = set()
    for track_name, records in (("facts", facts), ("behavior", behavior)):
        for c in records:
            cid = c.get("id", "?")
            where = f"{track_name}:{cid}"
            # 5. id 唯一
            if cid in seen:
                violations.append(f"{where} — 重複 id")
            seen.add(cid)
            # 4. 基本欄位
            for field in ("id", "brand", "model", "category", "text"):
                if not c.get(field):
                    violations.append(f"{where} — 缺欄位 {field}")
            # 3. 紅線：facts 不得含 gdrive
            if track_name == "facts" and c.get("source_type") == "gdrive":
                violations.append(f"{where} — 紅線違規：gdrive 內容進了 facts 語料")
            # 1./2. provenance 完整且未漂移
            prov = c.get("provenance") or {}
            bp, bs = prov.get("bronze_path"), prov.get("bronze_sha256")
            if not bp or not bs:
                violations.append(f"{where} — provenance 不完整（bronze_path/sha256 缺）")
                continue
            bronze = ROOT_DIR / bp
            if not bronze.exists():
                violations.append(f"{where} — bronze 檔不存在：{bp}")
            elif sha256_file(bronze) != bs:
                violations.append(f"{where} — bronze 內容已漂移（sha256 不符）：{bp}")

    # NFR-Rep-002「保存不足時明確阻擋並**保留稽核**」：結果落檔,不只印在 stdout。
    # 原本稽核結論只存在於當次終端輸出,CI log 輪替後就查不到「上一次跑是什麼時候、
    # 過了沒、違規哪幾項」——追溯鏈缺一環。exit code 行為完全不變(此處只多寫一個檔)。
    _write_audit_report(violations, facts_count=len(facts), behavior_count=len(behavior))

    if violations:
        print(f"❌ 稽核失敗（{len(violations)} 項違規）：")
        for v in violations[:30]:
            print(f"  - {v}")
        if len(violations) > 30:
            print(f"  ...（其餘 {len(violations) - 30} 項省略）")
        return 1

    print(f"✅ 稽核通過：facts={len(facts)} behavior={len(behavior)}，"
          f"provenance 完整、bronze 未漂移、紅線無違規")
    return 0


def _write_audit_report(violations: list[str], *, facts_count: int, behavior_count: int) -> None:
    """把稽核結論寫成 storage/corpus/_audit.json（best-effort,寫檔失敗不影響 gate）。

    violations 全量保留（不像 stdout 只印前 30 項）——事後追溯時要看得到全部。
    """
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "passed": not violations,
        "facts_count": facts_count,
        "behavior_count": behavior_count,
        "violation_count": len(violations),
        "violations": violations,
    }
    try:
        CORPUS_DIR.mkdir(parents=True, exist_ok=True)
        (CORPUS_DIR / "_audit.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:  # 寫不進去也不該讓品質 gate 的判定失真
        print(f"⚠️  稽核報告寫檔失敗（不影響判定）：{exc}")


if __name__ == "__main__":
    raise SystemExit(main())
