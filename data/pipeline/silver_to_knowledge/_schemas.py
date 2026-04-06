"""JSON response schemas for Gemini structured output."""

EXTRACT_SYMPTOMS_SCHEMA = {
    "type": "object",
    "properties": {
        "new_symptoms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "proposed_id": {"type": "string"},
                    "label": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "component": {"type": "string"},
                    "severity": {"type": "integer"},
                    "category": {"type": "string"},
                    "source_evidence": {"type": "string"},
                },
                "required": ["proposed_id", "label", "aliases", "component", "severity", "category", "source_evidence"],
            },
        },
        "alias_enrichments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "existing_symptom_id": {"type": "string"},
                    "new_aliases": {"type": "array", "items": {"type": "string"}},
                    "source_evidence": {"type": "string"},
                },
                "required": ["existing_symptom_id", "new_aliases", "source_evidence"],
            },
        },
    },
    "required": ["new_symptoms", "alias_enrichments"],
}


ENRICH_FAULT_TREE_SCHEMA = {
    "type": "object",
    "properties": {
        "new_verification_steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "order": {"type": "integer"},
                    "method": {"type": "string"},
                    "question": {"type": "string"},
                    "if_yes": {"type": "string"},
                    "if_no": {"type": "string"},
                    "cost": {"type": "string"},
                    "confidence_gain": {"type": "number"},
                    "source": {"type": "string"},
                },
                "required": ["order", "method", "question", "if_yes", "if_no", "cost", "confidence_gain"],
            },
        },
        "new_corrective_actions": {
            "type": "object",
            "properties": {
                "immediate_remote": {"type": "string"},
                "long_term_remote": {"type": "string"},
                "if_remote_fails": {"type": "string"},
                "dispatch_criteria": {"type": "array", "items": {"type": "string"}},
            },
        },
        "new_defect_hypotheses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fm_id": {"type": "string"},
                    "defect": {"type": "string"},
                    "type": {"type": "string"},
                    "probability": {"type": "number"},
                    "source": {"type": "string"},
                },
                "required": ["fm_id", "defect", "type", "probability"],
            },
        },
    },
    "required": ["new_verification_steps", "new_corrective_actions", "new_defect_hypotheses"],
}


GENERATE_FAULT_TREE_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "version": {"type": "string"},
        "updated_by": {"type": "string"},
        "required_symptoms": {"type": "array", "items": {"type": "string"}},
        "optional_symptoms": {"type": "array", "items": {"type": "string"}},
        "related_failures": {"type": "array", "items": {"type": "string"}},
        "failure_modes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fm_id": {"type": "string"},
                    "name": {"type": "string"},
                    "mechanism_type": {"type": "string"},
                    "defect_hypotheses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "defect": {"type": "string"},
                                "type": {"type": "string"},
                                "probability": {"type": "number"},
                                "source": {"type": "string"},
                            },
                            "required": ["defect", "type", "probability"],
                        },
                    },
                },
                "required": ["fm_id", "name", "mechanism_type", "defect_hypotheses"],
            },
        },
        "verification_chain": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "order": {"type": "integer"},
                    "method": {"type": "string"},
                    "question": {"type": "string"},
                    "if_yes": {"type": "string"},
                    "if_no": {"type": "string"},
                    "cost": {"type": "string"},
                    "confidence_gain": {"type": "number"},
                },
                "required": ["order", "method", "question", "if_yes", "if_no", "cost", "confidence_gain"],
            },
        },
        "corrective_actions": {
            "type": "object",
            "properties": {
                "immediate_remote": {"type": "string"},
                "long_term_remote": {"type": "string"},
                "if_remote_fails": {"type": "string"},
                "dispatch_criteria": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["immediate_remote", "long_term_remote", "if_remote_fails", "dispatch_criteria"],
        },
    },
    "required": ["id", "title", "required_symptoms", "related_failures", "failure_modes",
                  "verification_chain", "corrective_actions"],
}


VALIDATE_COVERAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "matched_symptoms": {"type": "array", "items": {"type": "string"}},
        "matched_failures": {"type": "array", "items": {"type": "string"}},
        "relevance_type": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["matched_symptoms", "matched_failures", "relevance_type", "confidence"],
}
