"""One short wheat cycle teaches new farms without changing legacy growth."""

from copy import deepcopy
import json

import pytest

from config.data import CROPS
from game.engine import Farm, GameError, PendingSaveError
from game.state import fresh, validate
from game.storage import SaveStore


def test_new_farm_tutorial_teaches_one_full_cycle_at_normal_price_and_reward(farm, clock):
    assert farm.tutorial_phase == "available" and farm.tutorial_plot is None
    assert farm.planting_seconds("wheat") == 60
    assert farm.planting_seconds("carrot") == CROPS["carrot"]["seconds"]
    before = farm.state["coins"]
    farm.plant(0, "wheat")
    assert farm.state["coins"] == before - CROPS["wheat"]["seed"]
    assert farm.tutorial_phase == "growing" and farm.tutorial_plot == 0
    assert farm.remaining(0) == farm.crop_duration(0) == 60
    for elapsed, stage in ((0, 0), (6, 1), (30, 2), (59, 2), (60, 3)):
        clock.value = farm.state["plots"][0]["planted_at"] + elapsed
        assert farm.stage(0) == stage
    assert farm.harvest(0) == CROPS["wheat"]["reward"]
    assert farm.state["coins"] == before - CROPS["wheat"]["seed"] + CROPS["wheat"]["reward"]
    assert farm.tutorial_phase == "completed" and farm.tutorial_plot is None
    farm.plant(0, "wheat")
    assert farm.remaining(0) == farm.crop_duration(0) == CROPS["wheat"]["seconds"]


def test_only_one_simultaneously_planted_wheat_gets_short_cycle(farm, clock):
    farm.plant(1, "wheat")
    farm.plant(0, "wheat")
    assert farm.tutorial_plot == 1
    assert farm.remaining(1) == 60 and farm.remaining(0) == 3600
    clock.skip(60)
    assert farm.ready_plots() == [1]
    with pytest.raises(GameError):
        farm.harvest(0)
    farm.harvest(1)
    assert farm.remaining(0) == 3540


def test_other_crops_never_receive_tutorial_speed_and_do_not_consume_it(farm):
    farm.plant(0, "carrot")
    assert farm.remaining(0) == CROPS["carrot"]["seconds"]
    assert farm.tutorial_phase == "available"
    farm.plant(1, "wheat")
    assert farm.remaining(1) == 60


def test_tutorial_progress_survives_restart_without_renewing_time(farm, clock):
    farm.plant(0, "wheat")
    planted_at = farm.state["plots"][0]["planted_at"]
    clock.skip(30)
    restored = Farm(farm.store, clock)
    assert restored.tutorial_phase == "growing" and restored.tutorial_plot == 0
    assert restored.remaining(0) == 30
    assert restored.state["plots"][0]["planted_at"] == planted_at
    clock.skip(30)
    ready = Farm(farm.store, clock)
    assert ready.remaining(0) == 0 and ready.tutorial_phase == "growing"
    ready.harvest(0)
    completed = Farm(farm.store, clock)
    assert completed.tutorial_phase == "completed"
    assert completed.state["tutorial"] == {"done": True, "plot": None}
    completed.plant(0, "wheat")
    assert completed.remaining(0) == 3600


def test_legacy_save_keeps_exact_keys_and_ordinary_first_crop(tmp_path, clock):
    data = fresh(clock())
    del data["tutorial"]
    store = SaveStore(tmp_path / "legacy.json")
    store.save(data)
    farm = Farm(store, clock)
    assert farm.state == data and "tutorial" not in farm.state
    assert farm.tutorial_phase == "completed" and farm.tutorial_plot is None
    farm.plant(0, "wheat")
    assert farm.remaining(0) == 3600
    assert "tutorial" not in farm.state and "tutorial" not in json.loads(store.path.read_text())


def test_failed_tutorial_save_keeps_one_memory_cycle_until_retry(farm, clock, monkeypatch):
    original = farm.store.save

    def fail(snapshot):
        raise OSError("disk full")

    monkeypatch.setattr(farm.store, "save", fail)
    with pytest.raises(PendingSaveError):
        farm.plant(0, "wheat")
    assert farm.tutorial_plot == 0 and farm.state["coins"] == 45
    monkeypatch.setattr(farm.store, "save", original)
    farm.save()
    clock.skip(60)
    restored = Farm(farm.store, clock)
    assert restored.remaining(0) == 0 and restored.state["coins"] == 45
    restored.harvest(0)
    assert Farm(farm.store, clock).tutorial_phase == "completed"


@pytest.mark.parametrize(
    "tutorial",
    [
        None,
        [],
        {},
        {"done": 0, "plot": None},
        {"done": False},
        {"done": False, "plot": True},
        {"done": False, "plot": -1},
        {"done": False, "plot": 2},
        {"done": False, "plot": 0},
        {"done": True, "plot": 0},
    ],
)
def test_invalid_tutorial_metadata_is_rejected(tutorial, clock):
    data = fresh(clock())
    data["tutorial"] = deepcopy(tutorial)
    with pytest.raises(ValueError):
        validate(data)


def test_tutorial_plot_must_be_existing_wheat_and_done_needs_no_slot(clock):
    data = fresh(clock())
    data["plots"][0] = {"crop": "carrot", "planted_at": clock()}
    data["tutorial"] = {"done": False, "plot": 0}
    with pytest.raises(ValueError):
        validate(data)
    data["plots"][0]["crop"] = "wheat"
    assert validate(data) == data
    data["tutorial"] = {"done": True, "plot": None}
    assert validate(data) == data
