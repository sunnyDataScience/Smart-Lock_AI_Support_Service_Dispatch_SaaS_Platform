"""AI 治理檢查 helpers（CR-0076）。

- scan_references_sourcing（TI-A04-02 / bronze-only 紅線）：掃 product-knowledge references
  內所有 URL，驗證 bronze 可溯來源；GDrive 連結必須在 bronze/gdrive/{file_id}.json 為
  link-only（僅 file_id/title/url，無正文）—— 落實「PDF (GDrive) 不可信，references 只引
  URL 不抄內容」。
- compute_agent_kpi_gate（TI-A03-03）：Agent KPI gate 純門檻邏輯（指標值由 live eval 另外
  蒐集；本函式只做 pass/fail 判定，可單元測）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_URL_RE = re.compile(r"https?://[^\s)\]}\"'>]+")
_GDRIVE_FILE_RE = re.compile(r"drive\.google\.com/file/d/([A-Za-z0-9_\-]+)")
# bronze/gdrive JSON 合法鍵集（link-only，無正文）
_GDRIVE_LINK_ONLY_KEYS = {"file_id", "title", "url"}


def _classify_url(url: str) -> str:
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if "drive.google.com" in url:
        return "gdrive"
    if "lin.ee" in url or "line.me" in url:
        return "line"
    return "website"


def scan_references_sourcing(references_dir: str | Path, bronze_dir: str | Path) -> dict:
    """掃 references *.md 內 URL，驗 bronze 可溯 + GDrive link-only。

    回 {scanned_files, total_urls, by_kind, violations}。
    violation kinds：
      - gdrive_bronze_missing：GDrive URL 對應的 bronze/gdrive/{file_id}.json 不存在
      - gdrive_not_link_only：bronze/gdrive JSON 含正文（超出 {file_id,title,url}）= 抄錄嫌疑
    """
    references_dir = Path(references_dir)
    bronze_gdrive = Path(bronze_dir) / "gdrive"
    md_files = sorted(references_dir.rglob("*.md"))
    by_kind: dict[str, int] = {}
    violations: list[dict] = []
    total = 0
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        for raw in _URL_RE.findall(text):
            url = raw.rstrip(".,;)")
            total += 1
            kind = _classify_url(url)
            by_kind[kind] = by_kind.get(kind, 0) + 1
            if kind == "gdrive":
                m = _GDRIVE_FILE_RE.search(url)
                if not m:
                    continue
                fid = m.group(1)
                bjson = bronze_gdrive / f"{fid}.json"
                if not bjson.exists():
                    violations.append({"kind": "gdrive_bronze_missing", "file": str(md.name),
                                       "url": url, "file_id": fid})
                    continue
                try:
                    data = json.loads(bjson.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    violations.append({"kind": "gdrive_bronze_unreadable", "file": str(md.name),
                                       "file_id": fid})
                    continue
                extra = set(data.keys()) - _GDRIVE_LINK_ONLY_KEYS
                if extra:
                    violations.append({"kind": "gdrive_not_link_only", "file_id": fid,
                                       "extra_keys": sorted(extra)})
    return {"scanned_files": len(md_files), "total_urls": total,
            "by_kind": by_kind, "violations": violations}


# ── A03-03 KPI gate 門檻 ──
KPI_THRESHOLDS = {
    "auto_resolve_rate": 0.70,     # ≥ 0.70
    "eval_pass_rate": 0.85,        # ≥ 0.85
    "escalation_correct_rate": 0.95,  # ≥ 0.95
    "latency_p95_ms": 8000,        # ≤ 8000
}


def compute_agent_kpi_gate(
    *, auto_resolve_rate: float, eval_pass_rate: float,
    escalation_correct_rate: float, latency_p95_ms: float,
) -> dict:
    """TI-A03-03：四指標 vs 門檻 → pass/fail + 各 breach。指標值由 live eval 蒐集。"""
    breaches: dict[str, bool] = {
        "auto_resolve_rate": auto_resolve_rate < KPI_THRESHOLDS["auto_resolve_rate"],
        "eval_pass_rate": eval_pass_rate < KPI_THRESHOLDS["eval_pass_rate"],
        "escalation_correct_rate": escalation_correct_rate < KPI_THRESHOLDS["escalation_correct_rate"],
        "latency_p95_ms": latency_p95_ms > KPI_THRESHOLDS["latency_p95_ms"],
    }
    return {"passed": not any(breaches.values()), "breaches": breaches,
            "thresholds": dict(KPI_THRESHOLDS)}
