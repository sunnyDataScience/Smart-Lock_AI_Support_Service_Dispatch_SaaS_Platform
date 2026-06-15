"""[lock-cs-agent] 應用設定載入 — 把 LiteLLM 供應商 / 記憶等設定從程式碼獨立到 config.toml。

用 stdlib `tomllib`(Python 3.11+)。機密(服務帳號金鑰)不在 toml,只放路徑;
載入時把該路徑設成 GOOGLE_APPLICATION_CREDENTIALS(ADC)。
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

# config.toml 預設位置:lock-cs-agent/config.toml(本檔在 lock-cs-agent/lockcore/)
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"

# 客服 agent 工具白名單:只留「讀知識 + 兜底搜尋 + 轉真人」。
# read_file/list_dir/find_files/grep 是讀 skill(SKILL.md + references/)的命脈,不可砍;
# 砍掉 write/edit/exec/shell/spawn/cron/message/web_fetch/image 等對客服危險或無用的工具。
CS_TOOL_ALLOWLIST: set[str] = {
    "read_file",
    "list_dir",
    "find_files",
    "grep",
    "web_search",
    "transfer_to_human",
}


@dataclass(frozen=True)
class AppConfig:
    model: str
    temperature: float
    max_tokens: int
    # vertex(僅 model 以 vertex_ai/ 開頭時用)
    vertex_project: str | None
    vertex_location: str | None
    credentials_path: Path | None
    # memory
    tenant: str
    backend: str  # "sqlite"(本地檔案,預設)或 "postgres"(lock-ai Cloud SQL，agent schema)
    db_path: str  # backend="sqlite" 時的檔案路徑;":memory:" = 暫存
    postgres_uri_env: str  # backend="postgres" 時讀此環境變數取連線字串(預設 POSTGRES_URI)
    extractor: str  # "llm"(用 LLM 抽乾淨事實)或 "raw"(整句存,PoC fallback)


def _auto_vertex_location(model: str, location: str) -> str:
    """location 留空時自動選:gemini-3.x 走 global,其餘區域用 us-central1。"""
    if location:
        return location
    return "global" if "gemini-3" in model else "us-central1"


def load_config(path: str | Path | None = None) -> AppConfig:
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))

    llm = data.get("llm", {})
    vx = llm.get("vertex", {})
    mem = data.get("memory", {})
    model = llm.get("model", "vertex_ai/gemini-3.1-flash-lite")

    creds = vx.get("credentials") or ""
    creds_path: Path | None = None
    if creds:
        p = Path(creds)
        creds_path = p if p.is_absolute() else (cfg_path.parent / p)

    return AppConfig(
        model=model,
        temperature=float(llm.get("temperature", 0.7)),
        max_tokens=int(llm.get("max_tokens", 4096)),
        vertex_project=vx.get("project") or None,
        vertex_location=_auto_vertex_location(model, vx.get("location", "")),
        credentials_path=creds_path,
        tenant=mem.get("tenant", "locksmart"),
        backend=str(mem.get("backend", "sqlite")).strip().lower(),
        db_path=mem.get("db_path", ":memory:"),
        postgres_uri_env=mem.get("postgres_uri_env", "POSTGRES_URI"),
        extractor=str(mem.get("extractor", "llm")).strip().lower(),
    )


def build_provider(cfg: AppConfig):
    """依設定組出 LiteLLMProvider(vertex 模型會帶 project/location 並設 ADC)。"""
    from lockcore.providers.base import GenerationSettings
    from lockcore.providers.litellm_provider import LiteLLMProvider

    extra_body: dict = {}
    if cfg.model.startswith("vertex_ai/"):
        if cfg.credentials_path and cfg.credentials_path.exists():
            os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(cfg.credentials_path))
        if cfg.vertex_project:
            extra_body["vertex_project"] = cfg.vertex_project
            # 讓 web_search 的 Vertex grounding 也讀得到 project
            os.environ.setdefault("VERTEX_PROJECT_ID", cfg.vertex_project)
        if cfg.vertex_location:
            extra_body["vertex_location"] = cfg.vertex_location

    provider = LiteLLMProvider(default_model=cfg.model, extra_body=extra_body)
    provider.generation = GenerationSettings(temperature=cfg.temperature, max_tokens=cfg.max_tokens)
    return provider


def _pg_uri(cfg: AppConfig) -> str:
    uri = os.getenv(cfg.postgres_uri_env, "")
    if not uri:
        raise RuntimeError(
            f"memory.backend='postgres' 但環境變數 {cfg.postgres_uri_env} 未設定;"
            "請設定連線字串或改回 backend='sqlite'。"
        )
    return uri


def build_memory_manager(cfg: AppConfig, provider=None):
    """記憶管理器。extractor="llm" 且有 provider 時用 LLMExtractor 抽乾淨事實,
    否則退回 default_extractor(整句存,PoC fallback)。

    backend="postgres" 走 PostgresMemoryProvider(agent.memory_entry / pg_trgm),
    否則 SqliteMemoryProvider(本地檔案 / FTS5)。"""
    from lockcore.agent.user_memory import (
        LLMExtractor,
        MemoryManager,
        SqliteMemoryProvider,
        default_extractor,
    )

    if cfg.extractor == "llm" and provider is not None:
        extractor = LLMExtractor(provider, cfg.model)
    else:
        extractor = default_extractor

    if cfg.backend == "postgres":
        from lockcore.agent.user_memory.provider import PostgresMemoryProvider

        mem_provider = PostgresMemoryProvider(_pg_uri(cfg), extractor=extractor)
    else:
        mem_provider = SqliteMemoryProvider(cfg.db_path, extractor=extractor)
    return MemoryManager(mem_provider)


def build_escalation_store(cfg: AppConfig):
    """轉真人稽核紀錄(transfer_to_human 用)。與記憶同後端,各自獨立 table。"""
    if cfg.backend == "postgres":
        from lockcore.agent.user_memory.postgres_store import PostgresEscalationStore

        return PostgresEscalationStore(_pg_uri(cfg))

    from lockcore.agent.user_memory import EscalationStore

    return EscalationStore(cfg.db_path)
