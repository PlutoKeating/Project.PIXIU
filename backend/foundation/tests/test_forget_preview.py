import pytest

from backend.foundation.api.forget_preview import ForgetPreviews


def test_receipt_binds_command_scope_and_is_consumed_once():
    store = ForgetPreviews()
    token = store.issue("forget example", "user:local", {"k1": 2})
    assert store.consume(token, "forget example", "user:local") == {"k1": 2}
    with pytest.raises(ValueError):
        store.consume(token, "forget example", "user:local")
    for command, scope in [("changed", "user:local"), ("forget example", "shared:home")]:
        token = store.issue("forget example", "user:local", {"k1": 2})
        with pytest.raises(ValueError):
            store.consume(token, command, scope)
        with pytest.raises(ValueError):
            store.consume(token, "forget example", "user:local")


def test_expiry_capacity_and_snapshot_copy():
    now = [0]
    store = ForgetPreviews(ttl=2, capacity=1, clock=lambda: now[0])
    targets = {"k1": 1}
    token = store.issue("example", None, targets)
    targets["k1"] = 2
    with pytest.raises(ValueError):
        store.issue("another", None, {})
    assert store.consume(token, "example", None) == {"k1": 1}
    expired = store.issue("example", None, {})
    now[0] = 2
    with pytest.raises(ValueError):
        store.consume(expired, "example", None)
    store.issue("replacement", None, {})
