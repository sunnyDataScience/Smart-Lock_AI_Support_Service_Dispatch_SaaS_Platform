"""Silver 文件載入工具。"""

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SILVER_DIR = ROOT_DIR / "storage" / "silver"
DRAFTS_DIR = ROOT_DIR / "storage" / "skill_drafts"

ALL_SOURCES = ["video", "youtube", "website", "gdrive", "line_chat", "problem_cards"]


def load_all_silver(source_filter: str = "") -> list[dict]:
    """載入所有 silver 文件為扁平 list。

    Args:
        source_filter: 若指定，只載入該 source（video/youtube/website/gdrive/line_chat/problem_cards）
    """
    sources = [source_filter] if source_filter else ALL_SOURCES
    docs = []
    for source in sources:
        source_dir = SILVER_DIR / source
        if not source_dir.exists():
            continue
        for f in sorted(source_dir.glob("*.json")):
            try:
                items = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(items, list):
                    for item in items:
                        item.setdefault("_source_file", f"{source}/{f.name}")
                    docs.extend(items)
                else:
                    items.setdefault("_source_file", f"{source}/{f.name}")
                    docs.append(items)
            except (json.JSONDecodeError, OSError) as e:
                print(f"[loader] skip {f.name}: {e}")
    return docs


def load_silver_by_file(source_filter: str = "") -> dict[str, list[dict]]:
    """載入 silver 文件，按來源檔案分群。

    Returns: {filename: [doc, doc, ...]}
    """
    sources = [source_filter] if source_filter else ALL_SOURCES
    grouped: dict[str, list[dict]] = {}
    for source in sources:
        source_dir = SILVER_DIR / source
        if not source_dir.exists():
            continue
        for f in sorted(source_dir.glob("*.json")):
            try:
                items = json.loads(f.read_text(encoding="utf-8"))
                key = f"{source}/{f.stem}"
                grouped[key] = items if isinstance(items, list) else [items]
            except (json.JSONDecodeError, OSError) as e:
                print(f"[loader] skip {f.name}: {e}")
    return grouped
