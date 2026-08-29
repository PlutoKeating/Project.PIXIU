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

    async def get_many(self, ids: list[str]) -> list[Evidence]:
        """按 id 批量获取证据（顺序与 ids 一致，缺失 id 跳过）。

        洞察流等批量解析场景使用，替代逐 id 调 get() 的 N+1 查询。
        默认抛 NotImplementedError；存储层实现应使用单条
        ``WHERE id IN (...)`` 批量查询（镜像 flow/store.py 的 get_many 模式）。
        """
        raise NotImplementedError(
            "get_many is not implemented by this repository"
        )

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

    @abstractmethod
    async def list_active(self) -> list[KnowledgeItem]:
        """列出全部 ACTIVE 状态的知识条目（引擎冲突仲裁/遗忘定位使用）。"""
        ...

    async def list_recent(
        self,
        scope: str,
        since_ts: int | None = None,
        limit: int | None = 50,
    ) -> list[KnowledgeItem]:
        """按 scope 列出最近入库的 ACTIVE 知识条目（created_at 降序）。

        窗口（since_ts）与 limit 过滤下沉到存储层单条 SQL，洞察流等窗口型
        查询使用，避免先全量 list_active() 再内存过滤。limit=None 表示不限制
        数量（质量重排需要窗口内全部候选）。
        默认抛 NotImplementedError；存储层实现应把 scope/status/窗口/limit
        过滤写入单条 SQL。
        """
        raise NotImplementedError(
            "list_recent is not implemented by this repository"
        )

    @abstractmethod
    async def list_vectors(self) -> list[tuple[str, int, bytes]]:
        """列出全部知识向量的 (knowledge_id, dim, vec_bytes)（检索 ANN 通道使用）。"""
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
    async def get_by_key(self, key: str, scope: str) -> Optional[Preference]:
        """按 key + scope 获取偏好（版本化定位，供 save 时决定是否递增版本）。"""
        ...

    @abstractmethod
    async def list(self, scope: str | None = None, limit: int = 100) -> list[Preference]:
        """列出偏好。可选按 scope 过滤，按更新时间降序。"""
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

    @abstractmethod
    async def find_entity_by_name(self, name: str) -> Optional[Entity]:
        """按规范化名称查找实体（引擎建图时用于解析已有实体 id）。"""
        ...

    @abstractmethod
    async def list_relations(self) -> list[Relation]:
        """列出全部关系（引擎遗忘级联统计使用）。"""
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
