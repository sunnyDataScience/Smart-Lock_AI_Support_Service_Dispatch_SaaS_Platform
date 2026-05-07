"""Dispatcher 工廠 — 對齊 SQL/seeds/dispatcher_user.sql。

V2.0 新獨立角色（PM Q1=A），用於解鎖 F-004 / F-019 派工流程測試。

Schema：id, tenant_id, email, password_hash, display_name, role='dispatcher',
        is_active, created_at, updated_at
"""

from __future__ import annotations

import uuid

import factory

from .tenant import DEFAULT_TENANT_ID

# 與 _admin_user.sql 同款 bcrypt（明文 changeme123）；測試環境不轉碼
DEFAULT_PASSWORD_HASH = "$2b$12$Hdfo2ixXxQXkAIYXaDz23.HSP8MD1TrkD3CvpwtdSqvDWSq.BAui6"


class DispatcherFactory(factory.DictFactory):
    """輸出 dispatcher 角色 user dict — role 固定為 'dispatcher'。"""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    tenant_id = DEFAULT_TENANT_ID
    email = factory.LazyAttribute(lambda o: f"dispatcher-{o.id[:8]}@example.com")
    password_hash = DEFAULT_PASSWORD_HASH
    display_name = factory.Faker("name", locale="zh_TW")
    role = "dispatcher"
    is_active = True
