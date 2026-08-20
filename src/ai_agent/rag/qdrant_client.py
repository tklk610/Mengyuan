"""Qdrant 向量数据库客户端

提供风格特征向量的存储和检索功能
"""
from __future__ import annotations

from typing import Any

import structlog
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams

from ai_agent.config.settings import settings

logger = structlog.get_logger(__name__)


class QdrantStore:
    """Qdrant 向量存储客户端"""

    COLLECTION_NAME = settings.qdrant_collection
    VECTOR_SIZE = 1536  # OpenAI embedding dimension

    def __init__(self) -> None:
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        """延迟初始化 Qdrant 客户端"""
        if self._client is None:
            self._client = QdrantClient(
                url=settings.qdrant_url,
                timeout=10.0,
            )
        return self._client

    def ensure_collection(self) -> None:
        """确保 collection 存在，不存在则创建"""
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]

            if self.COLLECTION_NAME not in collection_names:
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("qdrant.collection.created", collection=self.COLLECTION_NAME)
            else:
                logger.info("qdrant.collection.exists", collection=self.COLLECTION_NAME)

        except UnexpectedResponse as e:
            logger.error("qdrant.connection.failed", error=str(e), url=settings.qdrant_url)
            raise

    def upsert_style_profile(
        self,
        user_id: str,
        profile_id: str,
        name: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        """存储风格档案向量

        Args:
            user_id: 用户 ID
            profile_id: 风格档案 ID
            name: 风格名称
            vector: 风格特征向量
            payload: 额外数据（genre_tags, characteristics 等）
        """
        self.ensure_collection()

        point = models.PointStruct(
            id=profile_id,
            vector=vector,
            payload={
                "user_id": user_id,
                "name": name,
                **payload,
            },
        )

        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[point],
        )
        logger.info("qdrant.style_profile.upserted", user_id=user_id, profile_id=profile_id)

    def search_similar_styles(
        self,
        query_vector: list[float],
        user_id: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """检索相似风格档案

        Args:
            query_vector: 查询向量
            user_id: 用户 ID（过滤该用户的风格档案）
            limit: 返回数量

        Returns:
            相似风格档案列表
        """
        self.ensure_collection()

        results = self.client.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id",
                        match=models.MatchValue(value=user_id),
                    )
                ]
            ),
            limit=limit,
        )

        return [
            {
                "id": result.id,
                "score": result.score,
                "name": result.payload.get("name"),
                "genre_tags": result.payload.get("genre_tags"),
                "characteristics": result.payload.get("characteristics"),
            }
            for result in results
        ]

    def delete_style_profile(self, profile_id: str) -> None:
        """删除风格档案

        Args:
            profile_id: 风格档案 ID
        """
        self.client.delete(
            collection_name=self.COLLECTION_NAME,
            points_selector=models.PointIdsList(points=[profile_id]),
        )
        logger.info("qdrant.style_profile.deleted", profile_id=profile_id)

    def list_style_profiles(self, user_id: str) -> list[dict[str, Any]]:
        """列出用户所有风格档案

        Args:
            user_id: 用户 ID

        Returns:
            风格档案列表
        """
        self.ensure_collection()

        results = self.client.scroll(
            collection_name=self.COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id",
                        match=models.MatchValue(value=user_id),
                    )
                ]
            ),
            limit=100,
        )

        return [
            {
                "id": point.id,
                "name": point.payload.get("name"),
                "genre_tags": point.payload.get("genre_tags"),
                "characteristics": point.payload.get("characteristics"),
            }
            for point in results[0]
        ]


# === Global Instance ===
qdrant_store = QdrantStore()
