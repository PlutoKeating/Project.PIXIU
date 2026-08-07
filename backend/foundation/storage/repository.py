"""PIXIU Foundation — SQLite 仓储实现

基于 aiosqlite 实现全部 Repository ABC 接口。
每个类接收 aiosqlite.Connection，方法返回类型与 ABC 完全一致。
JSON 字段使用 json.dumps/loads 序列化。
"""

from __future__ import annotations

import json
import time
from typing import Optional

import aiosqlite

from ..core.models import (
    ConflictRecord,
    Entity,
    Evidence,
    KnowledgeItem,
    KnowledgeStatus,
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
        field=row["field"],
        old_value=json.loads(row["old_value"]),
        new_value=json.loads(row["new_value"]),
        resolution=row["resolution"],
        created_at=row["created_at"],
    )


# ══════════════════════════════════════════════════════════
# EvidenceRepository
# ══════════════════════════════════════════════════════════

class SqliteEvidenceRepo(EvidenceRepository):
    """证据仓储 — SQLite 实现。

    实现 EvidenceRepository 契约的全部方法：save / get / list_by_scope。
    JSON 字段使用 json.dumps/loads 序列化，所有 SQL 使用参数化查询。
    """

    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def save(self, evidence: Evidence) -> str:
        await self._db.execute(
            """INSERT OR REPLACE INTO evidence (id, source_type, raw, quality_score,
               sensitivity, scope, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                evidence.id,
                evidence.source_type.value,
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

    async def list_by_scope(self, scope: str, limit: int = 50) -> list[Evidence]:
        cursor = await self._db.execute(
            "SELECT * FROM evidence WHERE scope = ? ORDER BY created_at DESC LIMIT ?",
            (scope, limit),
        )
        rows = await cursor.fetchall()
        return [_row_to_evidence(r) for r in rows]


def _knowledge_search_text(item: KnowledgeItem) -> str:
    """生成 FTS 可搜索文本的明确规则。

    规则：title + body 文本。
    - body 为 dict 且含 description 字段时，取 description 值。
    - 否则将整个 body 序列化为 JSON 文本。
    """
    parts = [item.title]
    if isinstance(item.body, dict):
        desc = item.body.get("description")
        parts.append(str(desc) if desc else json.dumps(item.body, ensure_ascii=False))
    else:
        parts.append(str(item.body))
    return " ".join(parts)


# ══════════════════════════════════════════════════════════
# KnowledgeRepository
# ══════════════════════════════════════════════════════════

class SqliteKnowledgeRepo(KnowledgeRepository):
    """知识条目仓储 — SQLite 实现（含 FTS5 全文索引）。

    实现 KnowledgeRepository 契约全部方法。
    save 在同一事务中写入 knowledge_items + knowledge_evidence + knowledge_fts，
    任一步失败全部回滚。
    """

    def __init__(self, db: aiosqlite.Connection):
        self._db = db
        self._fts_ready = False
        self._vec_ready = False

    async def _ensure_fts(self) -> None:
        """惰性创建 knowledge_fts 表（幂等，仅首次调用执行）。"""
        if not self._fts_ready:
            await self._db.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5("
                "title, body_text, tokenize='trigram')"
            )
            await self._db.commit()
            self._fts_ready = True

    async def _ensure_vec(self) -> None:
        """惰性创建 knowledge_vec 表（幂等，仅首次调用执行）。"""
        if not self._vec_ready:
            await self._db.execute(
                """CREATE TABLE IF NOT EXISTS knowledge_vec (
                    knowledge_id TEXT PRIMARY KEY,
                    dim          INTEGER NOT NULL,
                    vec          BLOB NOT NULL,
                    FOREIGN KEY (knowledge_id)
                        REFERENCES knowledge_items(id) ON DELETE CASCADE
                )"""
            )
            await self._db.commit()
            self._vec_ready = True

    async def save(self, item: KnowledgeItem) -> str:
        """事务性保存：knowledge_items + knowledge_evidence + knowledge_fts。

        使用 UPSERT（ON CONFLICT DO UPDATE）保持 rowid 稳定，
        保证 FTS rowid 与内容表 rowid 始终一致。
        任一步失败则回滚整个事务。
        """
        await self._ensure_fts()
        try:
            await self._db.execute(
                """INSERT INTO knowledge_items (id, kind, title, body, status,
                   version, scope, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       kind=excluded.kind, title=excluded.title, body=excluded.body,
                       status=excluded.status, version=excluded.version,
                       scope=excluded.scope, updated_at=excluded.updated_at""",
                (
                    item.id,
                    item.kind.value,
                    item.title,
                    json.dumps(item.body, ensure_ascii=False),
                    item.status.value,
                    item.version,
                    item.scope,
                    item.created_at,
                    item.updated_at,
                ),
            )

            # 同一事务内写证据关联
            if item.evidence_ids:
                await self._db.executemany(
                    "INSERT OR IGNORE INTO knowledge_evidence (knowledge_id, evidence_id) VALUES (?, ?)",
                    [(item.id, eid) for eid in item.evidence_ids],
                )

            # 同一事务内同步 FTS 索引（rowid = knowledge_items 的稳定 rowid）
            cursor = await self._db.execute(
                "SELECT rowid FROM knowledge_items WHERE id = ?", (item.id,)
            )
            row = await cursor.fetchone()
            if row is None:
                raise RuntimeError(f"knowledge_items row not found after upsert: {item.id}")
            search_text = _knowledge_search_text(item)
            await self._db.execute(
                "INSERT OR REPLACE INTO knowledge_fts(rowid, title, body_text) VALUES (?, ?, ?)",
                (row["rowid"], item.title, search_text),
            )

            await self._db.commit()
            return item.id
        except Exception:
            await self._db.rollback()
            raise

    async def get(self, id: str) -> Optional[KnowledgeItem]:
        cursor = await self._db.execute("SELECT * FROM knowledge_items WHERE id = ?", (id,))
        row = await cursor.fetchone()
        return _row_to_knowledge(row) if row else None

    async def search_fts(self, query: str, limit: int = 20) -> list[KnowledgeItem]:
        """FTS5 全文检索，返回 KnowledgeItem 列表（不暴露 SQLite row）。"""
        await self._ensure_fts()
        cursor = await self._db.execute(
            """SELECT k.* FROM knowledge_items k
               JOIN knowledge_fts f ON k.rowid = f.rowid
               WHERE knowledge_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit),
        )
        rows = await cursor.fetchall()
        return [_row_to_knowledge(r) for r in rows]

    async def search_by_title(self, query: str, limit: int = 20) -> list[KnowledgeItem]:
        """按 title 子串模糊匹配（用于遗忘定位）。"""
        cursor = await self._db.execute(
            """SELECT * FROM knowledge_items
               WHERE title LIKE ? ESCAPE '\\'
               ORDER BY updated_at DESC
               LIMIT ?""",
            (f"%{_escape_like(query)}%", limit),
        )
        rows = await cursor.fetchall()
        return [_row_to_knowledge(r) for r in rows]

    async def save_vector(self, knowledge_id: str, dim: int, vec: bytes) -> None:
        """保存知识条目的向量（仅存储，不做 ANN 检索）。"""
        await self._ensure_vec()
        await self._db.execute(
            """INSERT OR REPLACE INTO knowledge_vec (knowledge_id, dim, vec)
               VALUES (?, ?, ?)""",
            (knowledge_id, dim, vec),
        )
        await self._db.commit()

    async def update_status(self, id: str, status: KnowledgeStatus) -> None:
        """更新知识条目状态（e.g. ACTIVE → FORGOTTEN）。"""
        await self._db.execute(
            "UPDATE knowledge_items SET status = ? WHERE id = ?",
            (status.value, id),
        )
        await self._db.commit()

    async def link_evidence(self, knowledge_id: str, evidence_id: str) -> None:
        await self._db.execute(
            "INSERT OR IGNORE INTO knowledge_evidence (knowledge_id, evidence_id) VALUES (?, ?)",
            (knowledge_id, evidence_id),
        )
        await self._db.commit()

    async def list_active(self) -> list[KnowledgeItem]:
        """列出全部 ACTIVE 知识条目（引擎冲突仲裁/遗忘定位使用）。"""
        cursor = await self._db.execute(
            "SELECT * FROM knowledge_items WHERE status = ? ORDER BY updated_at DESC",
            (KnowledgeStatus.ACTIVE.value,),
        )
        rows = await cursor.fetchall()
        return [_row_to_knowledge(r) for r in rows]


