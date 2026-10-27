"""Diagnostic failures do not alter player progress or prevent recovery."""

import logging

import pytest

from game.diagnostics import attach_log, detach_log, diagnostic_path
from game.storage import RecoveryRequired, SaveStore


def test_invalid_progress_is_logged_separately_and_original_bytes_remain(tmp_path):
    store = SaveStore(tmp_path / "save.json")
    store.path.write_bytes(b"broken progress\r\n")
    handler = attach_log(store.path)
    try:
        assert handler is not None
        with pytest.raises(RecoveryRequired):
            store.load()
        handler.flush()
        assert store.path.read_bytes() == b"broken progress\r\n"
        assert "Progresso rejeitado" in diagnostic_path(store.path).read_text(encoding="utf-8")
        assert not store.backup.exists() and not list(tmp_path.glob("*.corrupt-*"))
    finally:
        detach_log(handler)


def test_unwritable_diagnostics_does_not_block_read_only_recovery(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("full disk")

    monkeypatch.setattr("game.diagnostics.RotatingFileHandler", fail)
    store = SaveStore(tmp_path / "save.json")
    store.path.write_bytes(b"invalid")
    assert attach_log(store.path) is None
    with pytest.raises(RecoveryRequired):
        store.load()
    assert store.path.read_bytes() == b"invalid"
    detach_log(None)


def test_profile_named_log_cannot_be_replaced_by_diagnostics(tmp_path):
    profile = tmp_path / "player.log"
    profile.write_bytes(b"exact original profile")
    handler = attach_log(profile)
    try:
        logging.getLogger("game.storage").warning("diagnostic sample")
        handler.flush()
        assert diagnostic_path(profile) != profile
        assert profile.read_bytes() == b"exact original profile"
        assert "diagnostic sample" in diagnostic_path(profile).read_text(encoding="utf-8")
    finally:
        detach_log(handler)


def test_closed_diagnostic_handler_is_removed_from_the_application_logger(tmp_path):
    logger = logging.getLogger("game")
    before = list(logger.handlers)
    handler = attach_log(tmp_path / "save.json")
    assert handler in logger.handlers
    detach_log(handler)
    assert logger.handlers == before and handler.stream is None
