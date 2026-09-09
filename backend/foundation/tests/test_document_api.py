import base64

import aiosqlite
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from backend.foundation.api.documents import router
from backend.foundation.api.di import get_db
from backend.foundation.storage.schema import DOCUMENT_INPUTS_DDL


@pytest.mark.asyncio
async def test_upload_read_revoke_and_invalid_file():
    async with aiosqlite.connect(":memory:") as db:
        await db.execute(DOCUMENT_INPUTS_DDL)
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/documents", json={
                "filename": "notes.txt", "file_base64": base64.b64encode(b"meeting notes").decode()})
            assert response.status_code == 200
            document = response.json()
            reference = document["document_id"]
            response = await client.get(f"/documents/{reference}/read")
            assert response.json()["block"]["text"] == "meeting notes"
            assert (await client.get(f"/documents/{reference}/read?cursor=99")).status_code == 422
            assert (await client.delete(f"/documents/{reference}")).status_code == 200
            assert (await client.get(f"/documents/{reference}")).status_code == 404
            response = await client.post("/documents", json={
                "filename": "broken.docx", "file_base64": base64.b64encode(b"not a zip").decode()})
            assert response.status_code == 422
            assert (await client.post("/documents", json={"path": "/etc/passwd"})).status_code == 422


@pytest.mark.asyncio
async def test_progress_requires_live_document_and_does_not_expose_content(monkeypatch):
    from backend.foundation.api.ws_manager import ws_manager
    events = []

    async def broadcast(event, data):
        events.append((event, data))

    monkeypatch.setattr(ws_manager, "broadcast", broadcast)
    async with aiosqlite.connect(":memory:") as db:
        await db.execute(DOCUMENT_INPUTS_DDL)
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            document = (await client.post("/documents", json={"filename": "private-name.txt",
                "file_base64": base64.b64encode(b"private-content").decode()})).json()
            reference = document["document_id"]
            endpoint = f"/documents/{reference}/progress"
            progress = {"status": "running", "processed_blocks": 0, "saved_count": 0}
            assert (await client.post(endpoint, json=progress)).status_code == 200
            assert events == [("dreaming_progress", {**progress, "total_blocks": 1})]
            assert (await client.post(endpoint, json={**progress, "status": "completed"})).status_code == 422
            assert (await client.post(endpoint, json={**progress, "processed_blocks": 2})).status_code == 422
            await client.delete(f"/documents/{reference}")
            assert (await client.post(endpoint, json=progress)).status_code == 404
            assert len(events) == 1
