"""Combined failure paths preserve every accepted purchase and payment exactly once."""

from copy import deepcopy
import json

import pytest

from game.engine import Farm, PendingSaveError
from game.persistence import SaveStatus
from game.storage import RecoveryRequired
from tools.simulation import earn_to


def test_failed_purchase_then_production_and_write_retry_persist_each_once(farm, clock, monkeypatch):
    earn_to(farm, clock, 500)
    farm.construct("coop")
    original_balance = farm.state["coins"]
    price = farm.animal_price("chicken")
    saved = farm.store.path.read_bytes()
    failed_snapshots = []

    def fail(snapshot):
        failed_snapshots.append(deepcopy(snapshot))
        raise OSError("disk full after purchasing the chicken")

    with monkeypatch.context() as failure:
        failure.setattr(farm.store, "save", fail)
        with pytest.raises(PendingSaveError):
            farm.buy_animal("chicken")
        assert farm.count("chicken") == 1
        assert farm.state["coins"] == original_balance - price
        assert farm.store.path.read_bytes() == saved
        clock.skip(1800)
        assert farm.advance() == 15
        assert farm.advance() == 0
        assert farm.state["coins"] == original_balance - price + 15
        assert farm.persistence.status == SaveStatus.ERROR
        assert farm.store.path.read_bytes() == saved

    assert len(failed_snapshots) == 1
    assert failed_snapshots[0]["coins"] == original_balance - price
    assert farm.save() and farm.persistence.status == SaveStatus.SAVED
    assert json.loads(farm.store.path.read_text()) == farm.state
    restored = Farm(farm.store, clock)
    assert restored.state == farm.state and restored.offline_reward == 0
    assert restored.count("chicken") == 1
    assert restored.state["coins"] == original_balance - price + 15
    assert Farm(farm.store, clock).offline_reward == 0


def test_restored_backup_survives_failed_offline_save_then_credits_once(farm, clock, monkeypatch):
    earn_to(farm, clock, 500)
    farm.construct("coop")
    farm.buy_animal("chicken")
    # Rotate a backup that already contains the animal and its accounting mark.
    farm.preference("on_top", True)
    backup_bytes = farm.store.backup.read_bytes()
    backup_state = json.loads(backup_bytes)
    assert sum(animal["count"] for animal in backup_state["animals"]) == 1
    corrupt_bytes = b'{"damaged primary":\r\n'
    farm.store.path.write_bytes(corrupt_bytes)
    with pytest.raises(RecoveryRequired) as failure:
        farm.store.load()
    assert failure.value.backup_data == backup_state
    assert farm.store.path.read_bytes() == corrupt_bytes

    # This explicit restoration represents the recovery dialog's confirmed choice.
    assert farm.store.restore_backup() == backup_state
    restored_primary = farm.store.path.read_bytes()
    archives = {path.name: path.read_bytes() for path in farm.store.path.parent.glob("*.corrupt-*")}
    assert corrupt_bytes in archives.values() and backup_bytes in archives.values()
    failed_snapshots = []

    def fail(snapshot):
        failed_snapshots.append(deepcopy(snapshot))
        raise OSError("disk full while committing recovered offline income")

    clock.skip(7200)
    expected_income = 4 * 15
    with monkeypatch.context() as write_failure:
        write_failure.setattr(farm.store, "save", fail)
        with pytest.raises(OSError, match="recovered offline income"):
            Farm(farm.store, clock)
    assert len(failed_snapshots) == 1
    assert failed_snapshots[0]["coins"] == backup_state["coins"] + expected_income
    assert farm.store.path.read_bytes() == restored_primary
    assert farm.store.backup.read_bytes() == backup_bytes
    assert {path.name: path.read_bytes() for path in farm.store.path.parent.glob("*.corrupt-*")} == archives

    recovered = Farm(farm.store, clock)
    assert recovered.offline_reward == expected_income
    assert recovered.count("chicken") == 1
    assert recovered.state["coins"] == backup_state["coins"] + expected_income
    reopened = Farm(farm.store, clock)
    assert reopened.offline_reward == 0 and reopened.state == recovered.state
    assert corrupt_bytes in [path.read_bytes() for path in farm.store.path.parent.glob("*.corrupt-*")]
