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
