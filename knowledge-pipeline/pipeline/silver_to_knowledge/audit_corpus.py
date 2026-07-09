"""Step 2: 語料治理稽核 — 落地前品質 gate（最小評測 harness）。

檢查（任一違規 exit 1，可入 CI）：
  1. provenance 完整：facts/behavior 每 chunk 有 bronze_path + sha256
  2. 來源未漂移：bronze 檔存在且 sha256 相符
  3. 紅線：facts 語料內不得出現 gdrive 來源（quarantine 軌才准）
  4. 基本欄位：id/brand/model/category/text 非空
  5. id 唯一

用法：
  cd knowledge-pipeline && uv run python -m pipeline.silver_to_knowledge.audit_corpus
"""

import json
import sys
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


if __name__ == "__main__":
    raise SystemExit(main())
