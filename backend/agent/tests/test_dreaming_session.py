import pytest

from backend.agent.dreaming.session import DreamingSession


REFERENCE = "a" * 64
MANIFEST = {"document_id": REFERENCE, "version": "v1", "decoding_complete": True,
            "warnings": [], "blocks": [{"id": "block-1"}, {"id": "block-2"}]}


def prepare(session, block="block-1"):
    session.record_description(MANIFEST)
    session.record_delivery({"document_id": REFERENCE, "version": "v1",
                             "block": {"id": block, "kind": "text", "text": "原始资料"}})
    return {"title": "资料记忆", "text": "整理结果", "source_refs": [
        {"document_id": REFERENCE, "version": "v1", "block_id": block}]}


@pytest.mark.asyncio
async def test_approval_and_source_coverage_control_actual_writes():
    calls = []

    async def api(method, path, payload):
        calls.append((method, path, payload))
        return MANIFEST if method == "GET" else {"knowledge_id": "knw_test"}

    session = DreamingSession(api, document_ids=[REFERENCE], scope="user:local")
    proposal = prepare(session)
    plan_id = session.plan(proposal)["plan_id"]
    with pytest.raises(ValueError, match="approved"):
        await session.apply(plan_id)
    assert not calls
    with pytest.raises(ValueError):
        session.plan({**proposal, "approved": True})
    session.approved = True  # trusted host approval, never a model tool
    await session.apply(plan_id)
    await session.apply(plan_id)
    writes = [row for row in calls if row[0] == "POST"]
    assert len(writes) == 1
    assert writes[0][1] == "/memory/write"
    assert writes[0][2]["scope"] == "user:local"
    assert writes[0][2]["raw"]["body"]["document_sources"][0]["block"]["text"] == "原始资料"
    assert session.report("我已全部完成")["status"] == "incomplete"
    second = session.plan(prepare(session, "block-2"))
    await session.apply(second["plan_id"])
    assert session.report("完成")["status"] == "completed"


@pytest.mark.asyncio
async def test_revocation_unknown_sources_and_shared_scope_cannot_write():
    active = True
    calls = []

    async def api(*args):
        calls.append(args)
        return MANIFEST

    with pytest.raises(ValueError):
        DreamingSession(api, document_ids=[REFERENCE], scope="shared:home", approved=True)
    session = DreamingSession(api, document_ids=[REFERENCE], scope="user:local",
                              approved=True, active=lambda: active)
    proposal = prepare(session)
    proposal["source_refs"][0]["block_id"] = "block-not-read"
    with pytest.raises(ValueError, match="unread"):
        session.plan(proposal)
    plan_id = session.plan(prepare(session))["plan_id"]
    active = False
    with pytest.raises(ValueError, match="revoked"):
        await session.apply(plan_id)
    assert not calls
