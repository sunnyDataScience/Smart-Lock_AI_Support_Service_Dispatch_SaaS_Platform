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
    """tech 面未設 PASSWORD_RESET_WEB_URL → 連結指向師傅站 :3001(重設頁在那)。"""
    monkeypatch.delenv("PASSWORD_RESET_WEB_URL", raising=False)
    monkeypatch.setenv("API_SURFACE", "tech")
    assert _reset_link("tok").startswith("http://localhost:3001/reset-password?token=")


def test_reset_link_env_override_wins(monkeypatch):
    monkeypatch.setenv("API_SURFACE", "tech")
    monkeypatch.setenv("PASSWORD_RESET_WEB_URL", "https://tech.example.com")
    assert _reset_link("tok").startswith("https://tech.example.com/reset-password?token=")
