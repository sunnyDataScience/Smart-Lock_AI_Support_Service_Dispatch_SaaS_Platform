"""16.5.4-fix:忘記密碼 surface 分流的純單元測試(無 DB)。

live E2E 已實證(2026-07-16):tech 面 request→技師庫 token、confirm→技師庫改密
+新密碼登入成功;此處鎖住 surface 判斷與 reset 連結的站台路由,防回歸。
"""

from services.password_reset_service import _is_tech_surface, _reset_link


def test_tech_surface_detection(monkeypatch):
    monkeypatch.setenv("API_SURFACE", "tech")
    assert _is_tech_surface() is True
    monkeypatch.setenv("API_SURFACE", "dispatch")
    assert _is_tech_surface() is False
    monkeypatch.delenv("API_SURFACE", raising=False)
    assert _is_tech_surface() is False  # 預設 all=非 tech 面


def test_reset_link_routes_to_tech_portal_on_tech_surface(monkeypatch):
    """tech 面未設 PASSWORD_RESET_WEB_URL → 連結指向師傅站（重設頁在那）。

    **2026-07-30 改寫本測試的契約**：原本斷言 `http://localhost:3001`。
    而 prod 的 lock-tech-api 確實沒設這個 env → 技師收到的信裡就是 localhost 連結，
    在他手機/電腦上永遠打不開。與 CR-0194 的 LINE 深連結同一類 bug：
    **寄到使用者裝置上的連結不能是 localhost**。
    """
    monkeypatch.delenv("PASSWORD_RESET_WEB_URL", raising=False)
    monkeypatch.setenv("API_SURFACE", "tech")
    link = _reset_link("tok")
    assert link.endswith("/reset-password?token=tok")
    assert "localhost" not in link, "寄出去的重設連結不得是 localhost"
    assert link.startswith("https://")


def test_reset_link_brand_surface_follows_cors_origins(monkeypatch):
    """品牌面退 `cors_origins[0]` —— 這條**刻意保留**，因為它隨環境變動而正確：
    本機 cors_origins 是 localhost:3000（本機開發本來就要 localhost），
    prod 的 CORS_ORIGINS 是正式網址。這與 tech 面原本**硬編碼** localhost 是兩回事。
    """
    from services import password_reset_service as svc

    monkeypatch.delenv("PASSWORD_RESET_WEB_URL", raising=False)
    monkeypatch.setenv("API_SURFACE", "dispatch")

    class _Cfg:
        system = {"cors_origins": ["https://brand.example.com"]}

    monkeypatch.setattr(svc, "load_config", lambda: _Cfg())
    assert _reset_link("tok").startswith("https://brand.example.com/reset-password?token=")


def test_reset_link_brand_surface_without_cors_falls_back_to_prod(monkeypatch):
    """連 cors_origins 都沒有時才用得到常數 —— 那個常數也不得是 localhost。"""
    from services import password_reset_service as svc

    monkeypatch.delenv("PASSWORD_RESET_WEB_URL", raising=False)
    monkeypatch.setenv("API_SURFACE", "dispatch")

    class _Cfg:
        system: dict = {}

    monkeypatch.setattr(svc, "load_config", lambda: _Cfg())
    link = _reset_link("tok")
    assert "localhost" not in link, f"最後防線退到 localhost：{link}"
    assert link.startswith("https://")


def test_reset_link_env_override_wins(monkeypatch):
    monkeypatch.setenv("API_SURFACE", "tech")
    monkeypatch.setenv("PASSWORD_RESET_WEB_URL", "https://tech.example.com")
    assert _reset_link("tok").startswith("https://tech.example.com/reset-password?token=")
