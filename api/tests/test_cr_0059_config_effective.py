"""CR-0059 M18 config 排程生效日測試（BR-M18-02）。"""
from __future__ import annotations
import uuid
import pytest
import core.db as db_module
from services import config_m18_service as cfg

pytestmark = pytest.mark.component


@pytest.mark.asyncio
async def test_due_scheduled_activates_and_retires_old():
    assert await db_module._ensure_conn()
    ns = "test_sched_" + uuid.uuid4().hex[:8]
    # namespace
    await db_module._conn.execute(
        "INSERT INTO saas.config_namespace(code, description, json_schema) "
        "VALUES (%s, 't', '{}'::jsonb) ON CONFLICT DO NOTHING", (ns,))
    # 現行 active
    await db_module._conn.execute(
        "INSERT INTO saas.config_version(tenant_id,namespace,key,value,state,created_by,activated_at) "
        "VALUES (NULL,%s,'default','{\"v\":1}'::jsonb,'active','00000000-0000-0000-0000-000000000001',now())", (ns,))
    # 排程 draft（過去 effective_at → 到期）
    await db_module._conn.execute(
        "INSERT INTO saas.config_version(tenant_id,namespace,key,value,state,created_by,effective_at) "
        "VALUES (NULL,%s,'default','{\"v\":2}'::jsonb,'draft','00000000-0000-0000-0000-000000000001',now()-interval '1 hour')", (ns,))
    try:
        n = await cfg.activate_due_scheduled()
        assert n >= 1
        val = await cfg.read_global_value(namespace=ns)
        assert val == {"v": 2}  # 新值生效
        # 舊 active 已退役
        cur = await db_module._conn.execute(
            "SELECT count(*) FROM saas.config_version WHERE namespace=%s AND state='active'", (ns,))
        assert (await cur.fetchone())[0] == 1
    finally:
        await db_module._conn.execute("DELETE FROM saas.config_version WHERE namespace=%s", (ns,))
        await db_module._conn.execute("DELETE FROM saas.config_namespace WHERE code=%s", (ns,))
