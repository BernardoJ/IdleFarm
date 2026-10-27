"""Export original illustrated sources as deterministic, sharp runtime atlases.

Pillow is an authoring dependency only. Lossless sources live in assets/source;
runtime assets need no generator, network, Pillow or AI service.
"""

from collections import deque
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
SOURCE = OUT / "source"
SIZE = (512, 288)
CELL = 96
SPECIES = (
    "chicken",
    "duck",
    "peacock",
    "cow",
    "goat",
    "sheep",
    "pig",
    "horse",
    "mutt",
    "beagle",
    "collie",
    "golden",
)
SIZES = {
    "chicken": (34, 34),
    "duck": (42, 33),
    "peacock": (62, 48),
    "cow": (80, 65),
    "goat": (58, 49),
    "sheep": (57, 44),
    "pig": (64, 40),
    "horse": (86, 76),
    "mutt": (43, 39),
    "beagle": (48, 39),
    "collie": (58, 45),
    "golden": (63, 48),
}
FEATURES = {
    "fields": ["tilled_soil", "paths", "fences", "trees", "flowers", "stones", "tools", "well"],
    "coop": ["perches", "nests", "eggs", "straw", "feeders", "water", "feed_sacks", "feathers", "beams"],
    "barn": ["hay_bales", "straw", "trough", "buckets", "partitions", "tools", "feed_sacks", "beams"],
    "pigsty": ["mud_pool", "hoofprints", "pens", "trough", "water", "straw", "muddy_walls", "buckets"],
    "stable": ["stalls", "hay_racks", "trough", "saddle", "bridles", "horseshoes", "tools", "beams"],
    "kennel": ["beds", "blankets", "sleeping_cubbies", "bowls", "toys", "balls", "bones", "shelves", "rug"],
}
WINDOWS = {
    "coop": [[143, 9, 32, 25], [341, 8, 35, 26]],
    "barn": [[125, 5, 32, 22], [370, 5, 32, 22]],
    "pigsty": [[116, 8, 44, 22], [357, 8, 45, 22]],
    "stable": [[103, 6, 86, 23], [321, 6, 87, 23]],
    "kennel": [[138, 0, 51, 43], [327, 0, 51, 43]],
}
LAMPS = {
    "coop": [[228, 24], [456, 31]],
    "barn": [[71, 34], [443, 34]],
    "pigsty": [[64, 48], [446, 48]],
    "stable": [[202, 33], [309, 33]],
    "kennel": [[40, 58], [280, 47]],
    "fields": [[43, 78]],
}
FOREGROUND = {
    "fields": [[(0, 230), (60, 230), (102, 288), (0, 288)], [(465, 218), (512, 205), (512, 288), (425, 288)]],
    "coop": [[(0, 235), (172, 235), (181, 288), (0, 288)], [(327, 236), (512, 235), (512, 288), (320, 288)]],
    "barn": [[(0, 203), (144, 197), (164, 264), (0, 273)], [(366, 197), (512, 204), (512, 273), (355, 264)]],
    "pigsty": [
        [(0, 232), (139, 231), (145, 288), (0, 288)],
        [(363, 229), (512, 231), (512, 288), (359, 288)],
    ],
    "stable": [[(0, 225), (80, 215), (103, 288), (0, 288)], [(420, 216), (512, 224), (512, 288), (410, 288)]],
    "kennel": [
        [(0, 225), (112, 230), (242, 271), (242, 288), (0, 288)],
        [(275, 273), (400, 234), (512, 222), (512, 288), (275, 288)],
    ],
}


def opaque_sprite(image):
    """Remove faint generated matte noise; silhouettes use discrete pixel coverage."""
    image = image.convert("RGBA")
    image.putalpha(image.getchannel("A").point(lambda a: 255 if a >= 140 else 0))
    return image


