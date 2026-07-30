"""師傅推播深連結不得是 localhost 的純單元測試(無 DB)。

2026-07-30 業主回報:實收 LINE 推播「📢 搶單池有新工單…先接先得:
http://localhost:3001/pool」。根因=本機 stack 掛了真實
PLATFORM_LINE_CHANNEL_ACCESS_TOKEN,推的是真訊息到真手機,而
`tech_portal_base()` 未設 env 時退 `http://localhost:3001`。

手機不在容器/開發機的 network namespace,localhost 在那裡**永遠**打不開——
所以這不是「本機環境沒設好」,是預設值本身在這個投遞情境下就是錯的。
本檔鎖住:未設 env 時預設必須是可公開連線的正式站,且 env 覆蓋仍有效。
"""

from urllib.parse import urlparse

import pytest

from services import technician_line_service as tls


def test_default_base_is_not_localhost(monkeypatch):
    """未設 TECH_PORTAL_URL → 不得退 localhost/127.0.0.1(手機點不開)。"""
    monkeypatch.delenv("TECH_PORTAL_URL", raising=False)
    host = urlparse(tls.tech_portal_base()).hostname or ""
    assert host not in ("localhost", "127.0.0.1", "0.0.0.0", "::1")


def test_default_base_is_public_https(monkeypatch):
    """預設值須是 https 的正式站(LINE 訊息裡的連結要能直接點)。"""
    monkeypatch.delenv("TECH_PORTAL_URL", raising=False)
    assert tls.tech_portal_base().startswith("https://")


def test_empty_env_falls_back_to_default(monkeypatch):
    """compose 會傳 `TECH_PORTAL_URL=`(空字串)——空值須落回預設,不可組出 `/pool`。"""
    monkeypatch.setenv("TECH_PORTAL_URL", "")
    assert tls.tech_portal_base() == tls._DEFAULT_TECH_PORTAL_URL.rstrip("/")


def test_env_override_still_wins(monkeypatch):
    """顯式設定仍優先(prod 由 api.sh 烤入;要測本機也走這條)。"""
    monkeypatch.setenv("TECH_PORTAL_URL", "http://localhost:3001/")
    assert tls.tech_portal_base() == "http://localhost:3001"


@pytest.mark.parametrize("suffix", ["/pool", "/my-orders"])
def test_push_deeplinks_are_reachable_urls(monkeypatch, suffix):
    """兩條推播文案(池單 /pool、指派 /my-orders)的深連結都不得含 localhost。"""
    monkeypatch.delenv("TECH_PORTAL_URL", raising=False)
    link = f"{tls.tech_portal_base()}{suffix}"
    assert "localhost" not in link
    assert link.startswith("https://")
