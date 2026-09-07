from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "third_party" / "kylin-agent-runtime"))
from integrations.kylin_agent.pixiu.outbox import Outbox


def test_restart_retains_exact_request_and_lease_expires(tmp_path):
    now = [100.0]
    path = tmp_path / "outbox"
    first = Outbox(path, "profile-a", clock=lambda: now[0])
    payload = {"idempotency_key": "stable", "data": {"text": "记忆"}}
    first.enqueue("stable", payload)
    first.enqueue("stable", payload)
    old = first.claim(lease_seconds=10)
    assert old and old[1] == payload and first.pending() == 1
    first.close()
    second = Outbox(path, "profile-a", clock=lambda: now[0])
    try:
        assert second.claim() is None
        now[0] = 111
        current = second.claim()
        assert current and current[:2] == old[:2] and current[2] != old[2]
        assert not second.acknowledge(old[0], old[2])
        assert second.acknowledge(current[0], current[2])
        assert second.pending() == 0
        assert os.stat(path).st_mode & 0o777 == 0o700
        assert os.stat(path / "delivery.sqlite3").st_mode & 0o777 == 0o600
    finally:
        second.close()


def test_partition_capacity_collision_and_retry(tmp_path):
    now = [100.0]
    first = Outbox(tmp_path / "outbox", "a", capacity=2, clock=lambda: now[0])
    second = Outbox(tmp_path / "outbox", "b", capacity=2, clock=lambda: now[0])
    try:
        first.enqueue("one", {"value": 1})
        with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
            first.enqueue("one", {"value": 2})
        assert second.claim() is None
        second.enqueue("two", {"value": 2})
        with pytest.raises(ValueError, match="OUTBOX_FULL"):
            first.enqueue("three", {})
        job = first.claim()
        assert job and first.retry(job[0], job[2], delay=5)
        assert not first.acknowledge(job[0], job[2])
        assert first.claim() is None
        now[0] += 6
        assert first.claim() is not None
    finally:
        first.close()
        second.close()


def test_unsafe_storage_is_rejected(tmp_path):
    public = tmp_path / "public"
    public.mkdir(mode=0o755)
    with pytest.raises(ValueError, match="UNSAFE_OUTBOX_DIRECTORY"):
        Outbox(public, "a")
    link = tmp_path / "link"
    link.symlink_to(public, target_is_directory=True)
    with pytest.raises(ValueError, match="UNSAFE_OUTBOX_DIRECTORY"):
        Outbox(link, "a")


def test_byte_limit_preserves_previously_pending_record(tmp_path):
    outbox = Outbox(tmp_path / "outbox", "a", byte_limit=20)
    try:
        outbox.enqueue("one", {})
        with pytest.raises(ValueError, match="OUTBOX_FULL"):
            outbox.enqueue("two", {"text": "x" * 20})
        assert outbox.pending() == 1
    finally:
        outbox.close()


def test_two_instances_cannot_claim_the_same_delivery(tmp_path):
    first = Outbox(tmp_path / "outbox", "a")
    second = Outbox(tmp_path / "outbox", "a")
    try:
        first.enqueue("one", {"event": "TURN_END"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda box: box.claim(), [first, second]))
        assert sum(result is not None for result in results) == 1
        assert first.pending() == second.pending() == 1
    finally:
        first.close()
        second.close()