def _escape_like(value: str) -> str:
    """转义 LIKE 通配符，防止用户输入注入模式。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ══════════════════════════════════════════════════════════
# PreferenceRepository
# ══════════════════════════════════════════════════════════

class SqlitePreferenceRepo(PreferenceRepository):
    """偏好仓储 — SQLite 实现（含版本快照）。"""

    def __init__(self, db: aiosqlite.Connection):
        self._db = db

    async def save(self, pref: Preference) -> str:
        """版本化保存：同 key+scope 复用稳定 id，version+1，旧版本写入历史快照。

        首次保存以调用方传入的 id/version 为准；后续保存由仓储统一管理版本。
        """
        existing = await self.get_by_key(pref.key, pref.scope)
        if existing is not None:
            # 旧版本先入历史
            await self._db.execute(
                "INSERT OR REPLACE INTO preference_history (pref_id, version, snapshot, ts) "
                "VALUES (?, ?, ?, ?)",
                (
                    existing.id,
                    existing.version,
                    json.dumps(existing.value, ensure_ascii=False),
                    existing.updated_at,
                ),
            )
            effective = pref.model_copy(
                update={
                    "id": existing.id,
                    "version": existing.version + 1,
                    "created_at": existing.created_at,
                    "updated_at": int(time.time()),
                }
            )
        else:
            effective = pref

        await self._db.execute(
            """INSERT INTO preferences (id, category, key, value, confidence,
               version, scope, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   category=excluded.category, key=excluded.key, value=excluded.value,
                   confidence=excluded.confidence, version=excluded.version,
                   scope=excluded.scope, updated_at=excluded.updated_at""",
            (
                effective.id,
                effective.category,
                effective.key,
                json.dumps(effective.value, ensure_ascii=False),
                effective.confidence,
                effective.version,
                effective.scope,
                effective.created_at,
                effective.updated_at,
            ),
        )
        await self._db.commit()
        return effective.id

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
        snapshots = [
            PreferenceSnapshot(
                version=r["version"],
                value=json.loads(r["snapshot"]),
                updated_at=r["ts"],
            )
            for r in rows
        ]
        # API 契约：history 含当前版本（旧快照 + 最新值），按版本升序
        current = await self.get(pref_id)
        if current is not None and not any(s.version == current.version for s in snapshots):
            snapshots.append(
                PreferenceSnapshot(
                    version=current.version,
                    value=dict(current.value),
                    updated_at=current.updated_at,
                )
            )
            snapshots.sort(key=lambda s: s.version)
        return snapshots

    async def get_by_key(self, key: str, scope: str) -> Optional[Preference]:
        """按 key + scope 获取偏好（版本化定位，供 save 时决定是否递增版本）。"""
        cursor = await self._db.execute(
            "SELECT * FROM preferences WHERE key = ? AND scope = ? ORDER BY version DESC LIMIT 1",
            (key, scope),
        )
        row = await cursor.fetchone()
        return _row_to_preference(row) if row else None

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

    async def list_relations(self) -> list[Relation]:
        """列出全部关系（引擎遗忘级联统计使用）。"""
        cursor = await self._db.execute("SELECT * FROM relations")
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
