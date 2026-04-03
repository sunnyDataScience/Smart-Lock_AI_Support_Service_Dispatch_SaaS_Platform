# Knowledge Assets

Diagnostic intelligence knowledge base, stored as JSON files for Phase 0-1 rapid iteration.

## Directory Structure

```
knowledge/
├── failures/
│   └── failure_taxonomy.json          # Layer 2: Standardized failure definitions
├── failure_modes/
│   └── failure_mode_registry.json     # Layer 3: All known failure modes (fm_id registry)
├── fault_trees/
│   └── FT-HW-003.json                # Layer 3+5: FM hypotheses + verification chains
├── sop/
│   └── SOP-HW-001.json               # Workflow step sequences
├── ocap_rules.json                    # L8 Entropy: Out of Control Action Plan rules
└── README.md
```

## ID Reference Chain

```
symptoms.toml          → symptom_id    (e.g. fingerprint_no_response)
failure_taxonomy.json  → failure_id    (e.g. F-LOCK-001)
failure_mode_registry  → fm_id         (e.g. FM-ELEC-002)
fault_trees/*.json     → references all three above
components.toml        → component_id  (e.g. fingerprint_module)
```

All IDs are defined in their registry first, then referenced by other files. Never invent an ID inline.

## Design Rationale

- **JSON files** (not PostgreSQL): Phase 0-1 has 20-50 fault trees, 10 SOPs. Python `json.load()` + in-memory matching is sufficient.
- **Git versioned**: Every change is tracked. Expert edits are reviewable via PR.
- **Load + inject**: Same pattern as `load_prompt_template()` — read file, inject into LLM prompt.
- **Migration path**: When case_library exceeds 500 entries or concurrent writes are needed, migrate to PostgreSQL. Schema matches JSON structure 1:1.

## Matching Logic

```python
# Fault tree matching: set operation in Python
for ft in fault_trees:
    if set(ft["required_symptoms"]) <= set(user_symptoms):
        matches.append(ft)
matches.sort(key=lambda ft: len(ft["required_symptoms"]), reverse=True)
```

## Adding New Knowledge

1. Create a new `.json` file in the appropriate directory
2. Follow the existing file format (see examples)
3. Commit via Git (expert review via PR)
4. System picks up on next load (or hot-reload if configured)
