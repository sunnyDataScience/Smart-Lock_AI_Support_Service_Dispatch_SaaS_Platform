"""讀 status_snapshot.yaml 供 workbook 產生器渲染 derived 灰格。

刻意設計成「檔案不存在就整份空掉」—— 沒跑過 writeback.py 的環境仍要能
build 出四書，Plane 只是附加視圖，不是四書的前置依賴。
"""

from __future__ import annotations

from pathlib import Path

import yaml

SNAPSHOT = Path(__file__).resolve().parent / "status_snapshot.yaml"


class Snapshot:
    def __init__(self, path: Path = SNAPSHOT):
        raw: dict = {}
        if path.exists():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        self.available = bool(raw)
        self.source = raw.get("source") or {}
        self.coverage = raw.get("coverage") or {}
        axes = raw.get("axes") or {}
        self.spec = axes.get("axis1") or {}
        self.engineering = axes.get("axis2") or {}
        self.test_by_req = axes.get("axis3_req") or {}
        self.test_by_case = axes.get("axis3_case") or {}
        self.test_by_script = axes.get("axis3_script") or {}
        self.acceptance = axes.get("axis4") or {}

    # 每個取值器都回傳「人看得懂的一格文字」，缺值一律 "—"，不回傳 None。

    def acceptance_of(self, sc_id: str) -> str:
        return self.acceptance.get(sc_id) or "—"

    def engineering_of(self, wbs_id: str) -> str:
        return self.engineering.get(str(wbs_id)) or "—"

    def execution_of(self, tc_id: str) -> str:
        cell = self.test_by_case.get(tc_id)
        if not cell:
            return "—"
        return cell.get("latest_status") or "—"

    def req_execution_of(self, req_id: str) -> str:
        return self.test_by_req.get(req_id) or "—"

    def script_of(self, sc_id: str) -> str:
        cell = self.test_by_script.get(sc_id)
        if not cell:
            return "—"
        return f"{cell.get('run_status', '?')} {cell.get('progress', '')}".strip()

    def stamp(self) -> str:
        if not self.available:
            return "（尚未執行 _plane/writeback.py，Plane 欄位皆為 —）"
        return (f"Plane 快照 {self.source.get('generated_at', '?')}"
                f" @ {self.source.get('workspace', '?')}"
                f"　覆蓋 {self.coverage.get('covered', '?')}/{self.coverage.get('total', '?')}")
