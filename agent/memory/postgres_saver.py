import os
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

_postgres_pool: AsyncConnectionPool | None = None


async def build_postgres_saver(config: dict):
    """建立 checkpointer。

    使用 AsyncConnectionPool 而非單一 AsyncConnection，避免 CloudSQL idle 斷線後
    LangGraph checkpointer 整個失效（症狀：the connection is closed → agent 無法回覆）。
    Pool 會在 checkout 時自動驗證連線並回收壞掉的連線。
    """
    global _postgres_pool
    uri = os.getenv(config.get("postgres_uri_env", "POSTGRES_URI"))
    print(f"[*] 初始化記憶體模組: 連線至 PostgreSQL（pool）")

    pool = AsyncConnectionPool(
        conninfo=uri,
        min_size=1,
        max_size=int(config.get("pool_max_size", 10)),
        max_idle=float(config.get("pool_max_idle_seconds", 240)),  # < CloudSQL idle (~600s)
        timeout=float(config.get("pool_checkout_timeout", 30)),
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=False,
        check=AsyncConnectionPool.check_connection,
    )
    await pool.open(wait=True)
    _postgres_pool = pool

    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    return saver


async def close_postgres_conn():
    global _postgres_pool
    if _postgres_pool is not None:
        await _postgres_pool.close()
        _postgres_pool = None
