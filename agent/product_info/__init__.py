"""產品資訊載入器（profile-driven mega-doc）。

每份產品文件對應一個 (brand, model)，由 `load_product_info` tool 按需載入；
依用戶 profile 嚴格 gating（品牌+型號齊備時才能載入該型號文件）。

目錄結構：
    product_info/
        {Brand}/{Model}.md   — 型號 mega-doc
        {Brand}/_brand.md    — 品牌通用文件（已知品牌、型號未確認時可載入）
        _common/{topic}.md   — 跨品牌通用文件（troubleshoot / dispatch / ...）

凡 `{Brand}/` 下檔名以 `_` 開頭者視為品牌通用文件，model 欄位即為檔名（如 `_brand`）。

每份文件以 YAML frontmatter 開頭：
    ---
    brand: Dormakaba   # 或 _common
    model: AS701       # _common 可省略；品牌通用文件填 _brand
    description: "..."  # 一行摘要，會出現在 [可用產品資料] 清單
    ---
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


@dataclass
class ProductDoc:
    """單份產品文件。"""
    brand: str
    model: str | None
    name: str           # "Dormakaba/AS701" 或 "_common/troubleshoot"
    description: str
    path: Path
    body: str           # 純內容（去掉 frontmatter）


_docs: list[ProductDoc] = []
_index: dict[str, ProductDoc] = {}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 YAML frontmatter。回傳 (meta, body)。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta_block = m.group(1)
    body = text[m.end():]
    meta: dict = {}
    for line in meta_block.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip().strip('"').strip("'")
        meta[k.strip()] = v
    return meta, body


def load_all_docs(root: str | Path) -> list[ProductDoc]:
    """掃描 product_info 目錄，載入所有 .md 文件。"""
    global _docs, _index
    root = Path(root)
    docs: list[ProductDoc] = []
    if not root.exists():
        _docs = []
        _index = {}
        return _docs

    for md_path in sorted(root.rglob("*.md")):
        rel = md_path.relative_to(root)
        parts = rel.with_suffix("").parts
        if len(parts) != 2:
            continue
        brand, model_or_topic = parts
        text = md_path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        # 路徑優先：優先信任目錄結構，frontmatter 補上 description
        if brand == "_common":
            doc_brand = "_common"
            doc_model = None
            name = f"_common/{model_or_topic}"
        else:
            doc_brand = brand
            doc_model = model_or_topic
            name = f"{brand}/{model_or_topic}"
        docs.append(ProductDoc(
            brand=doc_brand,
            model=doc_model,
            name=name,
            description=meta.get("description", "(no description)"),
            path=md_path,
            body=body.strip(),
        ))

    _docs = docs
    _index = {d.name: d for d in docs}
    return docs


def all_docs() -> list[ProductDoc]:
    return list(_docs)


def _is_brand_common(d: ProductDoc) -> bool:
    """品牌通用文件：brand=具體品牌、model 以 `_` 開頭（如 `_brand`）。"""
    return d.brand != "_common" and d.model is not None and d.model.startswith("_")


def filter_loadable(brand: str | None, model: str | None) -> list[ProductDoc]:
    """依 profile 計算可載入清單。

    - 品牌+型號齊備：{brand}/{model} + {brand}/_brand（若有） + 全部 _common/*
    - 只知品牌：{brand}/_brand（若有） + 全部 _common/*
    - 都不知：只有 _common/*
    """
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
    """檢查指定品牌是否有任何產品文件（決定該品牌是否走新流程）。"""
    return any(d.brand == brand for d in _docs)
