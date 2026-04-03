"""Shared fixtures for all test levels."""

import sys
from pathlib import Path

import pytest

# Ensure agent/ is on Python path
AGENT_DIR = Path(__file__).resolve().parent.parent
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


@pytest.fixture
def knowledge_base_dir():
    """Path to the knowledge assets directory."""
    return str(AGENT_DIR / "harness" / "task")


@pytest.fixture
def sample_symptoms():
    """Common symptom ID sets for testing."""
    return {
        "fingerprint_bluetooth": ["fingerprint_fail", "bluetooth_disconnected"],
        "lock_stuck": ["lock_tongue_stuck"],
        "false_alarm": ["false_alarm", "beeping_no_operation"],
        "empty": [],
    }
