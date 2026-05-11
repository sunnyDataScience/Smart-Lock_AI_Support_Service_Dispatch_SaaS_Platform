"""產品資訊載入器（DB-backed）。

資料來源：PostgreSQL `product_docs` 表（DB 是 SoT）。
對外介面：
    - ProductDoc dataclass
    - load_all_docs(pool)         — 啟動時呼叫一次，從 DB 進記憶體 cache
    - reload_from_db(pool)        — 熱重載 API 用
    - all_docs() / get_doc(name)  — 查詢 cache
    - filter_loadable(brand, model) — profile gating
    - has_brand(brand)            — 該品牌是否存在

每份文件以 (brand, model) 對應一個 row，filter_loadable 邏輯：
    - 品牌+型號齊備：{brand}/{model} + {brand}/_brand（若有） + 全部 _common/*
    - 只知品牌    ：{brand}/_brand（若有） + 全部 _common/*
    - 都不知      ：只有 _common/*

== Mirror 機制 ==

本套件 runtime 只讀 DB，但在 agent/product_info/{Brand}/{Model}.md 維護
git mirror 供：
    - PR review / code search
    - 新人 onboard 看結構
    - 緊急時 backup（DB 掛了可重新 seed）

DB 仍是 source of truth，mirror 是「讀副本」。
"""

from __future__ import annotations

from dataclasses import dataclass

from psycopg_pool import AsyncConnectionPool


@dataclass
class ProductDoc:
    """單份產品文件。"""
    brand: str
    model: str | None
    name: str           # "Dormakaba/AS701" 或 "_common/troubleshoot"
    description: str
    body: str           # 純內容（去掉 frontmatter）


_docs: list[ProductDoc] = []
_index: dict[str, ProductDoc] = {}


async def load_all_docs(pool: AsyncConnectionPool) -> list[ProductDoc]:
    """從 DB 載入所有產品文件進記憶體 cache。"""
    global _docs, _index
    docs: list[ProductDoc] = []
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT name, brand, model, description, body FROM product_docs ORDER BY name"
            )
            rows = await cur.fetchall()
    for name, brand, model, description, body in rows:
        docs.append(ProductDoc(
            brand=brand,
            model=model,
            name=name,
            description=description,
            body=body,
        ))
    _docs = docs
    _index = {d.name: d for d in docs}
    return docs


async def reload_from_db(pool: AsyncConnectionPool) -> int:
    """熱重載 — admin API 用。回傳載入的 doc 數量。"""
    docs = await load_all_docs(pool)
    return len(docs)


def all_docs() -> list[ProductDoc]:
    return list(_docs)


def _is_brand_common(d: ProductDoc) -> bool:
    """品牌通用文件：brand=具體品牌、model 以 `_` 開頭（如 `_brand`）。"""
    return d.brand != "_common" and d.model is not None and d.model.startswith("_")


def filter_loadable(brand: str | None, model: str | None) -> list[ProductDoc]:
    """依 profile 計算可載入清單（邏輯與 v1 一致）。"""
    if brand and model:
        target = f"{brand}/{model}"
        return [d for d in _docs if d.name == target
                or (d.brand == brand and _is_brand_common(d))
                or d.brand == "_common"]
    if brand:
        return [d for d in _docs if (d.brand == brand and _is_brand_common(d))
                or d.brand == "_common"]
    return [d for d in _docs if d.brand == "_common"]


def get_doc(name: str) -> ProductDoc | None:
    return _index.get(name)


def has_brand(brand: str) -> bool:
    """檢查指定品牌是否有任何產品文件。"""
    return any(d.brand == brand for d in _docs)
