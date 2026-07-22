"""[lock-cs-agent] 應用設定載入 — 把 LiteLLM 供應商 / 記憶等設定從程式碼獨立到 config.toml。

用 stdlib `tomllib`(Python 3.11+)。機密(服務帳號金鑰)不在 toml,只放路徑;
載入時把該路徑設成 GOOGLE_APPLICATION_CREDENTIALS(ADC)。
"""

from __future__ import annotations

import os
import os
import re
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
    # 多供應商 failover：主模型連續錯誤→熔斷→依序改試這些 fallback 模型（LiteLLM 字串）。
    # 空=不啟用（ADR-009；補上 LINE live path 原缺的 failover 接線）。
    fallback_models: tuple[str, ...] = ()
    # CR-0179 方案 B：樣本圖引導映射（key → 公開 HTTPS 圖 URL）。AI 回覆文末輸出
    # [[photo-guide:<key>]] 標記，gateway 剝除後附發 LINE ImageMessage。
    # 空=功能關閉。key 全小寫-連字號（避開 reply_guard 型號/價格 regex 形態）。
    photo_guides: tuple[tuple[str, str], ...] = ()


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
        fallback_models=tuple(str(m) for m in (llm.get("fallback_models") or [])),
        photo_guides=tuple(
            (str(k), str(v)) for k, v in (data.get("photo_guides") or {}).items()
        ),
    )


@dataclass(frozen=True)
class _FallbackPreset:
    """給 FallbackProvider 的最小 preset（model 字串路由多供應商）。"""

    model: str
    max_tokens: int
    temperature: float
    reasoning_effort: str | None = None


def _make_litellm(cfg: AppConfig, model: str, temperature: float, max_tokens: int):
    """建單一 LiteLLMProvider(vertex 模型會帶 project/location 並設 ADC)。"""
    from lockcore.providers.base import GenerationSettings
    from lockcore.providers.litellm_provider import LiteLLMProvider

    extra_body: dict = {}
    if model.startswith("vertex_ai/"):
        if cfg.credentials_path and cfg.credentials_path.exists():
            os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(cfg.credentials_path))
        if cfg.vertex_project:
            extra_body["vertex_project"] = cfg.vertex_project
            # 讓 web_search 的 Vertex grounding 也讀得到 project
            os.environ.setdefault("VERTEX_PROJECT_ID", cfg.vertex_project)
        if cfg.vertex_location:
            extra_body["vertex_location"] = cfg.vertex_location

    provider = LiteLLMProvider(default_model=model, extra_body=extra_body)
    provider.generation = GenerationSettings(temperature=temperature, max_tokens=max_tokens)
    return provider


def build_provider(cfg: AppConfig):
    """依設定組出 provider。

    cfg.fallback_models 非空時，把主 provider 包進 FallbackProvider 做多供應商
    failover（主模型連續錯誤→熔斷→依序試 fallback 模型；ADR-009）。這條原本只在
    上游 factory.make_provider 有接，LINE live path（本函式）漏接——此處補上。
    """
    primary = _make_litellm(cfg, cfg.model, cfg.temperature, cfg.max_tokens)
    if not cfg.fallback_models:
        return primary

    from lockcore.providers.fallback_provider import FallbackProvider

    presets = [
        _FallbackPreset(model=m, max_tokens=cfg.max_tokens, temperature=cfg.temperature)
        for m in cfg.fallback_models
    ]
    return FallbackProvider(
        primary=primary,
        fallback_presets=presets,
        provider_factory=lambda fb: _make_litellm(cfg, fb.model, fb.temperature, fb.max_tokens),
    )


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


def build_webhook_idempotency_store(cfg: AppConfig):
    """LINE webhook 重送去重（CR-0166 R1）。postgres 後端才有跨實例防護；
    非 postgres（本機 sqlite）回 None＝不去重（單實例 burst 已由 _TurnDebouncer 處理）。"""
    if cfg.backend == "postgres":
        from lockcore.agent.user_memory.postgres_store import (
            PostgresWebhookIdempotencyStore,
        )

        return PostgresWebhookIdempotencyStore(_pg_uri(cfg))
    return None


# ── MCP servers（RAG-via-MCP，ADR-010/CR-0125）────────────────────────────
# config.toml [mcp_servers.<name>] → lockcore MCPServerConfig。
# env 值支援 ${VAR} 展開（機密不入 toml）；任一 ${VAR} 解不到值 → 跳過該 server
# （= RAG 未配置,agent 完全維持既有行為;MCP 工具註冊在 CS_TOOL_ALLOWLIST
# 剝離之後,白名單紅線不動）。

_ENV_VAR_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand_env(value: str) -> tuple[str, bool]:
    """展開 ${VAR}；回傳 (結果, 是否有變數解不到值)。"""
    missing = False

    def sub(m: re.Match) -> str:
        nonlocal missing
        v = os.environ.get(m.group(1), "")
        if not v:
            missing = True
        return v

    return _ENV_VAR_RE.sub(sub, value), missing


def load_mcp_servers(path: str | Path | None = None) -> dict:
    """讀 config.toml 的 [mcp_servers.*]，回傳 {name: MCPServerConfig}。"""
    from lockcore.config.schema import MCPServerConfig
    from loguru import logger

    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    servers: dict[str, object] = {}
    for name, raw in (data.get("mcp_servers") or {}).items():
        env: dict[str, str] = {}
        skip = False
        for k, v in (raw.get("env") or {}).items():
            expanded, missing = _expand_env(str(v))
            if missing:
                logger.info(
                    "MCP server '{}' 未配置（env {} 缺值）→ 跳過,agent 行為不變", name, k
                )
                skip = True
                break
            env[k] = expanded
        if skip:
            continue
        cwd = raw.get("cwd") or ""
        if cwd and not Path(cwd).is_absolute():
            cwd = str((cfg_path.parent / cwd).resolve())
        servers[name] = MCPServerConfig(
            type=raw.get("type"),
            command=raw.get("command", ""),
            args=list(raw.get("args", [])),
            env=env,
            cwd=cwd,
            url=raw.get("url", ""),
            tool_timeout=int(raw.get("tool_timeout", 30)),
            enabled_tools=list(raw.get("enabled_tools", ["*"])),
        )
    return servers
