"""PIXIU Foundation — SQLite 仓储实现

基于 aiosqlite 实现全部 Repository ABC 接口。
每个类接收 aiosqlite.Connection，方法返回类型与 ABC 完全一致。
JSON 字段使用 json.dumps/loads 序列化。
"""

from __future__ import annotations

import json
from typing import Optional

import aiosqlite

from ..core.models import (
    ConflictRecord,
    Entity,
    Evidence,
    KnowledgeItem,
    Preference,
    PreferenceSnapshot,
    Relation,
)
from ..core.repository import (
    ConflictRepository,
    EntityRepository,
    EvidenceRepository,
    KnowledgeRepository,
    PreferenceRepository,
)


def _row_to_evidence(row: aiosqlite.Row) -> Evidence:
    return Evidence(
        id=row["id"],
        source_type=row["source_type"],
        raw=json.loads(row["raw"]),
        quality_score=row["quality_score"],
        sensitivity=row["sensitivity"],
        scope=row["scope"],
        created_at=row["created_at"],
    )


def _row_to_knowledge(row: aiosqlite.Row) -> KnowledgeItem:
    return KnowledgeItem(
        id=row["id"],
        kind=row["kind"],
        title=row["title"],
        body=json.loads(row["body"]),
        status=row["status"],
        version=row["version"],
        scope=row["scope"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_preference(row: aiosqlite.Row) -> Preference:
    return Preference(
        id=row["id"],
        category=row["category"],
        key=row["key"],
        value=json.loads(row["value"]),
        confidence=row["confidence"],
        version=row["version"],
        scope=row["scope"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_entity(row: aiosqlite.Row) -> Entity:
    return Entity(
        id=row["id"],
        name=row["name"],
        norm_name=row["norm_name"],
        type=row["type"],
    )


def _row_to_conflict(row: aiosqlite.Row) -> ConflictRecord:
    return ConflictRecord(
        id=row["id"],
        target_knowledge=row["target_knowledge"],
        field=row.get("field", ""),
        old_value=json.loads(row["old_value"]),
        new_value=json.loads(row["new_value"]),
        resolution=row["resolution"],
        created_at=row["created_at"],
    )


# ══════════════════════════════════════════════════════════
# EvidenceRepository
# ══════════════════════════════════════════════════════════

class SqliteEvidenceRepo(EvidenceRepository):
    """证据仓储 — SQLite 实现。"""

    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def save(self, evidence: Evidence) -> str:
        await self._db.execute(
            """INSERT OR REPLACE INTO evidence (id, source_type, raw, quality_score,
               sensitivity, scope, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                evidence.id,
                evidence.source_type,
                json.dumps(evidence.raw, ensure_ascii=False),
                evidence.quality_score,
                evidence.sensitivity,
                evidence.scope,
                evidence.created_at,
            ),
        )
        await self._db.commit()
        return evidence.id

    async def get(self, id: str) -> Optional[Evidence]:
        cursor = await self._db.execute("SELECT * FROM evidence WHERE id = ?", (id,))
        row = await cursor.fetchone()
        return _row_to_evidence(row) if row else None

    async def delete(self, id: str) -> None:
        await self._db.execute("DELETE FROM evidence WHERE id = ?", (id,))
        await self._db.commit()

    async def list_by_scope(self, scope: str, offset: int = 0, limit: int = 50) -> list[Evidence]:
        cursor = await self._db.execute(
            "SELECT * FROM evidence WHERE scope = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (scope, limit, offset),
        )
        rows = await cursor.fetchall()
        return [_row_to_evidence(r) for r in rows]


# ══════════════════════════════════════════════════════════
# KnowledgeRepository
# ══════════════════════════════════════════════════════════

class SqliteKnowledgeRepo(KnowledgeRepository):
    """知识条目仓储 — SQLite 实现（含 FTS5）。"""

    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def save(self, item: KnowledgeItem) -> str:
        cursor = await self._db.execute(
            """INSERT OR REPLACE INTO knowledge_items (id, kind, title, body,
               status, version, scope, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.id,
                item.kind,
                item.title,
                json.dumps(item.body, ensure_ascii=False),
                item.status,
                item.version,
                item.scope,
                item.created_at,
                item.updated_at,
            ),
        )
        rowid = cursor.lastrowid

        # 同步 FTS5 索引（rowid 必须为整数，匹配 knowledge_items 的内容表 rowid）
        body_text = item.body.get("description", "") if isinstance(item.body, dict) else str(item.body)
        await self._db.execute(
            "INSERT OR REPLACE INTO knowledge_fts(rowid, title, body_text) VALUES (?, ?, ?)",
            (rowid, item.title, body_text),
        )

        await self._db.commit()
        return item.id

    async def get(self, id: str) -> Optional[KnowledgeItem]:
        cursor = await self._db.execute("SELECT * FROM knowledge_items WHERE id = ?", (id,))
        row = await cursor.fetchone()
        return _row_to_knowledge(row) if row else None

    async def delete(self, id: str) -> None:
        await self._db.execute("DELETE FROM knowledge_items WHERE id = ?", (id,))
        await self._db.commit()

    async def search_fts(self, query: str, limit: int = 20) -> list[KnowledgeItem]:
        cursor = await self._db.execute(
            """
            SELECT k.* FROM knowledge_items k
            JOIN knowledge_fts f ON k.rowid = f.rowid
            WHERE knowledge_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )
        rows = await cursor.fetchall()
        return [_row_to_knowledge(r) for r in rows]

    async def list_by_status(self, status: str) -> list[KnowledgeItem]:
        cursor = await self._db.execute(
            "SELECT * FROM knowledge_items WHERE status = ? ORDER BY updated_at DESC", (status,)
        )
        rows = await cursor.fetchall()
        return [_row_to_knowledge(r) for r in rows]

    async def link_evidence(self, knowledge_id: str, evidence_id: str) -> None:
        await self._db.execute(
            "INSERT OR IGNORE INTO knowledge_evidence (knowledge_id, evidence_id) VALUES (?, ?)",
            (knowledge_id, evidence_id),
        )
        await self._db.commit()


# ══════════════════════════════════════════════════════════
# PreferenceRepository
# ══════════════════════════════════════════════════════════

class SqlitePreferenceRepo(PreferenceRepository):
    """偏好仓储 — SQLite 实现（含版本快照）。"""

    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def save(self, pref: Preference) -> str:
        await self._db.execute(
            """INSERT OR REPLACE INTO preferences (id, category, key, value,
               confidence, version, scope, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pref.id,
                pref.category,
                pref.key,
                json.dumps(pref.value, ensure_ascii=False),
                pref.confidence,
                pref.version,
                pref.scope,
                pref.created_at,
                pref.updated_at,
            ),
        )
        # 写历史快照
        await self._db.execute(
            "INSERT OR REPLACE INTO preference_history (pref_id, version, snapshot, ts) VALUES (?, ?, ?, ?)",
            (pref.id, pref.version, json.dumps(pref.value, ensure_ascii=False), pref.updated_at),
        )
        await self._db.commit()
        return pref.id

    async def get(self, id: str) -> Optional[Preference]:
        cursor = await self._db.execute("SELECT * FROM preferences WHERE id = ?", (id,))
        row = await cursor.fetchone()
        return _row_to_preference(row) if row else None

    async def get_history(self, pref_id: str) -> list[PreferenceSnapshot]:
        cursor = await self._db.execute(
            "SELECT version, snapshot, ts FROM preference_history WHERE pref_id = ? ORDER BY version ASC",
            (pref_id,),
        )
        rows = await cursor.fetchall()
        return [
            PreferenceSnapshot(
                version=r["version"],
                value=json.loads(r["snapshot"]),
                updated_at=r["ts"],
            )
            for r in rows
        ]

    async def list_by_category(self, category: str) -> list[Preference]:
        cursor = await self._db.execute(
            "SELECT * FROM preferences WHERE category = ? ORDER BY updated_at DESC", (category,)
        )
        rows = await cursor.fetchall()
        return [_row_to_preference(r) for r in rows]


# ══════════════════════════════════════════════════════════
# EntityRepository
# ══════════════════════════════════════════════════════════

class SqliteEntityRepo(EntityRepository):
    """实体-关系图仓储 — SQLite 实现。"""

    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def save_entity(self, entity: Entity) -> str:
        await self._db.execute(
            "INSERT OR REPLACE INTO entities (id, name, norm_name, type) VALUES (?, ?, ?, ?)",
            (entity.id, entity.name, entity.norm_name, entity.type),
        )
        await self._db.commit()
        return entity.id

    async def get_entity(self, id: str) -> Optional[Entity]:
        cursor = await self._db.execute("SELECT * FROM entities WHERE id = ?", (id,))
        row = await cursor.fetchone()
        return _row_to_entity(row) if row else None

    async def save_relation(self, src: str, dst: str, type: str) -> None:
        await self._db.execute(
            "INSERT OR IGNORE INTO relations (src, dst, type) VALUES (?, ?, ?)", (src, dst, type)
        )
        await self._db.commit()

    async def get_relations(self, entity_id: str) -> list[Relation]:
        cursor = await self._db.execute(
            "SELECT * FROM relations WHERE src = ? OR dst = ?", (entity_id, entity_id)
        )
        rows = await cursor.fetchall()
        return [Relation(src=r["src"], dst=r["dst"], type=r["type"]) for r in rows]

    async def find_entity_by_name(self, name: str) -> Optional[Entity]:
        norm = name.strip().lower()
        cursor = await self._db.execute("SELECT * FROM entities WHERE norm_name = ?", (norm,))
        row = await cursor.fetchone()
        return _row_to_entity(row) if row else None


# ══════════════════════════════════════════════════════════
# ConflictRepository
# ══════════════════════════════════════════════════════════

class SqliteConflictRepo(ConflictRepository):
    """冲突审计仓储 — SQLite 实现。"""

    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def save(self, record: ConflictRecord) -> str:
        await self._db.execute(
            """INSERT OR REPLACE INTO conflict_records (id, target_knowledge,
               field, old_value, new_value, resolution, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id,
                record.target_knowledge,
                record.field,
                json.dumps(record.old_value, ensure_ascii=False),
                json.dumps(record.new_value, ensure_ascii=False),
                record.resolution,
                record.created_at,
            ),
        )
        await self._db.commit()
        return record.id

    async def get(self, id: str) -> Optional[ConflictRecord]:
        cursor = await self._db.execute("SELECT * FROM conflict_records WHERE id = ?", (id,))
        row = await cursor.fetchone()
        return _row_to_conflict(row) if row else None

    async def list(self, since: Optional[int] = None, limit: int = 50) -> list[ConflictRecord]:
        if since is not None:
            cursor = await self._db.execute(
                "SELECT * FROM conflict_records WHERE created_at > ? ORDER BY created_at DESC LIMIT ?",
                (since, limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM conflict_records ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [_row_to_conflict(r) for r in rows]

    async def resolve(self, id: str, resolution: str) -> None:
        await self._db.execute(
            "UPDATE conflict_records SET resolution = ? WHERE id = ?", (resolution, id)
        )
        await self._db.commit()
