import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

_sqlite_conn = None

async def build_sqlite_saver(config: dict):
    global _sqlite_conn
    db_path = config.get("sqlite_path", "./data/db/chat_history.db")
    print(f"[*] 初始化記憶體模組: 連線至 SQLite ({db_path})")
    conn = await aiosqlite.connect(db_path, timeout=30)
    await conn.execute("PRAGMA journal_mode=WAL")
    _sqlite_conn = conn
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    return saver

async def close_sqlite_conn():
    global _sqlite_conn
    if _sqlite_conn is not None:
        try:
            await _sqlite_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as e:
            # WAL checkpoint failure is non-fatal — connection close still proceeds.
            # Log so production issues are observable (CLAUDE.md: 絕不靜默吞噬錯誤).
            print(f"[SQLite Memory] WAL checkpoint 失敗（將續行關閉連線）: {e}")
        await _sqlite_conn.close()
        _sqlite_conn = None
