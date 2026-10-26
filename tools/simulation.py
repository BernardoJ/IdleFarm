"""Legitimate accelerated gameplay: never grants coins or changes the OS clock."""

from config.data import ANIMALS, BUILDINGS, CROPS


class VirtualClock:
    def __init__(self, value=1_800_000_000.0):
        self.value = value

    def __call__(self):
        return self.value

    def skip(self, seconds):
        self.value += seconds


def earn_to(farm, clock, target):
    rounds = 0
    while farm.state["coins"] < target:
        crop = max(farm.state["unlocked"], key=lambda key: CROPS[key]["reward"] - CROPS[key]["seed"])
        for index, plot in enumerate(farm.state["plots"]):
            if plot is None and farm.state["coins"] >= CROPS[crop]["seed"]:
                farm.plant(index, crop)
        growing = [i for i, p in enumerate(farm.state["plots"]) if p]
        if not growing:
            if farm.can_recover():
                farm.recover()
            crop = "wheat"
            farm.plant(0, crop)
            growing = [0]
        clock.skip(max(farm.remaining(i) for i in growing))
        farm.advance()
        for i in growing:
            farm.harvest(i)
        rounds += 1
        if rounds > 10000:
            raise AssertionError("Progression stopped")


def full_playthrough(farm, clock):
    assert farm.state["coins"] == 50 and len(farm.state["plots"]) == 2
    farm.plant(0, "wheat")
    farm.plant(1, "carrot")
    clock.skip(7200)
    assert farm.harvest(0) == 20
    assert farm.harvest(1) == 50
    crops_tested = ["wheat", "carrot"]
    for key, crop in list(CROPS.items())[2:]:
        while key not in farm.state["unlocked"]:
            earn_to(farm, clock, farm.state["coins"] + 400)
        earn_to(farm, clock, crop["seed"])
        farm.plant(0, key)
        clock.skip(crop["seconds"])
        assert farm.harvest(0) == crop["reward"]
        crops_tested.append(key)
    for _ in range(10):
        earn_to(farm, clock, farm.expansion_price())
        farm.expand()
    for key, building in BUILDINGS.items():
        earn_to(farm, clock, building["cost"])
        farm.construct(key)
        for species, animal in ANIMALS.items():
            if animal["building"] == key:
                earn_to(farm, clock, farm.animal_price(species))
                farm.buy_animal(species)
    for _ in range(8):
        earn_to(farm, clock, farm.animal_price("chicken"))
        farm.buy_animal("chicken")
    for i in range(len(farm.state["plots"])):
        key = tuple(CROPS)[i % 5]
        earn_to(farm, clock, CROPS[key]["seed"])
        if farm.state["plots"][i] is None:
            farm.plant(i, key)
    clock.skip(max(farm.remaining(i) for i in range(len(farm.state["plots"]))))
    farm.advance()
    farm.save()
    return {
        "crops_tested": crops_tested,
        "buildings": farm.state["buildings"].copy(),
        "animals": {key: farm.count(key) for key in ANIMALS},
        "plots": len(farm.state["plots"]),
        "coins": farm.state["coins"],
        "earned": farm.state["earned"],
        "virtual_hours": (clock.value - 1_800_000_000) / 3600,
    }
