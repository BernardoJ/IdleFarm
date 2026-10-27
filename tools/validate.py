"""Run a real virtual-clock playthrough and capture all day/night environments."""
# ruff: noqa: E402 -- direct script entry needs repository path and Qt platform before imports

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QFontMetrics, QImage
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QToolButton
from PIL import Image, ImageDraw, ImageFont
from config.data import SCENES, NAMES
from game.engine import Farm
from game.storage import SaveStore
from tools.simulation import VirtualClock, full_playthrough
from tools.font_checks import check_readable_fonts
from ui.window import FarmWindow
from visual.scene import time_label


def gallery_font():
    for name in ("DejaVuSans.ttf", "arial.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, 14)
        except OSError:
            continue
    return ImageFont.load_default(size=14)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "qa-output")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="idlefarm-qa-") as directory:
        clock = VirtualClock()
        farm = Farm(SaveStore(Path(directory) / "save.json"), clock)
        report = full_playthrough(farm, clock)
        # Screenshots use a separate visual preview clock, not a gameplay speed flag.
        window = FarmWindow(farm)
        window.show()
        if not window.pages.isVisible():
            window.toggle_manage()
        app.processEvents()
        clipped = []
        font_checks = {}
        scene_images = {}
        for scene in SCENES:
            window.navigate(scene)
            window.refresh()
            app.processEvents()
            for hour, period in ((12, "day"), (23, "night")):
                moment = datetime(2026, 1, 1, hour)
                window.scene.qa_moment = moment
                window.scene.qa_phase = 1
                window.time_info.setText(time_label(hour) + moment.strftime(" · %H:%M"))
                window.scene.repaint()
                app.processEvents()
                window.grab().save(str(output / f"{scene}-{period}.png"))
                font_checks[f"{scene}-{period}.png"] = check_readable_fonts(window)
                raw = window.renderer.render(farm, scene, moment, phase=1)
                raw.save(str(output / f"{scene}-{period}-scene.png"))
                scene_images[scene, period] = Image.open(output / f"{scene}-{period}-scene.png").convert(
                    "RGB"
                )
            for button in window.findChildren(QPushButton) + window.findChildren(QToolButton):
                if (
                    button.isVisible()
                    and QFontMetrics(button.font()).horizontalAdvance(button.text()) > button.width() - 14
                ):
                    clipped.append({"scene": scene, "text": button.text(), "width": button.width()})
            for item in window.findChildren(QLabel):
                if item.isVisible() and item.text() and item.wordWrap():
                    required = item.heightForWidth(item.width())
                    if required > item.height() + 2:
                        clipped.append(
                            {
                                "scene": scene,
                                "text": item.text(),
                                "required_height": required,
                                "height": item.height(),
                            }
                        )
        for period in ("day", "night"):
            gallery = Image.new("RGB", (1536, 624), "#263b32")
            draw = ImageDraw.Draw(gallery)
            font = gallery_font()
            for i, scene in enumerate(SCENES):
                x, y = (i % 3) * 512, (i // 3) * 312
                gallery.paste(
                    scene_images[scene, period].resize((512, 288), Image.Resampling.NEAREST), (x, y + 24)
                )
                draw.text(
                    (x + 10, y + 3),
                    NAMES[scene] + " · " + ("DIA" if period == "day" else "NOITE"),
                    fill="#e6c780",
                    font=font,
                )
            gallery.save(output / f"gallery-{period}.png")
        # A real animation preview uses the renderer, never a gameplay time multiplier.
        animation = []
        for phase in (0, 1, 2, 3, 4, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 29, 32, 35):
            gallery = Image.new("RGB", (1536, 624), "#263b32")
            draw = ImageDraw.Draw(gallery)
            for i, scene in enumerate(SCENES):
                raw = window.renderer.render(farm, scene, datetime(2026, 1, 1, 12), phase=phase)
                rgba = raw.convertToFormat(QImage.Format_RGBA8888)
                frame = Image.frombytes(
                    "RGBA",
                    (raw.width(), raw.height()),
                    bytes(rgba.constBits()),
                ).convert("RGB")
                x, y = (i % 3) * 512, (i // 3) * 312
                gallery.paste(frame, (x, y + 24))
                draw.text((x + 10, y + 3), NAMES[scene], fill="#e6c780", font=font)
            animation.append(gallery)
        animation[0].save(
            output / "animations.gif", save_all=True, append_images=animation[1:], duration=300, loop=0
        )
        report.update(
            {
                "ok": not clipped and all(check["ok"] for check in font_checks.values()),
                "clipped_controls": clipped,
                "font_checks": font_checks,
                "font_failures": [
                    {"capture": name, **failure}
                    for name, check in font_checks.items()
                    for failure in check["missing"]
                ],
                "scenes_captured": 12,
                "logical_resolution": [512, 288],
                "animation_preview_frames": len(animation),
                "device_pixel_ratio": window.devicePixelRatioF(),
                "platform": sys.platform,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "application_tests": "Use python -m pytest for the complete suite.",
            }
        )
        (output / "validation.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        window.close()
        app.processEvents()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if os.getenv("GITHUB_ACTIONS") == "true":
        for control in clipped:
            print("::error title=IdleFarm layout::" + json.dumps(control, ensure_ascii=True))
        for failure in report["font_failures"]:
            print("::error title=IdleFarm fonts::" + json.dumps(failure, ensure_ascii=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
