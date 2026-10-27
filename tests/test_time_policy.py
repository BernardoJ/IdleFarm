"""Resuming and reopening use the same bounded real-time production policy."""

from copy import deepcopy
import math

import pytest

from config.data import CATALOG
from game.engine import Farm, GameError
from game.persistence import SaveStatus
from game.state import MAX_TIMESTAMP
from game.storage import SaveStore
from tools.simulation import earn_to


class WallClock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value

    def skip(self, seconds):
        self.value += seconds


def production_farm(path, clock):
    farm = Farm(SaveStore(path), clock)
    earn_to(farm, clock, 2000)
    farm.construct("coop")
    farm.buy_animal("chicken")
    farm.plant(0, "pumpkin")
    return farm


@pytest.mark.parametrize("absence", [1800, 7200, 14400, 28800], ids=["30min", "2h", "4h", "8h"])
def test_resume_and_reopen_have_identical_first_tick_and_saved_progress(tmp_path, absence):
    clock = WallClock(1_800_000_000.0)
    seed = production_farm(tmp_path / "seed.json", clock)
    original = deepcopy(seed.state)
    live_clock, closed_clock = WallClock(clock()), WallClock(clock())
    live_store, closed_store = SaveStore(tmp_path / "live.json"), SaveStore(tmp_path / "closed.json")
    live_store.save(original)
    closed_store.save(original)
    live = Farm(live_store, live_clock)
    Farm(closed_store, closed_clock)
    live_clock.skip(absence)
    closed_clock.skip(absence)

    resumed_reward = live.advance()
    reopened = Farm(closed_store, closed_clock)
    expected_reward = min(absence, CATALOG["offline_limit"]) // 1800 * 15
    assert resumed_reward == reopened.offline_reward == expected_reward
    assert live.last_elapsed == reopened.last_elapsed == absence
    assert live.last_capped is reopened.last_capped is (absence > CATALOG["offline_limit"])
    assert live.state == reopened.state
    assert live.remaining(0) == reopened.remaining(0) == max(0, 28800 - absence)
    assert live.advance() == reopened.advance() == 0
    assert live.state == reopened.state

    # Saving immediately after the first resumed tick preserves the accounted
    # high-water mark: reopening must not credit that absence a second time.
    live.save()
    reopened.save()
    live_again, closed_again = Farm(live_store, live_clock), Farm(closed_store, closed_clock)
    assert live_again.offline_reward == closed_again.offline_reward == 0
    assert live_again.state == closed_again.state == live.state


def test_active_short_ticks_keep_full_income_beyond_four_total_hours(tmp_path):
    clock = WallClock(1_800_000_000.0)
    farm = production_farm(tmp_path / "save.json", clock)
    balance = farm.state["coins"]
    gains = []
    for _ in range(16):
        clock.skip(1800)
        gains.append(farm.advance())
    assert gains == [15] * 16
    assert farm.state["coins"] == balance + 240
    assert not farm.last_capped
    assert farm.remaining(0) == 0


@pytest.mark.parametrize("reopen", [False, True], ids=["resume", "reopen"])
def test_partial_animal_cycle_is_preserved_across_capped_absence(tmp_path, reopen):
    clock = WallClock(1_800_000_000.0)
    farm = production_farm(tmp_path / "save.json", clock)
    clock.skip(900)
    assert farm.advance() == 0
    farm.save()
    before = farm.state["coins"]
    clock.skip(8 * 3600)
    if reopen:
        farm = Farm(farm.store, clock)
        assert farm.offline_reward == 120
    else:
        assert farm.advance() == 120
    assert farm.state["coins"] == before + 120
    assert farm.last_capped
    clock.skip(899)
    assert farm.advance() == 0
    clock.skip(1)
    assert farm.advance() == 15
    assert farm.advance() == 0
    farm.save()
    assert Farm(farm.store, clock).offline_reward == 0


def test_backward_clock_never_regresses_growth_or_repeats_production(tmp_path):
    clock = WallClock(1_800_000_000.0)
    farm = production_farm(tmp_path / "save.json", clock)
    started = clock()
    clock.skip(1800)
    assert farm.advance() == 15
    before, remaining = deepcopy(farm.state), farm.remaining(0)
    clock.value = started - 3600
    assert farm.advance() == 0
    assert farm.state == before and farm.remaining(0) == remaining
    assert farm.last_elapsed == 0 and not farm.last_capped
    farm.save()
    recovered = Farm(farm.store, clock)
    assert recovered.offline_reward == 0 and recovered.state == before
    clock.value = started + 1800
    assert recovered.advance() == 0
    clock.skip(1800)
    assert recovered.advance() == 15


