"""Task-scoped memory operations. The launcher owns authorization, not the model.

This session exposes only private creates. Existing-memory corrections, sharing
and deletion are deliberately absent until their reviewed plan paths are wired.
"""
import copy
import re
import secrets

from pydantic import BaseModel, ConfigDict, Field


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    version: str
    block_id: str


class MemoryProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=512)
    text: str = Field(min_length=1, max_length=60000)
    source_refs: list[SourceReference] = Field(min_length=1)


class DreamingSession:
    def __init__(self, api, *, document_ids, scope, approved=False, active=lambda: True):
        if not re.fullmatch(r"user:[A-Za-z0-9_.-]+", scope):
            raise ValueError("Background document creation requires a private scope")
        self.api = api
        self.document_ids = frozenset(document_ids)
        self.scope = scope
        self.approved = approved
        self.active = active
        self.manifests = {}
        self.delivered = {}
        self.plans = {}
        self.results = {}
        self.job_id = secrets.token_hex(16)

    def _require_active(self):
        if not self.active():
            raise ValueError("Task authorization was revoked")

    def record_description(self, description):
        self._require_active()
        reference = description["document_id"]
        if reference not in self.document_ids:
            raise ValueError("Document is outside task authorization")
        previous = self.manifests.get(reference)
        if previous and previous["version"] != description["version"]:
            raise ValueError("Document changed during task")
        self.manifests[reference] = copy.deepcopy(description)

    def record_delivery(self, result):
        self._require_active()
        reference = result["document_id"]
        manifest = self.manifests.get(reference)
        block = result["block"]
        if not manifest or manifest["version"] != result["version"] or block["id"] not in {b["id"] for b in manifest["blocks"]}:
            raise ValueError("Describe the granted document before reading its blocks")
        self.delivered[(reference, block["id"])] = copy.deepcopy(block)

    async def search(self, query):
        self._require_active()
        return await self.api("POST", "/memory/query", {
            "text": query, "context_hint": {"scope": self.scope},
        })

    def plan(self, proposal):
        self._require_active()
        parsed = MemoryProposal.model_validate(proposal)
        for ref in parsed.source_refs:
            manifest = self.manifests.get(ref.document_id)
            if not manifest or manifest["version"] != ref.version or (ref.document_id, ref.block_id) not in self.delivered:
                raise ValueError("Proposal refers to an unread or unauthorized source")
        plan_id = secrets.token_hex(16)
        self.plans[plan_id] = parsed
        return {"plan_id": plan_id, "status": "ready" if self.approved else "awaiting_approval"}

    async def apply(self, plan_id):
        self._require_active()
        if not self.approved:
            raise ValueError("This task has no approved memory creation plan")
        if plan_id not in self.plans:
            raise ValueError("Unknown plan")
        if plan_id in self.results:
            return self.results[plan_id]
        proposal = self.plans[plan_id]
        # Revalidate the document grant immediately before any memory side effect.
        for reference in {ref.document_id for ref in proposal.source_refs}:
            current = await self.api("GET", "/documents/" + reference, None)
            if current["version"] != self.manifests[reference]["version"]:
                raise ValueError("Source version changed")
        self._require_active()
        sources = [{**ref.model_dump(), "block": self.delivered[(ref.document_id, ref.block_id)]}
                   for ref in proposal.source_refs]
        payload = {"source_type": "MANUAL_CONFIG", "scope": self.scope,
                   "raw": {"title": proposal.title, "body": {"text": proposal.text, "document_sources": sources}},
                   "idempotency_key": "dreaming:" + self.job_id + ":" + plan_id}
        result = await self.api("POST", "/memory/write", payload)
        self.results[plan_id] = result
        return result

    def report(self, summary):
        self._require_active()
        expected = {(ref, block["id"]) for ref, document in self.manifests.items() for block in document["blocks"]}
        covered = {(ref.document_id, ref.block_id) for plan_id in self.results
                   for ref in self.plans[plan_id].source_refs}
        complete = (set(self.manifests) == set(self.document_ids) and bool(expected)
                    and expected <= covered and all(doc.get("decoding_complete") for doc in self.manifests.values()))
        return {"status": "completed" if complete else "incomplete", "summary": summary,
                "saved_count": len(self.results), "remaining_blocks": len(expected - covered),
                "warnings": [warning for doc in self.manifests.values() for warning in doc.get("warnings", [])]}
