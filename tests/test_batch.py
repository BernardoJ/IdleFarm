"""Batch actions share business rules and persist once, including retry semantics."""

from copy import deepcopy
import json

import pytest

from game.engine import Farm, GameError, PendingSaveError
from game.persistence import SaveStatus
from tools.simulation import earn_to


def expand_to(farm, clock, count):
    while len(farm.state["plots"]) < count:
        earn_to(farm, clock, farm.expansion_price())
        farm.expand()
    earn_to(farm, clock, 100)


def test_free_navigation_wraps_predictably_and_reports_no_slot(farm, clock):
    assert farm.free_plots() == [0, 1]
    assert farm.next_free_plot(0) == 1
    assert farm.next_free_plot(1) == 0
    farm.plant(1, "carrot")
    assert farm.next_free_plot(0) == 0 and farm.next_free_plot(1) == 0
    farm.plant(0, "wheat")
    assert farm.free_plots() == [] and farm.next_free_plot(1) is None
    with pytest.raises(GameError):
        farm.next_free_plot(True)
    clock.skip(60)
    farm.harvest(0)
    assert farm.next_free_plot(1) == 0
    expand_to(farm, clock, 3)
    assert farm.next_free_plot(1) == 2


def test_quote_is_read_only_and_describes_requested_unaffordable_quantity(farm):
    farm.state["coins"] = 5
    farm.save()
    before = deepcopy(farm.state)
    quote = farm.planting_quote("wheat")
    assert quote == {
        "plots": [0, 1],
        "count": 2,
        "cost": 10,
        "balance": 5,
        "affordable_count": 1,
        "available_count": 2,
        "crop": "wheat",
    }
    assert farm.state == before
    assert farm.planting_quote("wheat", 1)["cost"] == 5
    assert farm.planting_quote("wheat", 100)["count"] == 2
    assert farm.planting_quote("wheat", 0)["count"] == 0
    for quantity in (-1, True, 1.5):
        with pytest.raises(GameError):
            farm.planting_quote("wheat", quantity)
    with pytest.raises(GameError):
        farm.planting_quote("pumpkin")


def test_batch_plant_with_enough_money_persists_once_and_only_one_tutorial(farm, clock, monkeypatch):
    original = farm.store.save
    writes = []

    def record(snapshot):
        writes.append(deepcopy(snapshot))
        original(snapshot)

    monkeypatch.setattr(farm.store, "save", record)
    summary = farm.plant_batch("wheat", [0, 1])
    assert summary == {"count": 2, "cost": 10, "plots": [0, 1], "crop": "wheat"}
    assert len(writes) == 1
    assert farm.state["coins"] == 40 and farm.remaining(0) == 60 and farm.remaining(1) == 3600
    assert Farm(farm.store, clock).state == farm.state
    clock.skip(60)
    assert farm.harvest_ready() == {"count": 1, "reward": 20, "plots": [0]}
    assert farm.tutorial_phase == "completed"


def test_batch_harvest_only_ready_crops_and_credit_each_once(farm, clock, monkeypatch):
    expand_to(farm, clock, 3)
    farm.plant(0, "wheat")
    farm.plant(1, "wheat")
    farm.plant(2, "carrot")
    clock.skip(3600)
    assert farm.ready_plots() == [0, 1]
    original = farm.store.save
    writes = []

    def record(snapshot):
        writes.append(snapshot)
        original(snapshot)

    monkeypatch.setattr(farm.store, "save", record)
    before = farm.state["coins"]
    summary = farm.harvest_ready()
    assert summary == {"count": 2, "reward": 40, "plots": [0, 1]}
    assert len(writes) == 1 and farm.state["coins"] == before + 40
    assert farm.state["plots"][:2] == [None, None]
    assert farm.state["plots"][2]["crop"] == "carrot"
    with pytest.raises(GameError):
        farm.harvest_ready()
    assert farm.state["coins"] == before + 40 and len(writes) == 1
    assert Farm(farm.store, clock).state == farm.state


@pytest.mark.parametrize("indices", [[], [0, 0], [0, True], [-1], [100], ["0"], None, "0"])
def test_invalid_batch_selection_cannot_spend_or_persist(farm, indices, monkeypatch):
    before = deepcopy(farm.state)
    written = []
    monkeypatch.setattr(farm.store, "save", lambda snapshot: written.append(snapshot))
    with pytest.raises(GameError):
        farm.plant_batch("wheat", indices)
    assert farm.state == before and written == []


def test_insufficient_batch_balance_never_partially_plants_or_overdraws(farm):
    farm.state["coins"] = 5
    farm.save()
    before = deepcopy(farm.state)
    disk = farm.store.path.read_bytes()
    with pytest.raises(GameError, match="Moedas insuficientes"):
        farm.plant_batch("wheat", [0, 1])
    assert farm.state == before and farm.store.path.read_bytes() == disk
    assert farm.plant_batch("wheat", [0])["cost"] == 5
    assert farm.state["coins"] == 0 and farm.state["plots"][1] is None


def test_occupied_batch_slot_rejects_whole_selection_and_empty_quotes_are_clear(farm):
    farm.plant(1, "carrot")
    before = deepcopy(farm.state)
    with pytest.raises(GameError, match="ocupado"):
        farm.plant_batch("wheat", [0, 1])
    assert farm.state == before
    farm.plant(0, "wheat")
    assert farm.planting_quote("wheat")["available_count"] == 0
    assert farm.planting_quote("wheat")["cost"] == 0
    with pytest.raises(GameError):
        farm.harvest_ready()


@pytest.mark.parametrize("operation", ["plant", "harvest"])
def test_batch_write_failure_stays_pending_and_retry_never_replays_business_action(
    farm, clock, monkeypatch, operation
):
    if operation == "harvest":
        farm.plant_batch("wheat", [0, 1])
        clock.skip(3600)
    original = farm.store.save
    disk = farm.store.path.read_bytes()
    balance = farm.state["coins"]

    def fail(snapshot):
        raise OSError("disk full")

    monkeypatch.setattr(farm.store, "save", fail)
    with pytest.raises(PendingSaveError) as failure:
        if operation == "plant":
            farm.plant_batch("wheat", [0, 1])
        else:
            farm.harvest_ready()
    expected_delta = -10 if operation == "plant" else 40
    assert failure.value.result["count"] == 2
    assert farm.state["coins"] == balance + expected_delta
    assert farm.persistence.status == SaveStatus.ERROR
    assert farm.store.path.read_bytes() == disk
    monkeypatch.setattr(farm.store, "save", original)
    farm.save()
    assert farm.persistence.status == SaveStatus.SAVED
    assert json.loads(farm.store.path.read_text()) == farm.state
    assert Farm(farm.store, clock).state == farm.state
    assert farm.state["coins"] == balance + expected_delta
