"""Document staging API shared by attachment and controlled Agent adapters."""
import asyncio
import base64
import subprocess
import zipfile
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..documents import decode_document
from ..documents.registry import DocumentRegistry, DocumentUnavailable
from .di import get_db

router = APIRouter(prefix="/documents", tags=["Documents"])


class DocumentUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_path: str | None = Field(default=None, max_length=4096)
    filename: str = Field(min_length=1, max_length=255)
    file_base64: str = Field(min_length=1, max_length=40 * 1024 * 1024)


def authorized_source(path):
    from .di import get_monitor_config_store
    from ..documents.access import source_authorized
    return source_authorized(path, get_monitor_config_store().get())


@router.post("")
async def register_document(body: DocumentUpload, db=Depends(get_db)):
    try:
        data = base64.b64decode(body.file_base64, validate=True)
        document = await asyncio.to_thread(decode_document, data, body.filename)
        return await DocumentRegistry(db, authorized_source).register(document, body.source_path)
    except (ValueError, OSError, zipfile.BadZipFile, ET.ParseError, subprocess.SubprocessError) as exc:
        raise HTTPException(422, "DOCUMENT_DECODE_FAILED") from exc


@router.get("/{document_id}")
async def describe_document(document_id: str, db=Depends(get_db)):
    try:
        return await DocumentRegistry(db, authorized_source).describe(document_id)
    except DocumentUnavailable as exc:
        raise HTTPException(404, "DOCUMENT_UNAVAILABLE") from exc


@router.get("/{document_id}/read")
async def read_document(document_id: str, cursor: int = Query(0, ge=0), db=Depends(get_db)):
    try:
        return await DocumentRegistry(db, authorized_source).read(document_id, cursor)
    except DocumentUnavailable as exc:
        raise HTTPException(404, "DOCUMENT_UNAVAILABLE") from exc
    except ValueError as exc:
        raise HTTPException(422, "DOCUMENT_CURSOR_INVALID") from exc


@router.delete("/{document_id}")
async def revoke_document(document_id: str, db=Depends(get_db)):
    await DocumentRegistry(db).revoke(document_id)
    return {"status": "revoked"}
