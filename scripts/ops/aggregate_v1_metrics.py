"""P4 Cutover — aggregate 30 day v1 metrics snapshots → 判斷 Stage 7 ready。

對齊：
  - scripts/ops/snapshot_v1_metrics.py (hourly snapshot)
  - docs/_audit/P4-stage-2-7-prep-checklists.md Stage 7 條件
  - 業主待裁決事項 1 P4 Stage 7 v1 router 刪除

從 720 hourly snapshot (30 day × 24h) aggregate 出：
  - 每 v1 endpoint 總 hit count
  - 連續 0 hit 的天數 / 小時數
  - 30 day 真 0 traffic 候選 (Stage 7 安全刪除集)
  - 仍有 traffic 的 endpoint (保留候選)

輸出 markdown report 給業主 review + Stage 7 簽核參考。

Usage:
    uv run python scripts/ops/aggregate_v1_metrics.py \
        --input-dir ./snapshots/v1-metrics \
        --output reports/p4-stage7-readiness.md \
        --window-days 30
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


def load_snapshots(input_dir: Path, since: datetime) -> list[dict]:
    """Load all snapshots in input_dir captured >= since."""
    snapshots = []
    if not input_dir.exists():
        return snapshots
    for day_dir in sorted(input_dir.iterdir()):
        if not day_dir.is_dir():
            continue
        for snap_file in sorted(day_dir.glob("*.json")):
            try:
                with open(snap_file) as f:
                    snap = json.load(f)
                captured = datetime.fromtimestamp(
                    snap.get("captured_at_epoch", 0), tz=timezone.utc,
                )
                if captured >= since:
                    snapshots.append(snap)
            except Exception:  # noqa: BLE001
                continue
    return snapshots


def aggregate(snapshots: list[dict]) -> dict:
    """Aggregate snapshots → per-endpoint stats."""
    endpoint_stats: dict = defaultdict(lambda: {
        "total_hits": 0,
        "max_hourly_hits": 0,
        "snapshots_with_traffic": 0,
        "snapshots_zero": 0,
        "first_seen": None,
        "last_seen": None,
    })

    inventory_seen: set = set()

    for snap in snapshots:
        ts = snap.get("captured_at_epoch", 0)
        metrics_ep = snap.get("endpoints", {}).get("v1_metrics", {})
        if metrics_ep.get("status", 500) >= 400:
            continue
        data = metrics_ep.get("data", {}) or {}
        items = data.get("items", [])

        # also gather inventory
        inv = snap.get("endpoints", {}).get("v1_inventory", {}).get("data", {}) or {}
        for ep in inv.get("items", []):
            inventory_seen.add(ep.get("path") + " " + ep.get("method", ""))

        seen_this_snapshot = set()
        for item in items:
            key = f"{item.get('method', '')} {item.get('path', '')}"
            count = item.get("count", 0)
            stats = endpoint_stats[key]
            stats["total_hits"] += count
            if count > stats["max_hourly_hits"]:
                stats["max_hourly_hits"] = count
            if count > 0:
                stats["snapshots_with_traffic"] += 1
            if stats["first_seen"] is None or ts < stats["first_seen"]:
                stats["first_seen"] = ts
            if stats["last_seen"] is None or ts > stats["last_seen"]:
                stats["last_seen"] = ts
            seen_this_snapshot.add(key)

        # Mounted endpoints with 0 in this snapshot
        for inv_key in inventory_seen:
            if inv_key not in seen_this_snapshot and inv_key in endpoint_stats:
                endpoint_stats[inv_key]["snapshots_zero"] += 1

    return {
        "total_snapshots": len(snapshots),
        "inventory_total": len(inventory_seen),
        "endpoint_stats": dict(endpoint_stats),
    }


def classify_for_stage7(agg: dict) -> tuple[list, list]:
    """Split into safe-to-delete vs keep-watching."""
    safe: list = []
    keep: list = []
    for key, stats in agg["endpoint_stats"].items():
        if stats["total_hits"] == 0:
            safe.append((key, stats))
        else:
            keep.append((key, stats))
    safe.sort(key=lambda x: x[0])
    keep.sort(key=lambda x: x[1]["total_hits"], reverse=True)
    return safe, keep


def render_report(agg: dict, window_days: int) -> str:
    safe, keep = classify_for_stage7(agg)
    total = len(agg["endpoint_stats"])

    lines = [
        "# P4 Stage 7 — v1 Router 刪除 Readiness Report",
        "",
        f"Window: 過去 {window_days} 天",
        f"Total snapshots loaded: {agg['total_snapshots']}",
        f"Total v1 endpoints (inventory union): {agg['inventory_total']}",
        f"Endpoints with stats: {total}",
        "",
        "## §1 安全可刪除 (Stage 7 候選) — 真 0 traffic",
        "",
    ]
    if not safe:
        lines.append("_(無 0 traffic 候選 — 全部仍有流量)_")
    else:
        lines.append("| Endpoint | total_hits | snapshots_zero | first→last |")
        lines.append("|---|---:|---:|---|")
        for key, stats in safe:
            first = (
                datetime.fromtimestamp(stats["first_seen"], tz=timezone.utc).strftime("%Y-%m-%d")
                if stats["first_seen"] else "-"
            )
            last = (
                datetime.fromtimestamp(stats["last_seen"], tz=timezone.utc).strftime("%Y-%m-%d")
                if stats["last_seen"] else "-"
            )
            lines.append(
                f"| `{key}` | 0 | {stats['snapshots_zero']} | {first} → {last} |"
            )

    lines.append("")
    lines.append("## §2 仍有流量 — 保留 / 延期觀察候選")
    lines.append("")
    if not keep:
        lines.append("_(全部 endpoint 已 0 traffic — Stage 7 全綠！)_")
    else:
        lines.append("| Endpoint | total_hits | max_hourly | snapshots_with_traffic |")
        lines.append("|---|---:|---:|---:|")
        for key, stats in keep:
            lines.append(
                f"| `{key}` | {stats['total_hits']} | "
                f"{stats['max_hourly_hits']} | "
                f"{stats['snapshots_with_traffic']} |"
            )

    lines.append("")
    lines.append("## §3 Stage 7 建議")
    lines.append("")
    if not keep and safe:
        lines.append("✅ **全 v1 endpoints 0 traffic** — 建議業主簽 Stage 7，整批刪 v1 router。")
    elif keep and not safe:
        lines.append("❌ **全 endpoint 仍有流量** — 延期 Stage 7，繼續觀察 + 找 caller。")
    else:
        lines.append(
            f"⚠️ **混合狀態** — {len(safe)} 個 0 traffic 可刪 / {len(keep)} 個仍有流量。"
            "建議: 階段性刪除 (先刪 §1 安全集), 對 §2 繼續觀察至少 30 day。"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", default="./snapshots/v1-metrics",
                        type=Path)
    parser.add_argument("--output", default=None)
    parser.add_argument("--window-days", type=int, default=30)
    args = parser.parse_args()

    since = datetime.now(timezone.utc) - timedelta(days=args.window_days)
    snapshots = load_snapshots(args.input_dir, since)
    if not snapshots:
        print(f"[warn] no snapshots loaded from {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    agg = aggregate(snapshots)
    report = render_report(agg, args.window_days)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            f.write(report)
        print(f"[ok] report → {out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
