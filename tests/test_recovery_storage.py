"""Invalid saves must never convert diagnostics into destructive writes."""

from copy import deepcopy
import json
import math
import os

import pytest

from game.engine import Farm
from game.state import MAX_TIMESTAMP, MIN_TIMESTAMP, fresh, number, validate
from game.storage import RecoveryRequired, SaveStore


def timestamp_state(value):
    data = fresh(value)
    data["plots"][0] = {"crop": "wheat", "planted_at": value}
    data["buildings"] = ["coop"]
    data["animals"] = [{"species": "chicken", "count": 1, "paid_until": value}]
    return data


@pytest.mark.parametrize(
    "value", [MIN_TIMESTAMP, 1, 1_800_000_000.25, MAX_TIMESTAMP - 1, math.nextafter(MAX_TIMESTAMP, 0)]
)
def test_calendar_timestamp_limits_preserve_valid_saved_values(value):
    data = timestamp_state(value)
    assert number(value)
    assert validate(data) == data


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(10**10_000, id="unbounded-integer"),
        MAX_TIMESTAMP,
        -1,
        float("inf"),
        float("-inf"),
        float("nan"),
        True,
        False,
        "1800000000",
        None,
        [],
        {},
    ],
)
def test_timestamp_rejects_invalid_values_without_conversion_overflow(value):
    assert not number(value)


@pytest.mark.parametrize("field", ["last_accounted", "planted_at", "paid_until"])
@pytest.mark.parametrize(
    "value", [pytest.param(10**400, id="overflowing-integer"), MAX_TIMESTAMP, -1, float("inf"), True]
)
def test_every_saved_timestamp_is_validated_before_conversions(field, value):
    data = timestamp_state(1_800_000_000)
    if field == "last_accounted":
        data[field] = value
    elif field == "planted_at":
        data["plots"][0][field] = value
    else:
        data["animals"][0][field] = value
    with pytest.raises(ValueError):
        validate(data)


@pytest.mark.parametrize("damage", ["huge-timestamp", "malformed-json", "invalid-utf8", "json-digit-limit"])
def test_invalid_primary_offers_valid_backup_without_writing(tmp_path, clock, caplog, damage):
    store = SaveStore(tmp_path / "save.json")
    valid = timestamp_state(clock())
    store.backup.write_text(json.dumps(valid), encoding="utf-8")
    if damage == "huge-timestamp":
        damaged = deepcopy(valid)
        damaged["last_accounted"] = 10**400
        raw = json.dumps(damaged).encode()
    elif damage == "malformed-json":
        raw = b'{"coins":'
    elif damage == "invalid-utf8":
        raw = b"\xff\xfe\x00"
    else:
        raw = b'{"last_accounted":' + b"9" * 10_000 + b"}"
    store.path.write_bytes(raw)
    backup = store.backup.read_bytes()
    with pytest.raises(RecoveryRequired) as failure:
        Farm(store, clock)
    assert failure.value.backup_data == valid
    assert str(store.path) in failure.value.details
    assert store.path.read_bytes() == raw
    assert store.backup.read_bytes() == backup
    assert sorted(path.name for path in tmp_path.iterdir()) == ["save.json", "save.json.bak"]
    assert "Progresso rejeitado" in caplog.text


def test_all_invalid_saves_require_decision_and_cancel_preserves_every_byte(tmp_path, clock):
    store = SaveStore(tmp_path / "save.json")
    store.path.write_bytes(b"bad primary\n")
    store.backup.write_bytes(b"bad backup\r\n")
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    for _ in range(2):
        with pytest.raises(RecoveryRequired) as failure:
            Farm(store, clock)
        assert failure.value.backup_data is None
        assert len(failure.value.issues) == 2
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_empty_installation_is_distinct_from_missing_primary_with_backup(tmp_path, clock):
    store = SaveStore(tmp_path / "save.json")
    assert store.load() is None
    data = fresh(clock())
    store.backup.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RecoveryRequired) as failure:
        store.load()
    assert failure.value.backup_data == data
    assert not store.path.exists()
    assert store.restore_backup() == data
    assert store.load() == data


