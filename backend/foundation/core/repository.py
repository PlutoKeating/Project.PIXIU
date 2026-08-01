"""PIXIU Foundation — Repository 抽象接口 (ABC)

本文件定义 Module B（引擎）与 Module C（基础设施）之间的存储层契约。
Module B 只消费这些接口，Module C 在 `storage/` 中实现它们。

契约定义见 `docs/DEVELOPMENT_PLAN.md` §3.2。

接口设计原则：
  - 所有 I/O 方法使用 async def。
  - 参数和返回值使用 core/models.py 中的 Pydantic 模型。
  - 不导入任何具体数据库实现。
  - 不暴露表名、SQL、连接或游标。
  - 仅包含已冻结的方法；未冻结接口见最终报告。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .models import (
    ConflictRecord,
    Entity,
    Evidence,
    KnowledgeItem,
    KnowledgeStatus,
    Preference,
    PreferenceCategory,
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
    async def list_by_scope(self, scope: str, limit: int) -> list[Evidence]:
        """按 scope 列出证据，按创建时间降序。"""
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
    async def search_fts(self, query: str, limit: int) -> list[KnowledgeItem]:
        """全文检索。"""
        ...

    @abstractmethod
    async def search_by_title(self, query: str, limit: int) -> list[KnowledgeItem]:
        """按 title 模糊匹配知识条目（用于遗忘定位）。"""
        ...

    @abstractmethod
    async def save_vector(self, knowledge_id: str, dim: int, vec: bytes) -> None:
        """保存知识条目的向量（三索引齐写之一）。"""
        ...

    @abstractmethod
    async def update_status(self, id: str, status: KnowledgeStatus) -> None:
        """更新知识条目状态（e.g. ACTIVE → FORGOTTEN）。"""
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
        """获取某实体的全部关联关系（入边 + 出边）。"""
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
    async def list(self) -> list[ConflictRecord]:
        """列出全部冲突记录。"""
        ...
