"""Shared loading utilities for silver_to_knowledge pipeline."""

import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


ROOT_DIR = Path(__file__).resolve().parents[2]
SILVER_DIR = ROOT_DIR / "storage" / "silver"
AGENT_DIR = ROOT_DIR.parent / "agent"
KNOWLEDGE_DIR = AGENT_DIR / "harness" / "task"
DRAFTS_DIR = ROOT_DIR / "storage" / "knowledge_drafts"


def load_all_silver(source_filter: str = "") -> list[dict]:
    """Load all silver documents as a flat list.

    Args:
        source_filter: if set, only load from this source (video/youtube/website/gdrive)
    """
    sources = [source_filter] if source_filter else ["video", "youtube", "website", "gdrive"]
    docs = []
    for source in sources:
        source_dir = SILVER_DIR / source
        if not source_dir.exists():
            continue
        for f in sorted(source_dir.glob("*.json")):
            try:
                items = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(items, list):
                    docs.extend(items)
                else:
                    docs.append(items)
            except (json.JSONDecodeError, OSError) as e:
                print(f"[loader] skip {f.name}: {e}")
    return docs


def load_silver_by_file(source_filter: str = "") -> dict[str, list[dict]]:
    """Load silver documents grouped by source file (for batched LLM calls).

    Returns: {filename: [doc, doc, ...]}
    """
    sources = [source_filter] if source_filter else ["video", "youtube", "website", "gdrive"]
    grouped = {}
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


def load_symptoms_toml() -> tuple[dict, set]:
    """Load symptoms.toml and return (symptom_dict, alias_set).

    Returns:
        symptom_dict: {symptom_id: {label, aliases, component, severity, category}}
        alias_set: flat set of all known alias strings (for deduplication)
    """
    path = KNOWLEDGE_DIR / "taxonomy" / "symptoms.toml"
    if not path.exists():
        return {}, set()
    with open(path, "rb") as f:
        data = tomllib.load(f)
    symptoms = data.get("symptoms", {})
    alias_set = set()
    for sid, info in symptoms.items():
        alias_set.add(info.get("label", ""))
        for alias in info.get("aliases", []):
            alias_set.add(alias)
    return symptoms, alias_set


def load_failures() -> list[dict]:
    """Load failure_taxonomy.json → list of 7 failures."""
    path = KNOWLEDGE_DIR / "knowledge" / "failures" / "failure_taxonomy.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("failures", [])


def load_failure_modes() -> list[dict]:
    """Load failure_mode_registry.json → list of 13+ failure modes."""
    path = KNOWLEDGE_DIR / "knowledge" / "failure_modes" / "failure_mode_registry.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("failure_modes", [])


def load_fault_trees() -> list[dict]:
    """Load all FT-HW-*.json fault trees."""
    ft_dir = KNOWLEDGE_DIR / "knowledge" / "fault_trees"
    if not ft_dir.exists():
        return []
    trees = []
    for f in sorted(ft_dir.glob("FT-HW-*.json")):
        try:
            trees.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as e:
            print(f"[loader] skip {f.name}: {e}")
    return trees


def get_valid_ids() -> tuple[set, set]:
    """Return (valid_symptom_ids, valid_fm_ids) for output validation."""
    symptoms, _ = load_symptoms_toml()
    fms = load_failure_modes()
    symptom_ids = set(symptoms.keys())
    fm_ids = {fm["id"] for fm in fms}
    return symptom_ids, fm_ids


def serialize_symptoms_for_prompt(symptoms: dict) -> str:
    """Serialize symptoms.toml into a compact format for LLM context."""
    lines = []
    for sid, info in symptoms.items():
        aliases = ", ".join(info.get("aliases", []))
        lines.append(f"- {sid}: {info.get('label', sid)} | aliases: [{aliases}] | "
                     f"component: {info.get('component', '?')} | severity: {info.get('severity', '?')}")
    return "\n".join(lines)
