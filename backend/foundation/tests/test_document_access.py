from backend.foundation.documents.access import source_authorized


def test_watched_source_requires_active_consent_and_cannot_escape_via_symlink(tmp_path):
    watched = tmp_path / "watched"
    watched.mkdir()
    inside = watched / "work.txt"
    inside.write_text("work")
    outside = tmp_path / "private.txt"
    outside.write_text("private")
    link = watched / "link.txt"
    link.symlink_to(outside)
    config = {"enabled": True, "sources": {"directory": True}, "directories": [str(watched)]}
    assert source_authorized(str(inside), config)
    assert not source_authorized(str(outside), config)
    assert not source_authorized(str(link), config)
    config["enabled"] = False
    assert not source_authorized(str(inside), config)
