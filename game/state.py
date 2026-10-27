"""Strict save validation; all money is integer-valued."""

from copy import deepcopy
from config.data import ANIMALS, BUILDINGS, CATALOG, CROPS, SCENES

# Unix epoch through the final fractional second of year 9999 UTC. The upper
# bound is the exclusive start of year 10000, not an arbitrary gameplay-age cap.
MIN_TIMESTAMP = 0
MAX_TIMESTAMP = 253_402_300_800


def number(value):
    """Validate saved timestamps without converting arbitrarily large integers."""
    return type(value) in (int, float) and MIN_TIMESTAMP <= value < MAX_TIMESTAMP


def integer(value):
    return type(value) is int and value >= 0


def fresh(now):
    return {
        "version": 1,
        "coins": CATALOG["initial_coins"],
        "plots": [None] * CATALOG["initial_plots"],
        "buildings": [],
        "animals": [],
        "unlocked": [key for key, crop in CROPS.items() if crop["unlock"] == 0],
        "earned": 0,
        "animal_earned": 0,
        "harvests": 0,
        "last_accounted": now,
        "preferences": {"on_top": False, "scene": "fields"},
    }


def validate(data):
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Versão de salvamento não reconhecida.")
    for key in ("coins", "earned", "animal_earned", "harvests"):
        if not integer(data.get(key)):
            raise ValueError(f"Campo inválido: {key}")
    if not number(data.get("last_accounted")):
        raise ValueError("Relógio inválido no salvamento.")
    plots = data.get("plots")
    if not isinstance(plots, list) or len(plots) < CATALOG["initial_plots"]:
        raise ValueError("Terrenos inválidos.")
    for plot in plots:
        if plot is not None and (
            not isinstance(plot, dict) or plot.get("crop") not in CROPS or not number(plot.get("planted_at"))
        ):
            raise ValueError("Plantação inválida.")
    for key, allowed in (("buildings", BUILDINGS), ("unlocked", CROPS)):
        values = data.get(key)
        if (
            not isinstance(values, list)
            or any(not isinstance(v, str) or v not in allowed for v in values)
            or len(values) != len(set(values))
        ):
            raise ValueError(f"Catálogo inválido: {key}")
    animals = data.get("animals")
    if not isinstance(animals, list):
        raise ValueError("Animais inválidos.")
    for animal in animals:
        if (
            not isinstance(animal, dict)
            or animal.get("species") not in ANIMALS
            or not integer(animal.get("count"))
            or animal["count"] < 1
            or not number(animal.get("paid_until"))
            or ANIMALS[animal["species"]]["building"] not in data["buildings"]
        ):
            raise ValueError("Lote de animais inválido.")
    prefs = data.get("preferences")
    if (
        not isinstance(prefs, dict)
        or type(prefs.get("on_top")) is not bool
        or prefs.get("scene") not in SCENES
    ):
        raise ValueError("Preferências inválidas.")
    return deepcopy(data)
