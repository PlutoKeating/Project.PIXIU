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


@pytest.mark.asyncio
async def test_correction_requires_individual_review_and_keeps_reviewed_version():
    import copy
    current = {"knowledge_id": "knw_example123", "scope": "user:local", "version": 3,
               "title": "约定", "body": {"content": "周六九点"}}
    writes = []

    async def api(method, path, payload):
        if path.startswith("/documents/"):
            return MANIFEST
        if method == "GET":
            return copy.deepcopy(current)
        assert path == "/memory/update"
        if payload["expected_version"] != current["version"]:
            raise ValueError("VERSION_CONFLICT")
        writes.append(payload)
        return {"knowledge_id": current["knowledge_id"], "version": current["version"] + 1}

    session = DreamingSession(api, document_ids=[REFERENCE], scope="user:local", approved=True)
    proposal = {**prepare(session), "operation": "update", "knowledge_id": current["knowledge_id"]}
    with pytest.raises(ValueError, match="Read"):
        session.plan(proposal)
    await session.read_memory(current["knowledge_id"])
    plan = session.plan(proposal)
    assert plan["status"] == "awaiting_approval"  # Directory grants never approve corrections.
    with pytest.raises(ValueError, match="approved"):
        await session.apply(plan["plan_id"])
    review = session.review(plan["plan_id"])
    assert review["before"]["version"] == 3 and review["after"]["text"] == proposal["text"]
    review["before"]["version"] = 99
    session.approve_plan(plan["plan_id"])
    current["version"] = 4
    await session.read_memory(current["knowledge_id"])
    with pytest.raises(ValueError, match="VERSION_CONFLICT"):
        await session.apply(plan["plan_id"])
    assert not writes
    replacement = session.plan(proposal)
    session.approve_plan(replacement["plan_id"])
    await session.apply(replacement["plan_id"])
    await session.apply(replacement["plan_id"])
    assert len(writes) == 1
    assert writes[0]["expected_version"] == 4
    assert writes[0]["body"]["document_sources"][0]["block"]["text"] == "原始资料"


@pytest.mark.asyncio
async def test_model_cannot_change_scope_or_approve_its_own_update():
    async def api(method, path, payload):
        return {"knowledge_id": "knw_example123", "version": 1, "scope": "shared:home"}

    session = DreamingSession(api, document_ids=[REFERENCE], scope="user:local", approved=True)
    with pytest.raises(ValueError, match="scope"):
        await session.read_memory("knw_example123")
    with pytest.raises(ValueError, match="reference"):
        await session.read_memory("../private")
    with pytest.raises(ValueError):
        session.plan({**prepare(session), "approved": True})


@pytest.mark.asyncio
async def test_unapproved_correction_queues_one_durable_review_without_writing():
    queued = []

    async def api(method, path, payload):
        if path.startswith('/memory/items/'):
            return {'knowledge_id': 'knw_example123', 'scope': 'user:local', 'version': 2,
                    'title': '安排', 'body': {'content': '旧安排'}}
        if path == '/dreaming/plans':
            queued.append(payload)
            return {'plan_id': 'persisted-review', 'status': 'awaiting_approval'}
        raise AssertionError('No direct memory writes are allowed before approval')

    session = DreamingSession(api, document_ids=[REFERENCE], scope='user:local',
                             approved=True, queue_reviews=True)
    await session.read_memory('knw_example123')
    plan = session.plan({**prepare(session), 'operation': 'update', 'knowledge_id': 'knw_example123'})
    result = await session.apply(plan['plan_id'])
    assert await session.apply(plan['plan_id']) == result
    assert len(queued) == 1 and queued[0]['expected_version'] == 2
    report = session.report('模型声称已完成')
    assert report['status'] == 'awaiting_approval' and report['saved_count'] == 0


@pytest.mark.asyncio
async def test_merge_freezes_all_read_versions_and_only_queues_approval():
    queued = []
    version = 2
    async def api(method, path, payload):
        if path.startswith('/memory/items/'):
            return {'knowledge_id': path.split('/')[3].split('?')[0], 'scope': 'user:local',
                    'version': version, 'title': '安排', 'body': {'content': '原安排'}}
        assert path == '/dreaming/plans'
        queued.append(payload)
        return {'plan_id': 'review', 'status': 'awaiting_approval'}
    session = DreamingSession(api, document_ids=[REFERENCE], scope='user:local', approved=True, queue_reviews=True)
    proposal = {**prepare(session), 'operation': 'merge', 'knowledge_id': 'knw_example123',
                'merge_ids': ['knw_example123', 'knw_example456']}
    await session.read_memory('knw_example123')
    with pytest.raises(ValueError, match='Read all'):
        session.plan(proposal)
    await session.read_memory('knw_example456')
    plan = session.plan(proposal)
    version = 3
    await session.read_memory('knw_example456')
    await session.apply(plan['plan_id'])
    await session.apply(plan['plan_id'])
    assert len(queued) == 1
    assert queued[0]['versions'] == {'knw_example123': 2, 'knw_example456': 2}
    assert queued[0]['operation'] == 'merge'
    assert session.report('完成')['saved_count'] == 0
