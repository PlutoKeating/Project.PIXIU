import aiosqlite
import pytest

from backend.foundation.documents import decode_document
from backend.foundation.documents.registry import DocumentRegistry, DocumentUnavailable
from backend.foundation.storage.schema import DOCUMENT_INPUTS_DDL


@pytest.mark.asyncio
async def test_registry_persists_full_content_and_revokes_access(tmp_path):
    path = tmp_path / "documents.db"
    original = "完整工作记录" * 10000
    async with aiosqlite.connect(path) as db:
        await db.execute(DOCUMENT_INPUTS_DDL)
        entry = await DocumentRegistry(db).register(decode_document(original.encode(), "工作.txt"))
        reference = entry["document_id"]
        assert entry["decoding_complete"]
        assert len(reference) == 64
    async with aiosqlite.connect(path) as db:
        registry = DocumentRegistry(db)
        cursor = 0
        reconstructed = []
        while cursor is not None:
            page = await registry.read(reference, cursor)
            reconstructed.append(page["block"]["text"])
            cursor = page["next_cursor"]
        assert "".join(reconstructed) == original
        with pytest.raises(DocumentUnavailable):
            await registry.read("unknown")
        with pytest.raises(ValueError):
            await registry.read(reference, -1)
        await registry.revoke(reference)
        with pytest.raises(DocumentUnavailable):
            await registry.describe(reference)


@pytest.mark.asyncio
async def test_expired_reference_cannot_read_original_document():
    async with aiosqlite.connect(":memory:") as db:
        await db.execute(DOCUMENT_INPUTS_DDL)
        registry = DocumentRegistry(db)
        entry = await registry.register(decode_document(b"secret", "private.txt"))
        await db.execute("UPDATE document_inputs SET expires_at = 0")
        with pytest.raises(DocumentUnavailable):
            await registry.read(entry["document_id"])
        await registry.register(decode_document(b"next", "next.txt"))
        cursor = await db.execute("SELECT count(*) FROM document_inputs")
        assert (await cursor.fetchone())[0] == 1


@pytest.mark.asyncio
async def test_directory_revocation_invalidates_existing_document_reference():
    authorized = True
    async with aiosqlite.connect(":memory:") as db:
        await db.execute(DOCUMENT_INPUTS_DDL)
        registry = DocumentRegistry(db, lambda path: authorized)
        entry = await registry.register(decode_document(b"work", "work.txt"), "/authorized/work.txt")
        assert "source_path" not in entry
        authorized = False
        with pytest.raises(DocumentUnavailable, match="revoked"):
            await registry.read(entry["document_id"])
