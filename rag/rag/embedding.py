"""embed() — 統一 embedding 介面（LiteLLM 路由，預設 vertex_ai/text-multilingual-embedding-002）。

維度固定 768（ADR-010；DB schema vector(768) 對齊）。
換模型須連動：Schema_rag.sql 維度 + 全量重嵌（embedding_model 欄可辨識舊向量）。
"""

import os
from pathlib import Path

from dotenv import load_dotenv
import litellm

EMBED_DIM = 768
# ADR-010 原訂 text-embedding-004；實測其對中文短文本退化（不同輸入回同一向量，
# 相似度全 1.0——它是英文為主模型）。改用同 768 維的 multilingual 版（CR-0124 勘誤）。
DEFAULT_MODEL = "vertex_ai/text-multilingual-embedding-002"

_ROOT = Path(__file__).resolve().parents[2]


def _ensure_credentials() -> None:
    load_dotenv(_ROOT / ".env")
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        for cand in (_ROOT / "credentials.json", _ROOT / "agent" / "credentials.json"):
            if cand.exists():
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cand)
                break
    if not os.getenv("VERTEX_PROJECT") and os.getenv("VERTEX_PROJECT_ID"):
        os.environ["VERTEX_PROJECT"] = os.getenv("VERTEX_PROJECT_ID")


def embed_model() -> str:
    return os.getenv("RAG_EMBED_MODEL", DEFAULT_MODEL)


def embed_texts(texts: list[str], *, batch_size: int = 64) -> list[list[float]]:
    """批次 embedding；回傳與輸入等長的 768 維向量列表。

    任一向量維度不符即丟錯（fail-fast——寧可灌注失敗也不落壞向量）。
    """
    _ensure_credentials()
    model = embed_model()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = litellm.embedding(model=model, input=batch)
        # litellm 回傳順序與輸入一致；仍以 index 排序防禦
        items = sorted(response.data, key=lambda d: d["index"])
        for item in items:
            vec = item["embedding"]
            if len(vec) != EMBED_DIM:
                raise ValueError(
                    f"embedding 維度 {len(vec)} ≠ {EMBED_DIM}（model={model}）——"
                    f"換模型須連動 Schema_rag.sql 並全量重嵌"
                )
            vectors.append(vec)
    return vectors


def embed_one(text: str) -> list[float]:
    return embed_texts([text])[0]
