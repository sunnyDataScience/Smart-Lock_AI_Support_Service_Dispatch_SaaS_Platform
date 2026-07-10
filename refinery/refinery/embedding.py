"""embed() — 與 rag 檢索共用同一 embedding 模型(CR-0140 D3)。

一致性鐵律:Publisher 灌入與 rag 查詢必須同模型,故共用 `RAG_EMBED_MODEL` env
(預設 vertex_ai/text-multilingual-embedding-002,768 維;CR-0124 勘誤後正典)。
"""

import os
from pathlib import Path

EMBED_DIM = 768
DEFAULT_MODEL = "vertex_ai/text-multilingual-embedding-002"

_ROOT = Path(__file__).resolve().parents[2]


def _ensure_credentials() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        for cand in (_ROOT / "credentials.json", _ROOT / "agent" / "credentials.json",
                     Path("/app/credentials.json")):
            if cand.exists():
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cand)
                break
    if not os.getenv("VERTEX_PROJECT") and os.getenv("VERTEX_PROJECT_ID"):
        os.environ["VERTEX_PROJECT"] = os.getenv("VERTEX_PROJECT_ID")


def embed_model() -> str:
    return os.getenv("RAG_EMBED_MODEL", DEFAULT_MODEL)


def embed(text: str) -> list[float]:
    """單文本 embedding;維度 768(DB vector(768) 對齊)。"""
    import litellm

    _ensure_credentials()
    resp = litellm.embedding(model=embed_model(), input=[text])
    vec = resp.data[0]["embedding"]
    if len(vec) != EMBED_DIM:
        raise RuntimeError(f"embedding 維度 {len(vec)} != {EMBED_DIM}(模型 {embed_model()}）")
    return vec
