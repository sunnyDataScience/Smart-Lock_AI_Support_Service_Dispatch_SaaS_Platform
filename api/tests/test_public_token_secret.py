"""public token 的 HMAC 金鑰來源（2026-08-02 資安掃描）。

**原問題**：`_get_secret()` 在 `PUBLIC_TOKEN_HMAC_SECRET` 未設時**靜默** fallback 到
原始碼裡的固定常數 `"dev-secret-do-not-use-in-prod"`。任何讀得到那一行的人都能簽發
合法的消費者 token——而這些 token 保護的不只是唯讀端點：

  POST /consumer/quotes/{token}          代客戶接受報價
  POST /consumer/scope-changes/{token}   代客戶核可加價
  POST /consumer/consents/{token}        代客戶同意
  POST /consumer/bindings:consume        LINE 綁定

payload 是明文 base64（`{"sub": ..., "purpose": ..., "exp": ..., "tenant_id": ...}`），
偽造只需要知道工單 UUID。

**修法**：env 未設時改用 process 啟動時隨機產生的金鑰 + `logger.critical`。
刻意不做成啟動失敗——若部署環境確實漏設，fail-fast 會直接變成 outage；
隨機金鑰只讓既有公開連結失效（那些連結若真是用已知金鑰簽的，本來就該失效）。
"""

from __future__ import annotations

import importlib

import pytest

pytestmark = pytest.mark.unit


def _reload_with_env(monkeypatch, value: str | None):
    """以指定的 env 值重新載入模組（module-level 的隨機金鑰要重新產生）。"""
    if value is None:
        monkeypatch.delenv("PUBLIC_TOKEN_HMAC_SECRET", raising=False)
    else:
        monkeypatch.setenv("PUBLIC_TOKEN_HMAC_SECRET", value)
    import services.public_token as mod
    return importlib.reload(mod)


def test_no_hardcoded_dev_secret_in_source():
    """原始碼裡不得再出現那個固定 fallback 字串。

    這是本檔最重要的一條——它擋的是「有人為了本機方便又加回來」。
    """
    import pathlib
    import services.public_token as mod
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    # 註解裡引用歷史字串是可以的，但不能出現在賦值語句
    offending = [
        ln for ln in src.splitlines()
        if "dev-secret-do-not-use-in-prod" in ln and not ln.lstrip().startswith("#")
    ]
    assert not offending, f"固定 dev secret 又被寫回程式碼：{offending}"


def test_env_secret_is_used_when_set(monkeypatch):
    mod = _reload_with_env(monkeypatch, "a-real-secret-from-secret-manager")
    assert mod._get_secret() == b"a-real-secret-from-secret-manager"


def test_missing_env_does_not_fall_back_to_a_known_constant(monkeypatch):
    """env 未設時用的金鑰必須是隨機的，不是任何可預測的常數。"""
    mod = _reload_with_env(monkeypatch, None)
    secret = mod._get_secret()
    assert secret != b"dev-secret-do-not-use-in-prod"
    assert len(secret) >= 32, "隨機金鑰長度不足"


def test_missing_env_logs_critical(monkeypatch, caplog):
    """漏設必須大聲叫——這是唯一會被發現的管道。"""
    mod = _reload_with_env(monkeypatch, None)
    mod._secret_warning_emitted = False
    with caplog.at_level("CRITICAL", logger="api.public_token"):
        mod._get_secret()
    assert any(
        r.levelname == "CRITICAL" and "PUBLIC_TOKEN_HMAC_SECRET" in r.getMessage()
        for r in caplog.records
    ), "env 未設時沒有記 CRITICAL"


def test_two_processes_without_env_do_not_share_a_secret(monkeypatch):
    """兩個沒設 env 的 process 不可共用同一把金鑰。

    這條釘住「隨機」的實質意義：若改回固定常數，兩次 reload 會得到相同值，此測試變紅。
    """
    first = _reload_with_env(monkeypatch, None)._get_secret()
    second = _reload_with_env(monkeypatch, None)._get_secret()
    assert first != second, "兩次載入得到相同金鑰＝金鑰不是隨機的"


def test_token_signed_with_one_secret_is_rejected_by_another(monkeypatch):
    """跨金鑰的 token 必須驗不過——證明簽章真的綁在金鑰上。"""
    mod = _reload_with_env(monkeypatch, "secret-A")
    token = mod.generate_token("11111111-1111-1111-1111-111111111111",
                               purpose="work_order_status")
    assert mod.verify_token(token).subject_id == "11111111-1111-1111-1111-111111111111"

    mod2 = _reload_with_env(monkeypatch, "secret-B")
    with pytest.raises(mod2.TokenInvalidError):
        mod2.verify_token(token)
