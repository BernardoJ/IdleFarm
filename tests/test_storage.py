from copy import deepcopy
import json
import os
import pytest
from game.engine import Farm
from game.state import fresh, validate
from game.storage import SaveStore


def test_failed_atomic_replace_keeps_previous_save(farm, monkeypatch):
    data = farm.store.path.read_bytes()
    before = deepcopy(farm.state)
    original = os.replace

    def fail(source, dest):
        if dest == farm.store.path:
            raise OSError("disk full")
        return original(source, dest)

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        farm.plant(0, "wheat")
    assert farm.state == before
    assert farm.store.path.read_bytes() == data
    assert not list(farm.store.path.parent.glob("*.tmp"))


def test_corruption_recovers_backup_without_destroying_bytes(farm, clock):
    before = deepcopy(farm.state)
    farm.plant(0, "wheat")  # Backup holds the preceding valid state.
    farm.store.path.write_text('{"coins":', encoding="utf-8")
    recovered = Farm(farm.store, clock)
    assert recovered.state == before
    assert "recuperado" in farm.store.warning
    assert list(farm.store.path.parent.glob("*.corrupt-*"))[0].read_text() == '{"coins":'


def test_both_invalid_files_are_preserved(tmp_path, clock):
    store = SaveStore(tmp_path / "save.json")
    store.path.write_text("broken", encoding="utf-8")
    store.backup.write_text("null", encoding="utf-8")
    farm = Farm(store, clock)
    assert farm.state["coins"] == 50
    assert len(list(tmp_path.glob("*.corrupt-*"))) == 2
    assert "ilegível" in store.warning


@pytest.mark.parametrize(
    "key,value",
    [
        ("coins", -1),
        ("coins", True),
        ("coins", 1.1),
        ("last_accounted", float("nan")),
        ("version", 99),
        ("plots", []),
        ("buildings", ["unknown"]),
        ("animals", [{"species": "horse", "count": 1, "paid_until": 1}]),
    ],
)
def test_strict_schema(key, value):
    data = fresh(100)
    data[key] = value
    with pytest.raises(ValueError):
        validate(data)


def test_alternate_save_never_touches_real_progress(tmp_path, monkeypatch, clock):
    real = tmp_path / "real.json"
    real.write_text("DO NOT TOUCH")
    monkeypatch.setenv("IDLEFARM_SAVE_PATH", str(real))
    store = SaveStore(tmp_path / "qa" / "test.json")
    farm = Farm(store, clock)
    farm.plant(0, "wheat")
    assert real.read_text() == "DO NOT TOUCH"
    assert json.loads(store.path.read_text())["coins"] == 45