def components(image, crop_grid=False):
    """Extract complete silhouettes, without neighbouring frames or matte specks."""
    width, height = image.size
    pixels = bytearray(image.getchannel("A").tobytes())
    found = {}
    for start in range(len(pixels)):
        if not pixels[start]:
            continue
        pixels[start] = 0
        queue = deque([start])
        left = right = start % width
        top = bottom = start // width
        cluster = []
        while queue:
            index = queue.popleft()
            x, y = index % width, index // width
            left, right = min(left, x), max(right, x)
            top, bottom = min(top, y), max(bottom, y)
            cluster.append((x, y))
            for near in (
                index - 1 if x else -1,
                index + 1 if x < width - 1 else -1,
                index - width,
                index + width,
            ):
                if 0 <= near < len(pixels) and pixels[near]:
                    pixels[near] = 0
                    queue.append(near)
        count = len(cluster)
        if count < (18 if crop_grid else 350):
            continue
        columns, rows = (4, 5) if crop_grid else (6, 4)
        column = min(columns - 1, int((left + right) / 2 / (width / columns)))
        row = (
            max(0, min(rows - 1, round((bottom + 1) / (height / rows)) - 1))
            if crop_grid
            else min(rows - 1, int((top + bottom) / 2 / (height / rows)))
        )
        key = row, column
        if crop_grid:
            found.setdefault(key, []).extend(cluster)
        elif key not in found or len(found[key]) < count:
            found[key] = cluster
    expected = 20 if crop_grid else 24
    if len(found) != expected:
        raise ValueError(f"Expected {expected} complete sprites, found {len(found)}")
    sprites = {}
    for key, cluster in found.items():
        mask = Image.new("L", image.size)
        ImageDraw.Draw(mask).point(cluster, fill=255)
        sprite = image.copy()
        sprite.putalpha(mask)
        sprites[key] = sprite.crop(mask.getbbox())
    return sprites


def export_animals():
    sheet = Image.new("RGBA", (CELL * len(SPECIES), CELL * 6))
    groups = {
        "birds": ("chicken", "duck", "peacock", "pig"),
        "livestock": ("cow", "goat", "sheep", "horse"),
        "dogs": ("mutt", "beagle", "collie", "golden"),
    }
    dimensions = {}
    for name, animals in groups.items():
        sprites = components(opaque_sprite(Image.open(SOURCE / f"{name}.png")))
        for row, species in enumerate(animals):
            frames = [sprites[row, frame] for frame in range(6)]
            width, height = SIZES[species]
            scale = min(width / max(f.width for f in frames), height / max(f.height for f in frames))
            dimensions[species] = []
            for frame, sprite in enumerate(frames):
                sprite = sprite.resize(
                    (round(sprite.width * scale), round(sprite.height * scale)), Image.Resampling.NEAREST
                )
                x, y = (CELL - sprite.width) // 2, CELL - 8 - sprite.height
                sheet.alpha_composite(sprite, (SPECIES.index(species) * CELL + x, frame * CELL + y))
                dimensions[species].append([x, y, sprite.width, sprite.height])
    sheet.save(OUT / "animals.png", optimize=True)
    return dimensions


def export_crops():
    source = opaque_sprite(Image.open(SOURCE / "crop-stages.png"))
    sprites = components(source, crop_grid=True)
    sheet = Image.new("RGBA", (CELL * 5, CELL * 4))
    widths, heights = (66, 66, 66, 72, 78), (55, 46, 68, 44, 51)
    for row in range(5):
        for stage in range(4):
            sprite = sprites[row, stage]
            # Shared scale per species retains growth instead of enlarging sprouts.
            scale = min(widths[row] / (source.width / 4 - 12), heights[row] / (source.height / 5 - 12))
            sprite = sprite.resize(
                (max(1, round(sprite.width * scale)), max(1, round(sprite.height * scale))),
                Image.Resampling.NEAREST,
            )
            sheet.alpha_composite(
                sprite, (row * CELL + (CELL - sprite.width) // 2, stage * CELL + CELL - 8 - sprite.height)
            )
    sheet.save(OUT / "crops.png", optimize=True)


def main():
    scenes = {}
    for scene, features in FEATURES.items():
        background = Image.open(SOURCE / f"{scene}.png").convert("RGB").resize(SIZE, Image.Resampling.NEAREST)
        background.save(OUT / f"{scene}.png", optimize=True)
        mask = Image.new("L", SIZE)
        draw = ImageDraw.Draw(mask)
        for polygon in FOREGROUND[scene]:
            draw.polygon(polygon, fill=255)
        foreground = background.convert("RGBA")
        foreground.putalpha(mask)
        foreground.save(OUT / f"{scene}-foreground.png", optimize=True)
        scenes[scene] = {
            "interior": scene != "fields",
            "features": features,
            "windows": WINDOWS.get(scene, []),
            "lamps": LAMPS[scene],
            "foreground_depth": 264,
            "walkable": [92, 151, 420, 250],
        }
    dimensions = export_animals()
    export_crops()
    manifest = {
        "version": 2,
        "resolution": list(SIZE),
        "cell": CELL,
        "animal_frames": 6,
        "species": list(SPECIES),
        "sprite_bounds": dimensions,
        "animations": {
            "idle": [0, 1, 0, 0],
            "walk": [2, 0, 3, 0],
            "feed": [0, 4, 4, 0],
            "rest": [0, 5, 5, 0],
            "display": [0, 1, 1, 0],
        },
        "scenes": scenes,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Exported 6 backgrounds, 6 foregrounds, 72 animal frames and 20 crop stages at 512×288.")


if __name__ == "__main__":
    main()
