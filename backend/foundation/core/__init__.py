"""PIXIU Foundation — 共享契约包

导出所有数据模型、抽象接口、配置、ID 生成器和日志工具，
供 Module B（引擎）和 Module C（基础设施）共同引用。
"""

from .config import settings
from .models import (
    ConflictRecord,
    ConflictResolution,
    Entity,
    Evidence,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeStatus,
    MemoryAtom,
    Preference,
    PreferenceCategory,
    PreferenceSnapshot,
    Relation,
    SourceType,
    SyncOp,
)
from .repository import (
    ConflictRepository,
    EntityRepository,
    EvidenceRepository,
    KnowledgeRepository,
    PreferenceRepository,
)
from .idgen import (
    gen_conflict_id,
    gen_device_id,
    gen_entity_id,
    gen_evidence_id,
    gen_knowledge_id,
    gen_pref_id,
    gen_request_id,
    gen_sync_op_id,
)
from .logger import get_logger
from .vector_store import VectorMatch, VectorStore

__all__ = [
    # config
    "settings",
    # models
    "ConflictRecord",
    "ConflictResolution",
    "Entity",
    "Evidence",
    "KnowledgeItem",
    "KnowledgeKind",
    "KnowledgeStatus",
    "MemoryAtom",
    "Preference",
    "PreferenceCategory",
    "PreferenceSnapshot",
    "Relation",
    "SourceType",
    "SyncOp",
    # repository ABCs
    "ConflictRepository",
    "EntityRepository",
    "EvidenceRepository",
    "KnowledgeRepository",
    "PreferenceRepository",
    # idgen
    "gen_evidence_id",
    "gen_knowledge_id",
    "gen_pref_id",
    "gen_conflict_id",
    "gen_device_id",
    "gen_sync_op_id",
    "gen_entity_id",
    "gen_request_id",
    # logger
    "get_logger",
    # vector storage seam
    "VectorMatch",
    "VectorStore",
]
