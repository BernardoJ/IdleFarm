"""Original, deterministic, native-resolution pixel art. Pillow is build-time only.

No source assets are copied from PescaIdle. All silhouettes, textures, palettes
and animation frames are authored here and exported as checked-in PNGs.
"""

from pathlib import Path
import random
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
INK = "#293c37"
WOOD = ("#654532", "#96613d", "#bd8752", "#e0b773")
GRASS = ("#426c48", "#537f4b", "#689354", "#7fa75b", "#a0b968")
SCENES = ("fields", "coop", "barn", "pigsty", "stable", "kennel")
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


def tree(d, x, y, seed, small=False):
    r = random.Random(seed)
    scale = 0.7 if small else 1

    def box(bounds, color):
        a, b, c, e = bounds
        d.ellipse(
            (x + int(a * scale), y + int(b * scale), x + int(c * scale), y + int(e * scale)), fill=color
        )

    d.ellipse((x - 10, y - 2, x + 13, y + 4), fill="#41643f")
    d.rectangle((x - 2, y - 31 * scale, x + 3, y), fill=WOOD[0])
    d.line((x + 2, y - 24 * scale, x + 2, y - 2), fill=WOOD[2])
    d.line((x, y - 16 * scale, x - 8, y - 26 * scale), fill=WOOD[0], width=2)
    for bounds in ((-17, -44, 14, -20), (-23, -34, 18, -10), (-13, -51, 11, -23)):
        box(bounds, "#2e5941")
    for _ in range(50):
        xx, yy = r.randint(-17, 12), r.randint(-43, -15)
        if ((xx / 20) ** 2 + ((yy + 29) / 22) ** 2) < 1:
            box(
                (xx, yy, xx + r.randint(3, 8), yy + r.randint(2, 5)),
                r.choice(("#3f7448", "#548a4d", "#76a454")),
            )
    for _ in range(9):
        xx, yy = r.randint(-13, 8), r.randint(-42, -21)
        d.line((x + xx, y + yy, x + xx + 2, y + yy), fill="#a3bb66")


def fence(d, x1, x2, y):
    for yy in (y - 9, y - 4):
        d.rectangle((x1, yy, x2, yy + 2), fill=WOOD[0])
        d.line((x1, yy, x2, yy), fill=WOOD[2])
    for x in range(x1, x2 + 1, 13):
        d.rectangle((x, y - 12, x + 3, y + 2), fill=WOOD[0])
        d.rectangle((x, y - 12, x + 1, y), fill=WOOD[3])
        d.point((x + 2, y - 8), fill=INK)


