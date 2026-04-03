import asyncio
import json
import os
import re
from functools import partial
from langchain_postgres import PGVector
from .base_retriever import BaseRetriever

from embeddings import get_embedding

UI_METADATA_DELIMITER = "\n===UI_METADATA===\n"


class PGVectorRetriever(BaseRetriever):
    def setup(self):
        self.collection_name = self.config.get("collection_name", self.config["name"])
        self.top_k = self.config.get("top_k", 2)
        self.strip_keywords = self.config.get("query_strip_keywords", [])

        connection_uri_env = self.config.get("connection_uri_env", "PG_VECTOR_URI")
        connection_uri = os.environ.get(connection_uri_env)
        if not connection_uri:
            raise ValueError(
                f"環境變數 {connection_uri_env} 未設定，"
                f"請在 .env 中設定 PostgreSQL 連線字串"
            )

        embed_fn = get_embedding(self.config)

        print(f"[*] 初始化 PGVector: collection={self.collection_name}...")

        self.vector_store = PGVector(
            embeddings=embed_fn,
            collection_name=self.collection_name,
            connection=connection_uri,
        )

        # 維度校驗
        expected_dim = self.config.get("embedding_dimensions")
        if expected_dim:
            test_vector = embed_fn.embed_query("test")
            actual_dim = len(test_vector)
            if actual_dim != expected_dim:
                raise ValueError(
                    f"Embedding 維度不符：預期 {expected_dim}，實際 {actual_dim}"
                )
            print(f"[*] 維度驗證通過: {actual_dim}")

    def _clean_query(self, question: str) -> str:
        """移除 query 中的高頻品牌名等噪音詞，讓向量搜尋聚焦操作語義。"""
        if not self.strip_keywords:
            return question
        cleaned = question
        for kw in self.strip_keywords:
            cleaned = re.sub(re.escape(kw), "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or question

    async def aretrieve(self, question: str) -> str:
        search_query = self._clean_query(question)
        if search_query != question:
            print(f"  [Query 清洗] '{question}' → '{search_query}'")

        loop = asyncio.get_event_loop()
        # MMR + score gating: 先用 similarity_search_with_score 取得帶分數的結果，
        # 過濾低於閾值的結果後，再依分數排序取 top_k
        score_threshold = self.config.get("score_threshold", 0.85)
        raw_results = await loop.run_in_executor(
            None,
            partial(
                self.vector_store.similarity_search_with_score,
                search_query,
                k=self.top_k * 3,  # fetch more candidates for filtering
            ),
        )

        # pgvector distance: lower = more similar (L2/cosine distance)
        # LangChain PGVector returns (doc, distance), convert to similarity
        scored_docs = []
        for doc, distance in raw_results:
            similarity = 1.0 - distance  # cosine distance → cosine similarity
            scored_docs.append((doc, similarity))

        # Filter by score threshold and take top_k
        passed = [(doc, score) for doc, score in scored_docs if score >= score_threshold]
        passed.sort(key=lambda x: x[1], reverse=True)
        docs = [doc for doc, _ in passed[:self.top_k]]

        if passed:
            top_score = passed[0][1]
            print(f"  [Score Gate] {len(passed)}/{len(raw_results)} docs passed "
                  f"(threshold={score_threshold}, top={top_score:.3f})")
        else:
            print(f"  [Score Gate] 0/{len(raw_results)} docs passed "
                  f"(threshold={score_threshold})")
            return "RETRIEVAL_LOW_CONFIDENCE"

        context = "\n---\n".join([doc.page_content for doc in docs])
        if not context:
            return "RETRIEVAL_LOW_CONFIDENCE"

        # 當 ui_type 非 TEXT 時，在尾部附加 metadata JSON
        ui_type = self.config.get("ui_type", "TEXT")
        if ui_type != "TEXT":
            metadata_list = [doc.metadata for doc in docs]
            metadata_block = json.dumps(
                {"ui_type": ui_type, "items": metadata_list},
                ensure_ascii=False,
            )
            context += UI_METADATA_DELIMITER + metadata_block

        return context
