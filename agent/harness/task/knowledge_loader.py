"""KnowledgeLoader — Software 3.0 knowledge asset loader.

Loads structured knowledge files (JSON/TOML) and serializes them
for injection into LLM diagnostic reasoning prompts.

Python does: load + filter + serialize + validate.
LLM does:    all diagnostic reasoning within the prompt context.
"""

import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]


class KnowledgeLoader:
    """Load knowledge files once, provide serialization for prompt injection."""

    def __init__(self, base_dir: str | Path):
        self.base = Path(base_dir)
        self._fault_trees = self._load_all_json("knowledge/fault_trees")
        self._sop = self._load_all_json("knowledge/sop")
        self._failures = self._load_json("knowledge/failures/failure_taxonomy.json")
        self._fm_registry = self._load_json("knowledge/failure_modes/failure_mode_registry.json")
        self._symptoms = self._load_toml("taxonomy/symptoms.toml")
        self._components = self._load_toml("taxonomy/components.toml")

        # Build symptom ID set for validation
        self._valid_symptom_ids: set[str] = set(self._symptoms.get("symptoms", {}).keys())

    # ── Internal loaders ──

    def _load_all_json(self, subdir: str) -> list[dict]:
        path = self.base / subdir
        if not path.exists():
            return []
        files = sorted(path.glob("*.json"))
        result = []
        for f in files:
            try:
                result.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError) as e:
                print(f"[KnowledgeLoader] skip {f.name}: {e}")
        return result

    def _load_json(self, path: str) -> dict:
        full = self.base / path
        if not full.exists():
            return {}
        return json.loads(full.read_text(encoding="utf-8"))

    def _load_toml(self, path: str) -> dict:
        full = self.base / path
        if not full.exists():
            return {}
        with open(full, "rb") as f:
            return tomllib.load(f)

    # ── Tier 1: Always injected (~3700 tokens) ──

    def get_symptom_taxonomy(self) -> str:
        """Serialize symptoms.toml for prompt injection.

        Returns a readable list of symptom IDs with aliases and components.
        """
        symptoms = self._symptoms.get("symptoms", {})
        if not symptoms:
            return "(no symptom taxonomy loaded)"
        lines = []
        for sid, data in symptoms.items():
            aliases = ", ".join(data.get("aliases", []))
            comp = data.get("component", "?")
            sev = data.get("severity", "?")
            lines.append(f"- {sid} [{comp}, {sev}]: {data.get('label', sid)} | aliases: {aliases}")
        return "\n".join(lines)

    def get_failure_context(self) -> str:
        """Serialize failure taxonomy + FM registry for prompt injection."""
        return json.dumps(
            {
                "failures": self._failures.get("failures", []),
                "failure_modes": self._fm_registry.get("failure_modes", []),
            },
            ensure_ascii=False,
            indent=2,
        )

    def get_component_graph(self) -> str:
        """Serialize component topology for prompt injection."""
        components = self._components.get("components", {})
        if not components:
            return "(no component graph loaded)"
        lines = []
        for cid, data in components.items():
            parts = [f"{cid} ({data.get('label', cid)}, {data.get('type', '?')})"]
            if ct := data.get("connects_to"):
                parts.append(f"connects_to: {ct}")
            if po := data.get("part_of"):
                parts.append(f"part_of: {po}")
            if pb := data.get("powered_by"):
                parts.append(f"powered_by: {pb}")
            if sf := data.get("shared_fault"):
                parts.append(f"shared_fault: {sf}")
            lines.append("  ".join(parts))
        return "\n".join(lines)

    # ── Tier 2: Filtered by relevance (~1500-3000 tokens) ──

    def get_relevant_fault_trees(self, symptom_ids: list[str]) -> str:
        """Lightweight relevance filter — NOT diagnostic reasoning.

        Python checks 'any overlap?', LLM decides 'which actually matches?'.
        """
        if not symptom_ids:
            return "[]"
        symptom_set = set(symptom_ids)
        relevant = [
            ft
            for ft in self._fault_trees
            if any(
                s in symptom_set
                for s in ft.get("required_symptoms", []) + ft.get("optional_symptoms", [])
            )
        ]
        return json.dumps(relevant, ensure_ascii=False, indent=2) if relevant else "[]"

    def get_sop(self, category: str) -> str:
        """Dict lookup by category. Returns serialized JSON."""
        for sop in self._sop:
            if sop.get("category") == category:
                return json.dumps(sop, ensure_ascii=False, indent=2)
        return "{}"

    # ── Validation (post-LLM output) ──

    def validate_symptom_ids(self, ids: list[str]) -> list[str]:
        """Keep only symptom IDs that exist in taxonomy. 3-line safety check."""
        return [s for s in ids if s in self._valid_symptom_ids]

    # ── Metadata ──

    @property
    def fault_tree_count(self) -> int:
        return len(self._fault_trees)

    @property
    def symptom_count(self) -> int:
        return len(self._valid_symptom_ids)

    @property
    def failure_mode_count(self) -> int:
        return len(self._fm_registry.get("failure_modes", []))
