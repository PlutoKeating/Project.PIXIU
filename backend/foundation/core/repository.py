"""PIXIU Foundation — Repository 抽象接口 (ABC)

本文件定义 Module B（引擎）与 Module C（基础设施）之间的存储层契约。
Module B 只消费这些接口，Module C 在 `storage/` 中实现它们。

契约定义见 `docs/DEVELOPMENT_PLAN.md` §3.2。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .models import (
    ConflictRecord,
    Entity,
    Evidence,
    KnowledgeItem,
    Preference,
    PreferenceSnapshot,
    Relation,
)


class EvidenceRepository(ABC):
    """原始证据仓储。"""

    @abstractmethod
    async def save(self, evidence: Evidence) -> str:
        """持久化一条证据，返回证据 id。"""
        ...

    @abstractmethod
    async def get(self, id: str) -> Optional[Evidence]:
        """按 id 获取证据。"""
        ...

    @abstractmethod
    async def delete(self, id: str) -> None:
        """删除证据。"""
        ...

    @abstractmethod
    async def list_by_scope(self, scope: str, offset: int = 0, limit: int = 50) -> list[Evidence]:
        """按 scope 分页列出证据。"""
        ...


class KnowledgeRepository(ABC):
    """知识条目仓储。"""

    @abstractmethod
    async def save(self, item: KnowledgeItem) -> str:
        """持久化一条知识，返回 id。"""
        ...

    @abstractmethod
    async def get(self, id: str) -> Optional[KnowledgeItem]:
        """按 id 获取知识条目。"""
        ...

    @abstractmethod
    async def delete(self, id: str) -> None:
        """级联删除知识条目及其关联。"""
        ...

    @abstractmethod
    async def search_fts(self, query: str, limit: int = 20) -> list[KnowledgeItem]:
        """FTS5 全文检索。"""
        ...

    @abstractmethod
    async def list_by_status(self, status: str) -> list[KnowledgeItem]:
        """按状态过滤知识条目。"""
        ...

    @abstractmethod
    async def link_evidence(self, knowledge_id: str, evidence_id: str) -> None:
        """关联证据到知识条目。"""
        ...


class PreferenceRepository(ABC):
    """偏好仓储。"""

    @abstractmethod
    async def save(self, pref: Preference) -> str:
        """持久化偏好，返回 id。"""
        ...

    @abstractmethod
    async def get(self, id: str) -> Optional[Preference]:
        """按 id 获取偏好。"""
        ...

    @abstractmethod
    async def get_history(self, pref_id: str) -> list[PreferenceSnapshot]:
        """获取偏好的全部历史版本快照。"""
        ...

    @abstractmethod
    async def list_by_category(self, category: str) -> list[Preference]:
        """按类别列出偏好。"""
        ...


class EntityRepository(ABC):
    """实体-关系图仓储。"""

    @abstractmethod
    async def save_entity(self, entity: Entity) -> str:
        """持久化实体，返回 id。"""
        ...

    @abstractmethod
    async def get_entity(self, id: str) -> Optional[Entity]:
        """按 id 获取实体。"""
        ...

    @abstractmethod
    async def save_relation(self, src: str, dst: str, type: str) -> None:
        """保存一条关系。"""
        ...

    @abstractmethod
    async def get_relations(self, entity_id: str) -> list[Relation]:
        """获取某实体的全部出边关系。"""
        ...

    @abstractmethod
    async def find_entity_by_name(self, name: str) -> Optional[Entity]:
        """按 norm_name 查找实体。"""
        ...


class ConflictRepository(ABC):
    """冲突审计仓储。"""

    @abstractmethod
    async def save(self, record: ConflictRecord) -> str:
        """持久化冲突记录，返回 id。"""
        ...

    @abstractmethod
    async def get(self, id: str) -> Optional[ConflictRecord]:
        """按 id 获取冲突记录。"""
        ...

    @abstractmethod
    async def list(self, since: Optional[int] = None, limit: int = 50) -> list[ConflictRecord]:
        """列出冲突记录，可按时间戳过滤。"""
        ...

    @abstractmethod
    async def resolve(self, id: str, resolution: str) -> None:
        """更新冲突裁决结果。"""
        ...
