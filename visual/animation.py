"""Small deterministic visual behaviours, independent of farm quantity and money."""

from dataclasses import dataclass
import math

HOMES = {
    "coop": ((145, 188), (255, 174), (356, 195), (207, 232), (328, 239)),
    "barn": ((157, 183), (280, 211), (357, 176), (205, 242), (346, 241)),
    "pigsty": ((180, 207), (288, 202), (364, 227), (212, 244), (329, 240)),
    "stable": ((167, 215), (339, 211), (255, 174), (200, 245), (330, 244)),
    "kennel": ((143, 191), (250, 177), (359, 194), (205, 234), (321, 234)),
}


@dataclass(frozen=True)
class Pose:
    x: int
    y: int
    frame: int
    behaviour: str
    mirrored: bool = False


def smooth(value):
    return value * value * (3 - 2 * value)


def pose(scene, species, index, seconds):
    """Feet remain anchored in idle; only walking changes the world position."""
    x, y = HOMES[scene][index]
    cycle = (seconds + index * 5.3) % 36
    offset, mirrored = 0, False
    if cycle < 7:
        behaviour = "display" if species == "peacock" and 2 < cycle < 4 else "idle"
        frame = 1 if behaviour == "display" or int(cycle * 1.4) % 5 == 1 else 0
    elif cycle < 13:
        behaviour = "walk"
        offset = round(10 * smooth((cycle - 7) / 6))
        frame = (2, 0, 3, 0)[int((cycle - 7) * 4) % 4]
    elif cycle < 19:
        behaviour, offset = "feed", 10
        frame = 0 if cycle < 13.7 or cycle > 18.3 else 4
    elif cycle < 25:
        behaviour, mirrored = "walk", True
        offset = round(10 * (1 - smooth((cycle - 19) / 6)))
        frame = (3, 0, 2, 0)[int((cycle - 19) * 4) % 4]
    else:
        behaviour = "rest"
        frame = 0 if cycle < 26 or cycle > 35 else 5
    return Pose(
        x + offset, y + (round(math.sin(cycle) * 1) if behaviour == "walk" else 0), frame, behaviour, mirrored
    )
