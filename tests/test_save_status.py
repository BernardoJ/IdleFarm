"""Persistence acknowledgements must match disk data, including failed purchases."""

from copy import deepcopy
import json
import pytest

from game.engine import Farm
from game.persistence import SaveStatus
from tools.simulation import earn_to
from ui.window import FarmWindow


class Monotonic:
    def __init__(self):
        self.value = 0

    def __call__(self):
        return self.value


def populated(farm, clock):
    earn_to(farm, clock, 500)
    farm.construct("coop")
    return farm


def test_animal_purchase_write_failure_survives_notice_timeout_without_double_charge(
    app, farm, clock, monkeypatch
):
    timer = Monotonic()
    monkeypatch.setattr("ui.window.time.monotonic", timer)
    populated(farm, clock)
    window = FarmWindow(farm)
    old_coins = farm.state["coins"]
    price = farm.animal_price("chicken")
    persisted = farm.store.path.read_bytes()
    original = farm.store.save
    attempts = []

    def fail(snapshot):
        attempts.append(deepcopy(snapshot))
        assert "Salvando" in window.save_info.text()
        raise OSError("disk full")

    monkeypatch.setattr(farm.store, "save", fail)
    try:
        window.act(lambda: farm.buy_animal("chicken"), "Galinha comprada")
        assert farm.state["coins"] == old_coins - price and farm.count("chicken") == 1
        assert farm.store.path.read_bytes() == persisted
        assert farm.persistence.status == SaveStatus.ERROR
        assert "Erro ao salvar" in window.save_info.text()
        timer.value = 13
        window.refresh()
        assert "Erro ao salvar" in window.save_info.text() and "Tudo salvo" not in window.notice.text()
        window.tick()
        assert len(attempts) == 2 and farm.persistence.status == SaveStatus.ERROR
        window.tick()
        assert len(attempts) == 2  # no unbounded retries every tick
        monkeypatch.setattr(farm.store, "save", original)
        timer.value = 24
        window.tick()
        assert farm.persistence.status == SaveStatus.SAVED and window.save_info.text() == "Tudo salvo"
        assert farm.count("chicken") == 1 and farm.state["coins"] == old_coins - price
        assert json.loads(farm.store.path.read_text()) == farm.state
    finally:
        monkeypatch.setattr(farm.store, "save", original)
        window.close()
        app.processEvents()


def test_failed_animal_production_save_remains_error_after_twelve_seconds(app, farm, clock, monkeypatch):
    timer = Monotonic()
    monkeypatch.setattr("ui.window.time.monotonic", timer)
    populated(farm, clock)
    farm.buy_animal("chicken")
    window = FarmWindow(farm)
    original = farm.store.save
    balance = farm.state["coins"]

    def fail(snapshot):
        raise OSError("write failed")

    monkeypatch.setattr(farm.store, "save", fail)
    try:
        clock.skip(1800)
        window.tick()
        assert farm.state["coins"] == balance + 15
        timer.value = 15
        window.refresh()
        assert farm.persistence.status == SaveStatus.ERROR
        assert "Tudo salvo" not in window.save_info.text() + window.notice.text()
        monkeypatch.setattr(farm.store, "save", original)
        assert window.save_now()
        assert window.save_info.text() == "Tudo salvo"
        assert farm.state["coins"] == balance + 15
    finally:
        monkeypatch.setattr(farm.store, "save", original)
        window.close()
        app.processEvents()


def test_old_write_completion_cannot_acknowledge_newer_change(farm, monkeypatch):
    original = farm.store.save
    observed = []

    def delayed(snapshot):
        observed.append(farm.persistence.status)
        original(snapshot)
        farm.plant(1, "wheat")  # nested save is deferred until the current one ends

    monkeypatch.setattr(farm.store, "save", delayed)
    farm.plant(0, "wheat")
    assert observed == [SaveStatus.SAVING]
    assert farm.persistence.status == SaveStatus.PENDING
    assert farm.persistence.saved_generation < farm.persistence.generation
    assert json.loads(farm.store.path.read_text())["plots"][1] is None
    assert farm.state["plots"][1]["crop"] == "wheat"
    monkeypatch.setattr(farm.store, "save", original)
    assert farm.save()
    assert farm.persistence.status == SaveStatus.SAVED
    assert json.loads(farm.store.path.read_text()) == farm.state


def test_save_is_snapshot_isolated_and_noop_when_nothing_changed(farm, monkeypatch):
    original = farm.store.save
    written = []

    def record(snapshot):
        written.append(snapshot)
        assert snapshot is not farm.state
        original(snapshot)

    monkeypatch.setattr(farm.store, "save", record)
    assert farm.save() and written == []
    farm.plant(0, "wheat")
    assert len(written) == 1
    assert farm.save() and len(written) == 1


def test_automatic_dirty_save_waits_for_regular_interval(app, farm, clock, monkeypatch):
    timer = Monotonic()
    monkeypatch.setattr("ui.window.time.monotonic", timer)
    window = FarmWindow(farm)
    original = farm.store.save
    writes = []

    def record(snapshot):
        writes.append(snapshot)
        original(snapshot)

    monkeypatch.setattr(farm.store, "save", record)
    try:
        for second in range(1, 30):
            timer.value = second
            clock.skip(1)
            window.tick()
        assert writes == [] and farm.persistence.status == SaveStatus.PENDING
        timer.value = 30
        clock.skip(1)
        window.tick()
        assert len(writes) == 1 and farm.persistence.status == SaveStatus.SAVED
    finally:
        window.close()
        app.processEvents()


def test_invalid_action_still_rolls_back_business_changes(farm):
    before = deepcopy(farm.state)
    with pytest.raises(ValueError):
        farm.buy_animal("chicken")
    assert farm.state == before
    assert farm.persistence.status == SaveStatus.SAVED


def test_reload_never_replays_a_successfully_retried_purchase(farm, clock, monkeypatch):
    populated(farm, clock)
    original = farm.store.save

    def fail(snapshot):
        raise OSError("full")

    monkeypatch.setattr(farm.store, "save", fail)
    with pytest.raises(OSError):
        farm.buy_animal("chicken")
    balance = farm.state["coins"]
    monkeypatch.setattr(farm.store, "save", original)
    farm.save()
    restored = Farm(farm.store, clock)
    assert restored.count("chicken") == 1 and restored.state["coins"] == balance
