"""Provenance 解析 — 每個知識 chunk 可回溯到 bronze 來源檔。

治理依據（CLAUDE.md bronze-only 紅線）：知識內容嚴格源自
`knowledge-pipeline/storage/bronze/`；GDrive PDF 內容不可信、只引 URL。
本模組讓紅線機器可查核：chunk 帶 bronze 檔路徑 + sha256，
audit_corpus.py 據此驗證來源存在且未漂移。
"""

import hashlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BRONZE_DIR = ROOT_DIR / "storage" / "bronze"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def chunk_id(source_type: str, source: str, chunk_index: str, content: str) -> str:
    """確定性 chunk id：同一來源同一段內容永遠同 id（冪等重跑不重複）。"""
    key = f"{source_type}\x00{source}\x00{chunk_index}\x00{content}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


# silver 產生後 bronze 曾改名（錯字修正），後綴比對救不回的登記於此
_SOURCE_ALIASES = {
    ("video", "Chainlock 設定教學.txt"): "Chatlock 設定教學.txt",  # Chainlock 為錯字
}


def resolve_bronze(source_type: str, source: str) -> tuple[str | None, str | None]:
    """由 silver chunk 的 (source_type, source) 找 bronze 檔，回傳 (相對路徑, sha256)。

    解析順序（處理 silver 產生後 bronze 改名的血緣漂移）：
      1. 精確路徑
      2. 別名表（錯字修正類改名）
      3. stem 完全相符（副檔名/子目錄差異）
      4. 唯一後綴相符（bronze 後來加品牌前綴，如「鎖栓測試進階」→「Dormakaba 鎖栓測試進階」）
    找不到回 (None, None) —— 由 audit 擋下。
    """
    alias = _SOURCE_ALIASES.get((source_type, source))
    if alias:
        source = alias

    candidate = BRONZE_DIR / source_type / source
    if candidate.exists():
        return (
            str(candidate.relative_to(ROOT_DIR)),
            sha256_file(candidate),
        )

    src_dir = BRONZE_DIR / source_type
    if not src_dir.is_dir():
        return (None, None)
    files = [p for p in src_dir.rglob("*") if p.is_file()]

    stem = Path(source).stem
    matches = [p for p in files if p.stem == stem]
    if len(matches) != 1:
        matches = [p for p in files if p.name.endswith(source)]
    if len(matches) == 1:
        return (
            str(matches[0].relative_to(ROOT_DIR)),
            sha256_file(matches[0]),
        )
    return (None, None)
