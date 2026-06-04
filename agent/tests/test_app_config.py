"""config.toml 載入器測試(離線,不打 API)。"""

from pathlib import Path

from lockcore.app_config import build_provider, load_config
from lockcore.providers.litellm_provider import LiteLLMProvider

_TOML = """
[llm]
model = "{model}"
temperature = 0.3
max_tokens = 1234

[llm.vertex]
project = "proj-x"
location = "{loc}"
credentials = "credentials.json"

[memory]
tenant = "acme"
db_path = ":memory:"
"""


def _write(tmp_path, model, loc=""):
    p = tmp_path / "config.toml"
    p.write_text(_TOML.format(model=model, loc=loc))
    return p


def test_loads_basic_fields(tmp_path):
    cfg = load_config(_write(tmp_path, "vertex_ai/gemini-2.5-flash"))
    assert cfg.model == "vertex_ai/gemini-2.5-flash"
    assert cfg.temperature == 0.3
    assert cfg.max_tokens == 1234
    assert cfg.vertex_project == "proj-x"
    assert cfg.tenant == "acme"
    assert cfg.db_path == ":memory:"
    # credentials 解析為相對 config.toml 的絕對路徑
    assert cfg.credentials_path == tmp_path / "credentials.json"


def test_auto_endpoint_gemini3_global(tmp_path):
    cfg = load_config(_write(tmp_path, "vertex_ai/gemini-3.1-flash-lite"))
    assert cfg.vertex_location == "global"


def test_auto_endpoint_gemini25_region(tmp_path):
    cfg = load_config(_write(tmp_path, "vertex_ai/gemini-2.5-flash"))
    assert cfg.vertex_location == "us-central1"


def test_explicit_location_respected(tmp_path):
    cfg = load_config(_write(tmp_path, "vertex_ai/gemini-3.1-flash-lite", loc="us-east5"))
    assert cfg.vertex_location == "us-east5"


def test_build_provider_vertex(tmp_path):
    cfg = load_config(_write(tmp_path, "vertex_ai/gemini-3.1-flash-lite"))
    prov = build_provider(cfg)
    assert isinstance(prov, LiteLLMProvider)
    assert prov.get_default_model() == "vertex_ai/gemini-3.1-flash-lite"
    assert prov._extra_body.get("vertex_project") == "proj-x"
    assert prov._extra_body.get("vertex_location") == "global"
    assert prov.generation.max_tokens == 1234