def test_archives_from_older_versions_do_not_silently_start_new_farm(tmp_path):
    store = SaveStore(tmp_path / "save.json")
    archive = tmp_path / "save.json.corrupt-from-v010"
    archive.write_bytes(b"old preserved progress")
    with pytest.raises(RecoveryRequired):
        store.load()
    assert archive.read_bytes() == b"old preserved progress" and not store.path.exists()


def test_retry_can_load_a_manually_repaired_primary(tmp_path, clock):
    store = SaveStore(tmp_path / "save.json")
    store.path.write_text("broken")
    with pytest.raises(RecoveryRequired):
        store.load()
    repaired = fresh(clock())
    repaired["coins"] = 137
    store.path.write_text(json.dumps(repaired))  # An external/manual repair, not the loader.
    assert store.load() == repaired and store.recovery is None


def test_authorized_restore_preserves_primary_and_backup_exactly(tmp_path, clock):
    store = SaveStore(tmp_path / "save.json")
    data = timestamp_state(clock())
    primary = b'{"damaged": '
    backup = json.dumps(data, indent=2).encode()
    store.path.write_bytes(primary)
    store.backup.write_bytes(backup)
    store.restore_backup()
    assert store.load() == data
    assert store.backup.read_bytes() == backup
    archives = [path.read_bytes() for path in tmp_path.glob("*.corrupt-*")]
    assert primary in archives and backup in archives


def test_authorized_new_farm_preserves_both_rejected_files(tmp_path, clock):
    store = SaveStore(tmp_path / "save.json")
    store.path.write_bytes(b"primary broken")
    store.backup.write_bytes(b"backup broken")
    new = fresh(clock())
    store.start_new(new)
    assert store.load() == new
    archives = {path.read_bytes() for path in tmp_path.glob("*.corrupt-*")}
    assert archives == {b"primary broken", b"backup broken"}


def test_restore_revalidates_backup_changed_after_diagnosis(tmp_path, clock):
    store = SaveStore(tmp_path / "save.json")
    store.path.write_bytes(b"damaged")
    store.backup.write_text(json.dumps(fresh(clock())))
    with pytest.raises(RecoveryRequired):
        store.load()
    store.backup.write_bytes(b"now damaged too")
    with pytest.raises(ValueError, match="cópia de segurança válida"):
        store.restore_backup()
    assert store.path.read_bytes() == b"damaged"
    assert store.backup.read_bytes() == b"now damaged too"
    assert not list(tmp_path.glob("*.corrupt-*"))


def test_save_refuses_to_replace_external_corruption(tmp_path, clock):
    store = SaveStore(tmp_path / "save.json")
    saved = fresh(clock())
    store.save(saved)
    store.path.write_bytes(b"externally damaged")
    saved["coins"] = 67
    with pytest.raises(RecoveryRequired):
        store.save(saved)
    assert store.path.read_bytes() == b"externally damaged"


def test_failed_recovery_install_keeps_originals_and_archives(tmp_path, clock, monkeypatch):
    store = SaveStore(tmp_path / "save.json")
    store.path.write_bytes(b"damaged primary")
    backup = json.dumps(fresh(clock())).encode()
    store.backup.write_bytes(backup)
    original = os.replace

    def fail(source, destination):
        if destination == store.path:
            raise OSError("disk full")
        return original(source, destination)

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match="disk full"):
        store.restore_backup()
    assert store.path.read_bytes() == b"damaged primary"
    assert store.backup.read_bytes() == backup
    assert {path.read_bytes() for path in tmp_path.glob("*.corrupt-*")} == {b"damaged primary", backup}
    assert not list(tmp_path.glob("*.tmp"))