def building(d, x, y, w, h, roof, kind="barn"):
    d.ellipse((x - 5, y + h - 2, x + w + 8, y + h + 7), fill="#3e623f")
    d.rectangle((x, y, x + w, y + h), fill=WOOD[0], outline=INK)
    for xx in range(x + 1, x + w, 5):
        d.rectangle((xx, y + 1, xx + 3, y + h - 1), fill=WOOD[1 if kind != "barn" else 0])
        d.line((xx + 1, y + 4, xx + 1, y + h - 3), fill=WOOD[2 if kind != "barn" else 1])
    d.rectangle((x - 1, y + h - 3, x + w + 2, y + h), fill="#9a9e85")
    for xx in range(x, x + w, 7):
        d.line((xx, y + h - 2, xx + 4, y + h - 2), fill="#c4bea1")
    d.polygon(
        ((x - 5, y), (x + w // 2, y - 23), (x + w + 6, y), (x + w + 3, y + 5), (x - 5, y + 5)), fill=INK
    )
    d.polygon(((x - 4, y - 1), (x + w // 2, y - 21), (x + w + 3, y - 1)), fill=roof[0])
    for yy in range(y - 18, y, 4):
        lo = x + int((y - yy) * w / 46)
        hi = x + w - int((y - yy) * w / 46)
        if hi >= lo:
            d.line((lo, yy, hi, yy), fill=roof[1])
            for xx in range(lo + 3, hi, 8):
                d.line((xx, yy, xx - 1, yy + 2), fill=roof[2])
    d.line((x - 4, y, x + w // 2, y - 21), fill=roof[2], width=2)
    d.rectangle((x - 5, y + 1, x + w + 5, y + 4), fill=WOOD[0])
    d.line((x - 4, y + 1, x + w + 4, y + 1), fill=WOOD[3])
    door = x + w // 2 - 9
    d.rectangle((door, y + 9, door + 18, y + h - 3), fill=INK)
    d.rectangle((door + 2, y + 10, door + 16, y + h - 4), fill="#513e32")
    d.line((door + 9, y + 10, door + 9, y + h - 4), fill=WOOD[2])
    d.line((door + 2, y + 12, door + 15, y + h - 6), fill=WOOD[3])
    d.line((door + 15, y + 12, door + 2, y + h - 6), fill=WOOD[2])
    for xx in (x + 7, x + w - 15):
        d.rectangle((xx, y + 10, xx + 8, y + 19), fill=INK)
        d.rectangle((xx + 1, y + 11, xx + 7, y + 18), fill="#dcae61")
        d.line((xx + 4, y + 11, xx + 4, y + 18), fill=WOOD[0])
        d.line((xx + 1, y + 15, xx + 7, y + 15), fill=WOOD[0])
    if kind == "coop":
        d.rectangle((x + w + 1, y + 14, x + w + 13, y + 29), fill=WOOD[0])
        d.line((x + w + 2, y + 15, x + w + 13, y + 26), fill=WOOD[3], width=2)
        for yy in range(y + 17, y + 30, 4):
            d.line((x + w + 3, yy, x + w + 10, yy), fill=WOOD[1])


def hay(d, x, y):
    d.rectangle((x, y, x + 14, y + 9), fill="#886b37", outline=WOOD[0])
    d.rectangle((x + 1, y + 1, x + 13, y + 7), fill="#c6a657")
    for yy in (y + 2, y + 4, y + 6):
        d.line((x + 2, yy, x + 12, yy), fill="#e2c777")
    for xx in (x + 4, x + 10):
        d.line((xx, y, xx, y + 8), fill="#785d35")


def trough(d, x, y):
    d.polygon(((x, y), (x + 18, y), (x + 15, y + 8), (x + 2, y + 8)), fill=WOOD[0])
    d.rectangle((x + 2, y + 1, x + 15, y + 3), fill="#648e98")
    d.line((x + 3, y + 1, x + 13, y + 1), fill="#a3c2bf")
    d.line((x + 3, y + 5, x + 15, y + 5), fill=WOOD[2])


def background(scene, index):
    r = random.Random(331 + index)
    im = Image.new("RGB", (256, 144))
    d = ImageDraw.Draw(im)
    for y in range(58):
        d.line((0, y, 255, y), fill=(105 + y // 3, 158 + y // 3, 172 + y // 4))
    d.ellipse((200, 12, 213, 25), fill="#efdb98")
    d.polygon(
        (
            (0, 52),
            (32, 21),
            (54, 43),
            (88, 15),
            (121, 42),
            (154, 24),
            (188, 43),
            (232, 23),
            (256, 44),
            (256, 70),
            (0, 70),
        ),
        fill="#7c9b98",
    )
    d.polygon(
        (
            (0, 58),
            (18, 47),
            (48, 54),
            (69, 36),
            (98, 59),
            (132, 43),
            (159, 55),
            (184, 39),
            (217, 57),
            (245, 46),
            (256, 50),
            (256, 77),
            (0, 77),
        ),
        fill="#5c8072",
    )
    d.rectangle((0, 60, 255, 143), fill=GRASS[1])
    for _ in range(2800):
        x, y = r.randrange(256), r.randrange(62, 144)
        d.line((x, y, x + r.randrange(1, 4), y), fill=r.choice(GRASS))
    # Winding worn path, with darker margins and individual cobbles.
    path = (
        (120, 59),
        (133, 59),
        (146, 80),
        (153, 96),
        (186, 122),
        (210, 144),
        (184, 144),
        (162, 121),
        (136, 101),
        (132, 83),
    )
    d.polygon(path, fill="#a99562")
    for _ in range(180):
        x, y = r.randrange(116, 214), r.randrange(62, 144)
        if im.getpixel((x, y)) == (169, 149, 98):
            d.line((x, y, x + 2, y), fill=r.choice(("#bda773", "#c9b985", "#938256")))
    for x in range(0, 257, 18):
        tree(d, x, 65 + (x % 9), r.randrange(9999), small=True)
    roofs = (
        ("#a66448", "#bf8052", "#e4af75"),
        ("#75613d", "#a28a4b", "#d1b96e"),
        ("#854d48", "#ab6450", "#d18b67"),
        ("#646e63", "#859087", "#bdc0a1"),
        ("#65516a", "#887088", "#b6999b"),
        ("#826048", "#ab8557", "#dcaf70"),
    )
    if scene == "fields":
        building(d, 24, 62, 61, 30, roofs[index], "house")
        d.rectangle((36, 39, 42, 50), fill=WOOD[1])
        d.line((35, 39, 43, 39), fill=WOOD[3], width=2)
        # Decorative orchard and well, never extra crop representatives.
        for x, y in ((215, 82), (240, 94)):
            tree(d, x, y, x)
        d.ellipse((94, 81, 110, 88), fill=INK)
        d.rectangle((95, 82, 109, 89), fill="#7a8b83")
        d.ellipse((96, 80, 108, 85), fill="#45656b")
        d.line((95, 80, 95, 68), fill=WOOD[0], width=2)
        d.line((109, 80, 109, 68), fill=WOOD[0], width=2)
        d.polygon(((91, 69), (102, 62), (114, 69)), fill=roofs[index][0])
    else:
        building(
            d, 32 if scene != "kennel" else 25, 66, 75 if scene != "kennel" else 40, 32, roofs[index], scene
        )
        if scene == "coop":
            for x in (137, 159):
                d.rectangle((x, 70, x + 14, 80), fill=WOOD[0])
                d.ellipse((x + 2, 74, x + 11, 78), fill="#d3ba70")
            fence(d, 137, 185, 66)
            trough(d, 211, 114)
            d.line((158, 76, 187, 76), fill=WOOD[3], width=2)
        elif scene == "barn":
            for x, y in ((115, 83), (120, 73), (132, 83)):
                hay(d, x, y)
            trough(d, 211, 105)
            d.line((157, 64, 157, 82), fill=WOOD[0], width=2)
            d.line((151, 65, 163, 65), fill="#b6b7a0", width=2)
        elif scene == "pigsty":
            d.ellipse((153, 91, 236, 128), fill="#655546")
            d.ellipse((159, 95, 230, 124), fill="#806450")
            for _ in range(60):
                x, y = r.randrange(165, 229), r.randrange(101, 121)
                d.line((x, y, x + 3, y), fill=r.choice(("#91725b", "#705645")))
            trough(d, 119, 86)
        elif scene == "stable":
            hay(d, 117, 85)
            hay(d, 125, 76)
            trough(d, 218, 101)
            d.rectangle((160, 66, 195, 91), fill=WOOD[0])
            for xx in (164, 179):
                d.rectangle((xx, 70, xx + 11, 87), fill="#4a4435")
            d.polygon(((156, 66), (178, 55), (200, 66)), fill=roofs[index][1])
        elif scene == "kennel":
            for x, y in ((98, 74), (155, 79)):
                building(d, x, y, 30, 18, roofs[index], "doghouse")
                d.ellipse((x + 11, y + 8, x + 20, y + 17), fill=INK)
            trough(d, 213, 111)
            d.ellipse((117, 110, 121, 114), fill="#bb6f59")
            d.line((117, 112, 121, 112), fill="#e5bd7c")
    fence(d, 9, 27, 91)
    fence(d, 114 if scene != "fields" else 119, 201, 89)
    for x, y in ((10, 111), (245, 135), (10, 63), (253, 71)):
        tree(d, x, y, x + y + index)
    for _ in range(34):
        x, y = r.choice((r.randrange(4, 33), r.randrange(225, 254))), r.randrange(84, 142)
        d.line((x, y, x, y - 3), fill="#3c6242")
        d.rectangle((x - 1, y - 4, x + 1, y - 3), fill=r.choice(("#e4c37d", "#c99497", "#abc4b2")))
    fence(d, 19, 107, 141)
    fence(d, 219, 255, 141)
    im.save(OUT / f"{scene}.png")


def animal(species, frame):
    im = Image.new("RGBA", (32, 32))
    d = ImageDraw.Draw(im)
    bob = 1 if frame == 1 else 0
    # Draw on a local translated layer to keep feet and gait consistent.
    body = Image.new("RGBA", (32, 32))
    p = ImageDraw.Draw(body)
    if species in ("chicken", "duck", "peacock"):
        colors = {
            "chicken": ("#f3dfb0", "#cba76c"),
            "duck": ("#ebe5c4", "#afbea1"),
            "peacock": ("#3e8f90", "#28636c"),
        }
        light, dark = colors[species]
        if species == "peacock":
            if frame in (2, 3):
                p.ellipse((1, 2, 23, 23), fill="#275f58", outline=INK)
                for x, y in ((5, 8), (11, 5), (17, 8), (3, 14), (20, 14)):
                    p.ellipse((x - 1, y - 1, x + 2, y + 2), fill="#b2a558")
                    p.point((x, y), fill="#377ea1")
            else:
                p.polygon(((4, 23), (1, 10), (8, 14), (10, 6), (13, 23)), fill="#3f8263", outline=INK)
        p.ellipse((7, 14, 24, 26), fill=dark, outline=INK)
        p.ellipse((8, 14, 22, 23), fill=light)
        p.ellipse((10, 18, 18, 23), fill=dark)
        head = "#397c60" if species == "duck" else light
        p.ellipse((20, 9, 28, 18), fill=head, outline=INK)
        p.rectangle((24, 12, 25, 13), fill=INK)
        p.polygon(((27, 14), (31, 15), (27, 17)), fill="#d9a052")
        if species == "chicken":
            p.rectangle((21, 7, 23, 10), fill="#b65349")
            p.rectangle((24, 8, 26, 10), fill="#d36c50")
        if species == "peacock":
            p.line((23, 9, 23, 5), fill="#7bb8ab")
            p.point((22, 4), fill="#c8c17c")
        for x in (12, 21):
            p.line((x, 26, x + (frame % 2), 29), fill="#ca9858")
            p.line((x - 1, 29, x + 2, 29), fill="#ca9858")
        p.polygon(((8, 16), (3, 12), (5, 22)), fill=dark)
    else:
        coats = {
            "cow": ("#eee6c9", "#b2b29a"),
            "goat": ("#c6b28c", "#9b8868"),
            "sheep": ("#f1e9d1", "#c5c5aa"),
            "pig": ("#dca08e", "#b67d72"),
            "horse": ("#aa7652", "#785239"),
            "mutt": ("#a98a65", "#775e46"),
            "beagle": ("#e0c29c", "#9a6846"),
            "collie": ("#ece6d3", "#414c49"),
            "golden": ("#daba79", "#ac8854"),
        }
        light, dark = coats[species]
        is_dog = species in ("mutt", "beagle", "collie", "golden")
        top = 16 if is_dog else 13
        for x in (9, 14, 22, 25):
            step = (frame % 2) if x in (9, 22) else -(frame % 2)
            p.rectangle((x + step, 22, x + step + 2, 28), fill=dark, outline=INK)
            p.line((x + step, 28, x + step + 2, 28), fill=INK)
        p.ellipse((5, top, 26, 25), fill=dark, outline=INK)
        p.ellipse((6, top, 25, 22), fill=light)
        if species == "cow":
            p.polygon(((9, 14), (13, 15), (15, 19), (10, 22), (8, 19)), fill=INK)
            p.rectangle((19, 14, 23, 18), fill="#48514a")
            p.ellipse((13, 23, 20, 26), fill="#c79b88")
        if species == "sheep":
            for x, y in ((7, 14), (12, 12), (18, 12), (23, 15), (10, 19), (17, 18)):
                p.ellipse((x - 3, y - 2, x + 4, y + 4), fill=light, outline="#c1bda1")
        hy = 10 if species == "horse" else 13 if not is_dog else 15
        p.polygon(
            ((21, hy + 1), (24, hy - 3), (29, hy), (30, hy + 8), (25, hy + 10), (21, hy + 7)),
            fill=dark,
            outline=INK,
        )
        p.rectangle((23, hy + 1, 28, hy + 6), fill=light)
        p.point((27, hy + 2), fill=INK)
        p.rectangle((26, hy + 6, 30, hy + 8), fill="#b38f79" if species != "pig" else "#edb6a3")
        p.point((29, hy + 7), fill=INK)
        if species in ("cow", "goat"):
            p.line((22, hy - 1, 20, hy - 5), fill="#dfd6ae", width=2)
            p.line((27, hy - 1, 28, hy - 5), fill="#dfd6ae", width=2)
        if species == "pig":
            p.polygon(((23, hy), (20, hy - 4), (26, hy - 2)), fill="#e4aa99", outline=INK)
            p.arc((1, 18, 7, 24), 0, 300, fill=dark, width=1)
        elif species == "horse":
            p.polygon(((21, hy - 1), (21, hy + 12), (24, hy + 8), (25, hy - 2)), fill=INK)
            p.line((5, 16, 3, 25 + (frame % 2)), fill=INK, width=2)
        elif is_dog:
            p.polygon(((22, hy), (20, hy + 8), (24, hy + 9), (26, hy)), fill=dark)
            p.line((6, 19, 2, 14 - (frame % 2) * 3), fill=dark, width=2)
            if species in ("collie", "beagle"):
                p.polygon(
                    ((9, top), (20, top), (18, 22), (9, 21)),
                    fill="#424b45" if species == "collie" else "#65503d",
                )
            if frame == 3:  # Resting pose; expressive eyes stay distinct.
                p.line((26, hy + 2, 28, hy + 2), fill=INK)
        if species == "goat":
            p.line((27, hy + 9, 26, hy + 12), fill="#e6d7b6", width=2)
    d.ellipse((4, 27, 29, 30), fill=(35, 57, 40, 75))
    im.alpha_composite(body, (0, -bob))
    return im


def crops():
    sheet = Image.new("RGBA", (32 * 5, 32 * 4))
    colors = ("#dac17b", "#e99a54", "#d4bd59", "#cb615a", "#d88a45")
    for c in range(5):
        for stage in range(4):
            cell = Image.new("RGBA", (32, 32))
            d = ImageDraw.Draw(cell)
            d.polygon(((2, 20), (19, 16), (31, 22), (14, 29)), fill="#624734", outline="#3e3e30")
            for x in range(6, 26, 5):
                d.line((x, 21, x + 6, 24), fill="#927049")
            if stage:
                for x, y in ((10, 22), (18, 20), (23, 24)):
                    height = 3 if stage == 1 else 8 if stage == 2 else 12
                    d.line((x, y, x, y - height), fill="#5d8d4c", width=2)
                    d.line((x, y - 2, x - 3, y - 5), fill="#99af62", width=2)
                    d.line((x, y - 3, x + 3, y - 6), fill="#6f9d51", width=2)
                    if stage == 3:
                        if c == 0:
                            for dy in (0, 3, 6):
                                d.line((x - 2, y - height + dy, x + 2, y - height + dy + 1), fill=colors[c])
                        elif c == 1:
                            d.polygon(((x - 2, y - 3), (x + 2, y - 3), (x, y + 2)), fill=colors[c])
                        elif c == 2:
                            d.ellipse((x - 2, y - 10, x + 2, y - 3), fill=colors[c], outline="#ab984b")
                        elif c == 3:
                            d.ellipse((x - 3, y - 4, x + 1, y), fill=colors[c])
                            d.point((x - 1, y - 2), fill="#f1c28d")
                        else:
                            d.ellipse((x - 4, y - 4, x + 3, y + 1), fill=colors[c], outline="#ad643c")
                            d.line((x, y - 3, x, y), fill="#edb65d")
            sheet.alpha_composite(cell, (c * 32, stage * 32))
    sheet.save(OUT / "crops.png")


def main():
    OUT.mkdir(exist_ok=True)
    for i, scene in enumerate(SCENES):
        background(scene, i)
    sheet = Image.new("RGBA", (32 * len(SPECIES), 128))
    for i, species in enumerate(SPECIES):
        for frame in range(4):
            sheet.alpha_composite(animal(species, frame), (i * 32, frame * 32))
    sheet.save(OUT / "animals.png")
    crops()
    icon = Image.new("RGBA", (32, 32), INK)
    d = ImageDraw.Draw(icon)
    d.rectangle((2, 2, 29, 29), fill="#bd9e64")
    d.rectangle((4, 4, 27, 27), fill="#547b4a")
    d.rectangle((8, 15, 24, 26), fill=WOOD[2], outline=INK)
    d.polygon(((5, 15), (16, 6), (27, 15)), fill="#b96f50", outline=INK)
    d.line((8, 14, 16, 8), fill="#e6b77d")
    d.rectangle((14, 20, 18, 26), fill=WOOD[0])
    d.rectangle((10, 18, 12, 20), fill="#f1d790")
    icon.save(OUT / "icon.png")
    icon.resize((256, 256), Image.Resampling.NEAREST).save(
        OUT / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)]
    )
    print("Original backgrounds, crop stages, 48 animal frames and icon generated.")


if __name__ == "__main__":
    main()
