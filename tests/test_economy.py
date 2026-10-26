from copy import deepcopy
import pytest
from config.data import ANIMALS, BUILDINGS, CATALOG, CROPS, geometric_price
from game.engine import Farm, GameError
from game.storage import SaveStore
from tools.simulation import earn_to, full_playthrough


def test_complete_gameplay(farm, clock):
    report = full_playthrough(farm, clock)
    assert report["crops_tested"] == list(CROPS)
    assert set(report["buildings"]) == set(BUILDINGS)
    assert all(report["animals"][key] > 0 for key in ANIMALS)
    assert report["plots"] == 12
    assert farm.count("chicken") == 9
    saved = deepcopy(farm.state)
    restored = Farm(farm.store, clock)
    assert restored.state == saved
    clock.skip(6 * 3600)
    expected = sum(
        (int((clock() - a["paid_until"]) // ANIMALS[a["species"]]["seconds"]))
        * a["count"]
        * ANIMALS[a["species"]]["reward"]
        for a in saved["animals"]
        if ANIMALS[a["species"]]["seconds"]
    )
    assert restored.advance() == expected
    assert restored.advance() == 0
    assert restored.state["coins"] == saved["coins"] + expected


@pytest.mark.parametrize("key", CROPS)
def test_each_crop_exact_boundary_and_single_harvest(farm, clock, key):
    earn_to(farm, clock, CROPS[key]["unlock"] + CROPS[key]["seed"])
    assert key in farm.state["unlocked"]
    before = farm.state["coins"]
    farm.plant(0, key)
    assert farm.state["coins"] == before - CROPS[key]["seed"]
    with pytest.raises(GameError):
        farm.plant(0, "wheat")
    assert farm.stage(0) == 0
    clock.skip(CROPS[key]["seconds"] * 0.1)
    assert farm.stage(0) == 1
    clock.skip(CROPS[key]["seconds"] * 0.4)
    assert farm.stage(0) == 2
    clock.skip(CROPS[key]["seconds"] * 0.5 - 1)
    with pytest.raises(GameError):
        farm.harvest(0)
    clock.skip(1)
    assert farm.stage(0) == 3
    assert farm.harvest(0) == CROPS[key]["reward"]
    with pytest.raises(GameError):
        farm.harvest(0)
    assert farm.state["coins"] == before - CROPS[key]["seed"] + CROPS[key]["reward"]


@pytest.mark.parametrize("species", ANIMALS)
def test_all_species_individual_payments(farm, clock, species):
    animal = ANIMALS[species]
    building = animal["building"]
    earn_to(farm, clock, BUILDINGS[building]["cost"] + animal["cost"] * 5)
    farm.construct(building)
    farm.buy_animal(species)
    if not animal["seconds"]:
        clock.skip(40 * 3600)
        assert farm.advance() == 0
        assert farm.hourly() == 0
        return
    clock.skip(animal["seconds"] // 2)
    farm.buy_animal(species)
    assert farm.advance() == 0
    clock.skip(animal["seconds"] // 2)
    assert farm.advance() == animal["reward"]
    clock.skip(animal["seconds"] // 2)
    assert farm.advance() == animal["reward"]
    clock.skip(animal["seconds"] * 10)
    assert farm.advance() == 20 * animal["reward"]


def test_rejected_actions_are_atomic(farm):
    before = deepcopy(farm.state)
    for action in (
        lambda: farm.construct("barn"),
        lambda: farm.buy_animal("chicken"),
        farm.expand,
        lambda: farm.plant(0, "pumpkin"),
        lambda: farm.plant(-1, "wheat"),
        lambda: farm.plant(True, "wheat"),
        lambda: farm.construct("invalid"),
    ):
        with pytest.raises(GameError):
            action()
        assert farm.state == before


def test_prices_exact_unlimited_expansion(farm, clock):
    # Reaching >5 plots must remain an economic operation, independent of visuals.
    for i in range(15):
        assert farm.expansion_price() == geometric_price(120, 35, i)
        earn_to(farm, clock, farm.expansion_price())
        farm.expand()
    assert len(farm.state["plots"]) == 17
    assert geometric_price(80, 12, 100) == (80 * 112**100 + 100**100 - 1) // 100**100


def test_duplicate_building_and_recovery(farm, clock):
    earn_to(farm, clock, 220)
    farm.construct("coop")
    with pytest.raises(GameError):
        farm.construct("coop")
    with pytest.raises(GameError):
        farm.recover()
    # A valid edge-state save can spend all liquidity on permanent investments.
    farm.state["coins"] = 0
    assert farm.can_recover()
    farm.recover()
    assert farm.state["coins"] == 5
    farm.plant(0, "wheat")
    assert not farm.can_recover()
    with pytest.raises(GameError):
        farm.recover()
    clock.skip(3600)
    assert farm.harvest(0) == 20


@pytest.mark.parametrize("absence", [0, 60, 1799, 1800, 3600, 14400, 28800, 86400])
def test_offline_cap_and_unlimited_crop_growth(tmp_path, clock, absence):
    farm = Farm(SaveStore(tmp_path / "offline.json"), clock)
    earn_to(farm, clock, 2000)
    farm.construct("coop")
    farm.buy_animal("chicken")
    farm.plant(0, "pumpkin")
    before = farm.state["coins"]
    clock.skip(absence)
    reopened = Farm(farm.store, clock)
    expected = (min(absence, CATALOG["offline_limit"]) // 1800) * 15
    assert reopened.offline_reward == expected
    assert reopened.state["coins"] == before + expected
    assert reopened.remaining(0) == max(0, 28800 - absence)
    twice = Farm(farm.store, clock)
    assert twice.offline_reward == 0
    assert twice.state["coins"] == reopened.state["coins"]
    clock.skip(1800)
    assert twice.advance() == 15


def test_partial_cycles_survive_offline_cap(farm, clock):
    earn_to(farm, clock, 500)
    farm.construct("coop")
    farm.buy_animal("chicken")
    clock.skip(900)
    farm.advance()
    farm.save()
    clock.skip(10 * 3600)
    reopened = Farm(farm.store, clock)
    assert reopened.offline_reward == 8 * 15
    clock.skip(899)
    assert reopened.advance() == 0
    clock.skip(1)
    assert reopened.advance() == 15


def test_backwards_clock_cannot_repeat_payments_or_harvest(farm, clock):
    earn_to(farm, clock, 500)
    farm.construct("coop")
    farm.buy_animal("chicken")
    farm.plant(0, "wheat")
    clock.skip(3600)
    farm.advance()
    farm.harvest(0)
    before = deepcopy(farm.state)
    clock.skip(-86400)
    assert farm.advance() == 0
    farm.save()
    restored = Farm(farm.store, clock)
    assert restored.state == before
    clock.skip(86400)
    assert restored.advance() == 0
    with pytest.raises(GameError):
        restored.harvest(0)
    clock.skip(1800)
    assert restored.advance() == 15
