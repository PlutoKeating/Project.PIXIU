"""PIXIU Foundation — 存储层

导出 SQLite Repository 实现类、Schema 初始化和迁移工具。
"""

from .idempotency import AgentIngestReceiptStore
from .migrations import apply_pending, latest_version
from .repository import (
    SqliteConflictRepo,
    SqliteEntityRepo,
    SqliteEvidenceRepo,
    SqliteKnowledgeRepo,
    SqlitePreferenceRepo,
)
from .schema import (
    create_connection,
    ensure_knowledge_fts,
    ensure_knowledge_vec,
    init_db,
    init_db_on_connection,
)
from .vector_store import SqliteVectorStore
from .vector_id_map import SqliteVectorIdMap

__all__ = [
    # repos
    "SqliteEvidenceRepo",
    "SqliteKnowledgeRepo",
    "SqlitePreferenceRepo",
    "SqliteEntityRepo",
    "SqliteConflictRepo",
    "SqliteVectorStore",
    "SqliteVectorIdMap",
    "AgentIngestReceiptStore",
    # schema
    "create_connection",
    "ensure_knowledge_fts",
    "ensure_knowledge_vec",
    "init_db",
    "init_db_on_connection",
    # migrations
    "apply_pending",
    "latest_version",
]
