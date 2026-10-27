"""Deterministic farm simulation. Rendering limits never enter economic calculations."""

from collections import Counter
from copy import deepcopy
from functools import wraps
import time

from config.data import ANIMALS, BUILDINGS, CATALOG, CROPS, SCENES, geometric_price
from game.state import fresh, validate
from game.persistence import SaveProgress


class GameError(ValueError):
    """An expected, user-readable action failure."""


class PendingSaveError(OSError):
    """The business action completed once; only persistence needs a retry."""

    def __init__(self, error, result=None):
        super().__init__("A ação foi aplicada nesta janela, mas ainda não foi possível salvar.")
        self.result = result
        self.error = error


def transaction(method):
    @wraps(method)
    def atomic(self, *args, **kwargs):
        self.advance()
        before = deepcopy(self.state)
        try:
            result = method(self, *args, **kwargs)
        except Exception:
            # Roll back an invalid business action and propagate its original error.
            self.state = before
            raise
        if self.state != before:
            self.persistence.changed()
        # A completed purchase stays pending in memory if writing fails. Retrying
        # persistence must never execute the purchase or charge the player again.
        try:
            self.save()
        except OSError as exc:
            raise PendingSaveError(exc, result) from exc
        return result

    return atomic


class Farm:
    def __init__(self, store=None, clock=time.time):
        self.store, self.clock = store, clock
        data = store.load() if store else None
        self.state = validate(data) if data else fresh(clock())
        self.persistence = SaveProgress()
        self._persisted_state = deepcopy(data)
        if data is not None:
            self.persistence.saved_generation = 0
        self.offline_reward = self.advance(offline=True)
        self.save()  # Commit the offline payment before showing it, preventing reopening exploits.

    @property
    def now(self):
        return max(self.clock(), self.state["last_accounted"])

    def save(self):
        if self.persistence.saving or self.store is None:
            return False
        if self.state != self._persisted_state and not self.persistence.dirty:
            self.persistence.changed()
        if not self.persistence.dirty and self.persistence.last_error is None:
            return True
        snapshot = deepcopy(self.state)
        generation = self.persistence.begin()
        try:
            self.store.save(snapshot)
        except OSError as exc:
            self.persistence.fail(exc)
            raise
        self._persisted_state = snapshot
        if self.state != snapshot and self.persistence.generation == generation:
            self.persistence.changed()
        self.persistence.complete(generation)
        return not self.persistence.dirty

    def advance(self, offline=False):
        now = self.now
        last = self.state["last_accounted"]
        elapsed = now - last
        credited = min(elapsed, CATALOG["offline_limit"]) if offline else elapsed
        end = last + credited
        gain = 0
        for animal in self.state["animals"]:
            species = ANIMALS[animal["species"]]
            if not species["seconds"]:
                continue
            cycles = max(0, int((end - animal["paid_until"]) // species["seconds"]))
            gain += cycles * species["reward"] * animal["count"]
            animal["paid_until"] += cycles * species["seconds"] + (elapsed - credited)
        self.state["last_accounted"] = now
        self.state["coins"] += gain
        self.state["earned"] += gain
        self.state["animal_earned"] += gain
        self._unlock()
        if now != last or gain:
            self.persistence.changed()
        return gain

    def _unlock(self):
        for key, crop in CROPS.items():
            if self.state["earned"] >= crop["unlock"] and key not in self.state["unlocked"]:
                self.state["unlocked"].append(key)

    def _pay(self, cost):
        if self.state["coins"] < cost:
            raise GameError("Moedas insuficientes.")
        self.state["coins"] -= cost

    def _plot(self, index):
        if type(index) is not int or not 0 <= index < len(self.state["plots"]):
            raise GameError("Terreno não encontrado.")
        return self.state["plots"][index]

    def remaining(self, index):
        plot = self._plot(index)
        return max(0, CROPS[plot["crop"]]["seconds"] - (self.now - plot["planted_at"])) if plot else 0

    def stage(self, index):
        plot = self._plot(index)
        if not plot:
            return 0
        elapsed = self.now - plot["planted_at"]
        total = CROPS[plot["crop"]]["seconds"]
        # Compare elapsed time directly: 1 - remaining / duration loses precision at 10%.
        return 3 if elapsed >= total else 2 if elapsed >= total / 2 else 1 if elapsed >= total / 10 else 0

    @transaction
    def plant(self, index, crop):
        if crop not in CROPS or crop not in self.state["unlocked"]:
            raise GameError("Cultura ainda bloqueada.")
        if self._plot(index) is not None:
            raise GameError("Este terreno já está ocupado.")
        self._pay(CROPS[crop]["seed"])
        self.state["plots"][index] = {"crop": crop, "planted_at": self.now}

    @transaction
    def harvest(self, index):
        plot = self._plot(index)
        if not plot or self.remaining(index) > 0:
            raise GameError("A plantação ainda não está pronta.")
        gain = CROPS[plot["crop"]]["reward"]
        self.state["coins"] += gain
        self.state["earned"] += gain
        self.state["harvests"] += 1
        self.state["plots"][index] = None
        self._unlock()
        return gain

    def expansion_price(self):
        return geometric_price(
            CATALOG["expansion_base"],
            CATALOG["expansion_growth_percent"],
            len(self.state["plots"]) - CATALOG["initial_plots"],
        )

    @transaction
    def expand(self):
        self._pay(self.expansion_price())
        self.state["plots"].append(None)

    @transaction
    def construct(self, building):
        if building not in BUILDINGS:
            raise GameError("Construção desconhecida.")
        if building in self.state["buildings"]:
            raise GameError("Esta construção já foi adquirida.")
        self._pay(BUILDINGS[building]["cost"])
        self.state["buildings"].append(building)

    def count(self, species):
        return sum(a["count"] for a in self.state["animals"] if a["species"] == species)

    def animal_price(self, species):
        return geometric_price(
            ANIMALS[species]["cost"], CATALOG["animal_growth_percent"], self.count(species)
        )

    @transaction
    def buy_animal(self, species):
        if species not in ANIMALS:
            raise GameError("Espécie desconhecida.")
        if ANIMALS[species]["building"] not in self.state["buildings"]:
            raise GameError("Construa a instalação primeiro.")
        self._pay(self.animal_price(species))
        self.state["animals"].append({"species": species, "count": 1, "paid_until": self.now})

    def hourly(self, building=None):
        # UI estimate only. Actual payments use integer cycles, never this float.
        return sum(
            a["count"] * ANIMALS[a["species"]]["reward"] * 3600 / ANIMALS[a["species"]]["seconds"]
            for a in self.state["animals"]
            if ANIMALS[a["species"]]["seconds"]
            and (building is None or ANIMALS[a["species"]]["building"] == building)
        )

    def next_production(self, species):
        seconds = ANIMALS[species]["seconds"]
        times = [
            max(0, a["paid_until"] + seconds - self.now)
            for a in self.state["animals"]
            if a["species"] == species
        ]
        return min(times) if times and seconds else None

    def can_recover(self):
        return (
            self.state["coins"] < CATALOG["recovery_coins"]
            and all(plot is None for plot in self.state["plots"])
            and self.hourly() == 0
        )

    @transaction
    def recover(self):
        if not self.can_recover():
            raise GameError("As sementes de recomeço estão disponíveis apenas sem outras fontes de renda.")
        self.state["coins"] = CATALOG["recovery_coins"]

    @transaction
    def preference(self, key, value):
        if (key == "on_top" and type(value) is bool) or (key == "scene" and value in SCENES):
            self.state["preferences"][key] = value
        else:
            raise GameError("Preferência inválida.")

    def representatives(self, scene):
        """Diversity first, capped at five; identifiers are real owned plot indices/species."""
        if scene == "fields":
            entries = [(i, p["crop"]) for i, p in enumerate(self.state["plots"]) if p]
        else:
            counts = Counter()
            for animal in self.state["animals"]:
                if ANIMALS[animal["species"]]["building"] == scene:
                    counts[animal["species"]] += animal["count"]
            entries = [(species, species) for species, count in counts.items() for _ in range(min(5, count))]
        selected, rest, seen = [], [], set()
        for identifier, species in entries:
            if species not in seen:
                seen.add(species)
                selected.append(identifier)
            else:
                rest.append(identifier)
        return (selected + rest)[:5]
