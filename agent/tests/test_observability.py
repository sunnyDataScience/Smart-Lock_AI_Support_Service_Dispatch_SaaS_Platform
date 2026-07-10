"""CR-0156/ADR-007 可觀測性測試:scrub 純函式、no-op 語意(env 未設不炸)、
turn_span nullcontext、套件缺降級、OPIK opt-in gating。全程不需 otel/opik 套件。"""

from __future__ import annotations

import sys

import litellm
import pytest

import lockcore.observability as obs
import lockcore.providers.litellm_provider as lp
from lockcore.observability import scrub_text, turn_span


@pytest.fixture(autouse=True)
def _reset_obs_state(monkeypatch):
    """每個測試前重置模組級狀態(setup 冪等旗標),並清掉 opt-in env。"""
    monkeypatch.setattr(obs, "_initialized", False)
    monkeypatch.setattr(obs, "_enabled", False)
    monkeypatch.setattr(obs, "_tracer", None)
    monkeypatch.setattr(lp, "_OPIK_WIRED", False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OPIK_API_KEY", raising=False)
    yield


# ── scrub_text 純函式 ────────────────────────────────────────────────────────

def test_scrub_line_uid_hashed_and_stable():
    uid = "U" + "a1b2c3d4" * 4  # U + 32 hex
    out = scrub_text(f"客人 {uid} 傳訊息")
    assert uid not in out
    assert "U#" in out
    # 雜湊保留關聯性:同 uid 兩次遮蔽結果一致
    assert scrub_text(uid) == scrub_text(uid)
    assert len(scrub_text(uid)) == 2 + 12  # "U#" + sha256 前 12 碼


def test_scrub_email_phone_addr_token():
    assert "[EMAIL]" in scrub_text("聯絡 sunny@funngo.ai 謝謝")
    assert "sunny@funngo.ai" not in scrub_text("聯絡 sunny@funngo.ai 謝謝")
    assert "[PHONE]" in scrub_text("手機 0912-345-678")
    assert "0912" not in scrub_text("手機 0912-345-678")
    assert "[ADDR]" in scrub_text("地址 台北市大安區和平東路二段106號")
    out = scrub_text("http://x/cb?access_token=abc123&next=1")
    assert "abc123" not in out
    assert "access_token=[TOKEN]" in out


def test_scrub_non_pii_passthrough():
    text = "門鎖 Dormakaba AS701 無法上鎖,電池已換新"
    assert scrub_text(text) == text


def test_scrub_attributes_types():
    uid = "U" + "0f" * 16
    out = obs._scrub_attributes({"session_key": f"locksmart:{uid}", "retry": 3, "ok": True})
    assert uid not in out["session_key"]
    assert "U#" in out["session_key"]
    assert out["retry"] == 3
    assert out["ok"] is True


# ── no-op 語意(opt-in:env 未設=零行為變化)──────────────────────────────────

def test_setup_noop_without_env():
    assert obs.setup_observability() is False
    assert obs.observability_enabled() is False


def test_turn_span_nullcontext_without_env():
    cm = turn_span("agent.turn", channel="line")
    with cm as span:
        assert span is None  # nullcontext 語意
    assert obs.observability_enabled() is False


def test_setup_degrades_when_otel_missing(monkeypatch):
    """endpoint 有設但 otel 套件缺 → 降級停用 + 不炸;turn_span 仍為 no-op。"""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    # sys.modules 塞 None → `from opentelemetry import ...` 必 ImportError(確定性)
    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    assert obs.setup_observability() is False
    assert obs.observability_enabled() is False
    with turn_span("agent.turn", channel="line") as span:
        assert span is None


def test_setup_idempotent():
    assert obs.setup_observability() is False
    assert obs.setup_observability() is False  # 第二次走冪等旗標,不重跑


# ── OPIK gating(litellm_provider)────────────────────────────────────────────

def test_opik_noop_without_env(monkeypatch):
    before = list(litellm.callbacks or [])
    lp._maybe_enable_opik()
    assert list(litellm.callbacks or []) == before  # 未設 OPIK_API_KEY=零行為變化


def test_opik_missing_package_degrades(monkeypatch):
    monkeypatch.setenv("OPIK_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "opik", None)  # 強制 `import opik` ImportError
    before = list(litellm.callbacks or [])
    lp._maybe_enable_opik()  # 不炸=通過;WARNING 由 loguru 出
    assert list(litellm.callbacks or []) == before


def test_provider_init_without_env_keeps_callbacks(monkeypatch):
    before = list(litellm.callbacks or [])
    lp.LiteLLMProvider(api_key="x")
    assert list(litellm.callbacks or []) == before
