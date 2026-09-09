"""Private document staging. Opaque references grant access to one upload only.

Registration accepts bytes from trusted product entrypoints, never a model path.
Reading a block proves delivery, not model understanding or successful ingestion.
"""
from dataclasses import asdict
import json
import secrets
import time

from .decode import DecodedDocument


class DocumentUnavailable(ValueError):
    pass


class DocumentRegistry:
    def __init__(self, db):
        self.db = db

    async def register(self, document: DecodedDocument) -> dict:
        reference = secrets.token_hex(32)
        now = int(time.time())
        payload = json.dumps(asdict(document), ensure_ascii=False)
        if len(payload.encode()) > 100 * 1024 * 1024:
            raise ValueError("Decoded document exceeds the supported size")
        await self.db.execute("DELETE FROM document_inputs WHERE expires_at <= ?", (now,))
        await self.db.execute(
            "INSERT INTO document_inputs (id, payload, expires_at) VALUES (?, ?, ?)",
            (reference, payload, now + 86400),
        )
        await self.db.commit()
        return self._describe(reference, json.loads(payload))

    async def _get(self, reference):
        cursor = await self.db.execute(
            "SELECT payload FROM document_inputs WHERE id = ? AND expires_at > ?",
            (reference, int(time.time())),
        )
        row = await cursor.fetchone()
        if row is None:
            raise DocumentUnavailable("Document reference is unavailable or expired")
        return json.loads(row[0])

    @staticmethod
    def _describe(reference, document):
        return {
            "document_id": reference, "name": document["name"], "version": document["version"],
            "blocks": [{key: block[key] for key in ("id", "kind", "location")} for block in document["blocks"]],
            "warnings": document["warnings"],
            "decoding_complete": bool(document["blocks"]) and not document["warnings"],
        }

    async def describe(self, reference):
        return self._describe(reference, await self._get(reference))

    async def read(self, reference, cursor=0):
        document = await self._get(reference)
        if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0 or cursor >= len(document["blocks"]):
            raise ValueError("Invalid document cursor")
        return {"document_id": reference, "version": document["version"],
                "block": document["blocks"][cursor],
                "next_cursor": cursor + 1 if cursor + 1 < len(document["blocks"]) else None}

    async def revoke(self, reference):
        await self.db.execute("DELETE FROM document_inputs WHERE id = ?", (reference,))
        await self.db.commit()
