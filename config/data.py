"""Single source of truth; also resolves data from a PyInstaller bundle."""

import json
from pathlib import Path
import sys

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
CATALOG = json.loads((ROOT / "config" / "catalog.json").read_text(encoding="utf-8"))
CROPS = CATALOG["crops"]
ANIMALS = CATALOG["animals"]
BUILDINGS = CATALOG["buildings"]
SCENES = ("fields", *BUILDINGS)
NAMES = {"fields": "Plantações", **{key: value["name"] for key, value in BUILDINGS.items()}}


def geometric_price(base: int, percent: int, count: int) -> int:
    """Exact integer arithmetic, rounded upwards; independent of float precision."""
    numerator = base * (100 + percent) ** count
    denominator = 100**count
    return (numerator + denominator - 1) // denominator
