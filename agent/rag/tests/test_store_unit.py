"""store/embedding 純單元測試（無 DB、無網路）。"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.store import _vec_literal, tenant_id  # noqa: E402
from rag.embedding import EMBED_DIM, embed_model, DEFAULT_MODEL  # noqa: E402


def test_vec_literal_format():
    assert _vec_literal([0.1, -0.25, 1.0]) == "[0.1,-0.25,1]"


def test_tenant_default_deny(monkeypatch):
    monkeypatch.delenv("RAG_TENANT_ID", raising=False)
    with pytest.raises(RuntimeError, match="RAG_TENANT_ID"):
        tenant_id()


def test_tenant_uuid_validation(monkeypatch):
    monkeypatch.setenv("RAG_TENANT_ID", "not-a-uuid")
    with pytest.raises(ValueError):
        tenant_id()
    monkeypatch.setenv("RAG_TENANT_ID", "00000000-0000-0000-0000-000000000001")
    assert tenant_id() == "00000000-0000-0000-0000-000000000001"


def test_embed_model_default(monkeypatch):
    monkeypatch.delenv("RAG_EMBED_MODEL", raising=False)
    assert embed_model() == DEFAULT_MODEL
    monkeypatch.setenv("RAG_EMBED_MODEL", "vertex_ai/gemini-embedding-001")
    assert embed_model() == "vertex_ai/gemini-embedding-001"


def test_embed_dim_constant():
    assert EMBED_DIM == 768  # 與 SQL/Schema_rag.sql vector(768) 對齊