def test_forward_clock_jump_is_capped_and_its_watermark_cannot_be_replayed(tmp_path):
    clock = WallClock(1_800_000_000.0)
    farm = production_farm(tmp_path / "save.json", clock)
    started, balance = clock(), farm.state["coins"]
    clock.skip(8 * 3600)
    assert farm.advance() == 120 and farm.last_capped
    assert farm.state["coins"] == balance + 120
    assert farm.remaining(0) == 0
    high_water_state = deepcopy(farm.state)
    clock.value = started + 3600
    assert farm.advance() == 0 and farm.state == high_water_state
    assert farm.remaining(0) == 0
    farm.save()
    restored = Farm(farm.store, clock)
    assert restored.offline_reward == 0 and restored.state == high_water_state
    clock.value = started + 8 * 3600 + 1800
    assert restored.advance() == 15


@pytest.mark.parametrize(
    "sample",
    [10**10000, float("nan"), float("inf"), float("-inf"), True, "later", None, -1, MAX_TIMESTAMP],
    ids=[
        "huge-int",
        "nan",
        "infinity",
        "negative-infinity",
        "boolean",
        "text",
        "none",
        "negative",
        "year10000",
    ],
)
def test_invalid_wall_clock_samples_freeze_at_last_valid_watermark(tmp_path, sample):
    clock = WallClock(1_800_000_000.0)
    farm = production_farm(tmp_path / "save.json", clock)
    before, saved = deepcopy(farm.state), farm.store.path.read_bytes()
    clock.value = sample
    assert farm.now == before["last_accounted"]
    assert farm.advance() == 0
    assert farm.last_elapsed == 0 and not farm.last_capped
    assert farm.state == before
    assert farm.store.path.read_bytes() == saved
    assert farm.remaining(0) == 28800


def test_failed_save_after_resume_retries_without_recrediting_absence(tmp_path, monkeypatch):
    clock = WallClock(1_800_000_000.0)
    farm = production_farm(tmp_path / "save.json", clock)
    balance, saved = farm.state["coins"], farm.store.path.read_bytes()
    clock.skip(8 * 3600)
    assert farm.advance() == 120
    original_save = farm.store.save

    def fail(snapshot):
        raise OSError("simulated disk failure after resume")

    monkeypatch.setattr(farm.store, "save", fail)
    with pytest.raises(OSError):
        farm.save()
    assert farm.persistence.status == SaveStatus.ERROR
    assert farm.store.path.read_bytes() == saved
    assert farm.advance() == 0
    assert farm.state["coins"] == balance + 120
    monkeypatch.setattr(farm.store, "save", original_save)
    farm.save()
    assert farm.persistence.status == SaveStatus.SAVED
    restored = Farm(farm.store, clock)
    assert restored.offline_reward == 0 and restored.state == farm.state


def test_new_farm_rejects_invalid_initial_clock_without_creating_progress(tmp_path):
    store = SaveStore(tmp_path / "save.json")
    with pytest.raises(GameError, match="horário"):
        Farm(store, clock=lambda: 10**10000)
    assert not store.path.exists() and not store.backup.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("sample", [float("nan"), 10**10000], ids=["nan", "huge-int"])
def test_existing_progress_opens_with_invalid_clock_without_overwriting_it(tmp_path, sample):
    clock = WallClock(1_800_000_000.0)
    farm = production_farm(tmp_path / "save.json", clock)
    original, saved = deepcopy(farm.state), farm.store.path.read_bytes()
    reopened = Farm(farm.store, clock=lambda: sample)
    assert reopened.offline_reward == 0 and reopened.state == original
    assert farm.store.path.read_bytes() == saved


def test_last_valid_fractional_clock_second_can_be_saved_without_overflow(tmp_path):
    clock = WallClock(1_800_000_000.0)
    farm = production_farm(tmp_path / "save.json", clock)
    clock.value = math.nextafter(float(MAX_TIMESTAMP), 0)
    assert farm.advance() == 120 and farm.last_capped
    assert farm.state["last_accounted"] == clock()
    farm.save()
    assert Farm(farm.store, clock).offline_reward == 0
    clock.value = MAX_TIMESTAMP
    assert farm.advance() == 0
    assert farm.state["last_accounted"] < MAX_TIMESTAMP
