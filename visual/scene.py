"""Layered 512×288 scenes, bounded sprites and independent local-time lighting."""

import json
import math
import time
from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from config.data import ANIMALS, BUILDINGS, CROPS, ROOT, SCENES
from visual.animation import pose
from visual.lighting import Lighting, weights

WIDTH, HEIGHT, CELL = 512, 288, 96
POSITIONS = ((135, 167), (180, 221), (268, 167), (341, 221), (400, 167))
ANIMAL_KEYS = tuple(ANIMALS)
CROP_KEYS = tuple(CROPS)


def field_layout(farm):
    """Back-to-front plot anchors; stable ties retain their original draw order."""
    return sorted(
        zip(farm.representatives("fields"), POSITIONS),
        key=lambda item: item[1][1],
    )


def lighting(hour):
    """Continuous representative ambient tint, also exposed for preview tools."""
    first, second, amount = weights(hour)
    colors = {
        "night": (27, 42, 78, 91),
        "dawn": (142, 100, 137, 45),
        "day": (235, 244, 194, 0),
        "dusk": (221, 132, 68, 50),
    }
    return QColor(*(round(a * (1 - amount) + b * amount) for a, b in zip(colors[first], colors[second])))


def time_label(hour):
    return (
        "AMANHECER"
        if 5 <= hour < 8
        else "DIA"
        if 8 <= hour < 17
        else "ENTARDECER"
        if 17 <= hour < 20
        else "NOITE"
    )


class Renderer:
    def __init__(self):
        self.manifest = json.loads((ROOT / "assets/manifest.json").read_text(encoding="utf-8"))
        if self.manifest["resolution"] != [WIDTH, HEIGHT]:
            raise RuntimeError("Resolução dos recursos incompatível.")
        self.backgrounds = {key: self._load(key + ".png") for key in SCENES}
        self.foregrounds = {key: self._load(key + "-foreground.png") for key in SCENES}
        self.animals = self._load("animals.png")
        self.crops = self._load("crops.png")
        self.light = Lighting(self.backgrounds, self.foregrounds, self.manifest["scenes"])
        # Fixed-size atlas slices, reused regardless of the number of owned animals.
        self.animal_frames = {
            (key, frame): self.animals.copy(index * CELL, frame * CELL, CELL, CELL)
            for index, key in enumerate(ANIMAL_KEYS)
            for frame in range(6)
        }
        self.crop_frames = {
            (key, stage): self.crops.copy(index * CELL, stage * CELL, CELL, CELL)
            for index, key in enumerate(CROP_KEYS)
            for stage in range(4)
        }

    @staticmethod
    def _load(name):
        image = QImage(str(ROOT / "assets" / name))
        if image.isNull():
            raise RuntimeError(f"Recurso gráfico ausente: {name}")
        return image.convertToFormat(QImage.Format_ARGB32_Premultiplied)

    def icon(self, key, frame=0):
        if key in BUILDINGS or key == "fields":
            return self.backgrounds[key].scaled(80, 45, Qt.KeepAspectRatio, Qt.FastTransformation)
        if key in CROPS:
            return self.crop_frames[key, 3].copy(9, 16, 78, 73)
        x, y, width, height = self.manifest["sprite_bounds"][key][frame]
        return self.animal_frames[key, frame].copy(x, y, width, height)

    def entities(self, farm, scene, phase):
        return sorted(
            ((key, pose(scene, key, index, phase)) for index, key in enumerate(farm.representatives(scene))),
            key=lambda item: item[1].y,
        )

    def render(self, farm, scene, moment=None, phase=0, selected=0):
        light = self.light.at(scene, moment)
        image = light.background
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        self.light.beams(painter, scene, light, phase)
        if scene == "fields":
            for identifier, (x, y) in field_layout(farm):
                key = farm.state["plots"][identifier]["crop"]
                stage = farm.stage(identifier)
                sway = round(math.sin(phase * 0.8 + x)) if stage > 1 else 0
                sprite = self.light.actor(self.crop_frames[key, stage], scene, x, y, light)
                painter.drawImage(QPoint(x - CELL // 2 + sway, y - CELL + 8), sprite)
                if identifier == selected:
                    painter.setPen(QColor("#ffdf91"))
                    # Corner marks keep the plants visible and identify the selected bed.
                    for side in (-1, 1):
                        xx = x + side * 37
                        painter.drawLine(xx, y + 5, xx - side * 7, y + 5)
                        painter.drawLine(xx, y + 5, xx, y - 2)
                if stage == 3 and int(phase * 2 + identifier) % 5 == 0:
                    painter.setPen(QColor("#fff2bd"))
                    painter.drawLine(x + 22, y - 51, x + 22, y - 45)
                    painter.drawLine(x + 19, y - 48, x + 25, y - 48)
        else:
            for key, state in self.entities(farm, scene, phase):
                x, y = state.x, state.y
                bounds = self.manifest["sprite_bounds"][key][state.frame]
                shadow_width = round(bounds[2] * 0.8)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(32, 24, 23, 90))
                painter.drawEllipse(x - shadow_width // 2, y - 3, shadow_width, 7)
                sprite = self.animal_frames[key, state.frame]
                if state.mirrored:
                    sprite = sprite.flipped(Qt.Horizontal)
                sprite = self.light.actor(sprite, scene, x, y, light)
                painter.drawImage(QPoint(x - CELL // 2, y - CELL + 8), sprite)
                if scene == "pigsty" and 155 < x < 350 and state.behaviour in ("walk", "rest"):
                    painter.setPen(QColor(190, 151, 105, 100))
                    radius = 3 + int((phase * 3) % 8)
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(x - radius, y - 2, radius * 2, 5)
        # Original foreground alpha owns fence/plant occlusion, after feet-sorted actors.
        painter.drawImage(0, 0, light.foreground)
        self.ambient(painter, scene, phase, light)
        self.light.lamps(painter, scene, light, phase)
        painter.end()
        return image

    def ambient(self, painter, scene, phase, light):
        if scene == "fields":
            for index in range(6):
                x = round(40 + index * 83 + math.sin(phase * 0.5 + index) * 8)
                y = round(106 + (index * 37) % 142 + math.cos(phase * 0.7 + index) * 6)
                if light.night > 0.6:
                    if math.sin(phase + index) > 0:
                        painter.fillRect(x, y, 1, 2, QColor("#f5d894"))
                else:
                    wing = 2 if int(phase * 4 + index) % 2 else 1
                    painter.fillRect(x - wing, y, wing * 2 + 1, 2, QColor("#ead6a0"))
                    painter.fillRect(x, y, 1, 3, QColor("#69593f"))
        else:
            # Tiny water glints and drifting straw/dust stay within each room.
            for index in range(4):
                x = 104 + (index * 73) % 290 + round(math.sin(phase * 0.3 + index) * 2)
                y = 155 + int((phase * 1.4 + index * 29) % 85)
                painter.fillRect(x, y, 1 + index % 2, 1, QColor(230, 202, 148, 40))
            if scene == "pigsty":
                painter.setPen(QColor(191, 177, 144, 95))
                painter.setBrush(Qt.NoBrush)
                radius = 5 + int(phase * 2) % 15
                painter.drawEllipse(265 - radius, 192, radius * 2, radius // 3 + 2)
            water = {
                "coop": (459, 129),
                "barn": (380, 65),
                "pigsty": (311, 82),
                "stable": (475, 163),
                "kennel": (432, 81),
            }
            x, y = water[scene]
            for index in range(3):
                shift = round(math.sin(phase * 1.1 + index) * 3)
                painter.fillRect(
                    x - 5 + shift,
                    y + index * 2,
                    5 - index,
                    1,
                    QColor(182, 218, 216, round(30 + light.daylight * 50)),
                )


class SceneWidget(QWidget):
    plot_selected = Signal(int)

    def __init__(self, farm, renderer, parent=None):
        super().__init__(parent)
        self.farm, self.renderer = farm, renderer
        self.scene = "fields"
        self.selected = 0
        self.started = time.monotonic()
        self.qa_moment = None
        self.qa_phase = None
        self.setMinimumHeight(HEIGHT)
        self.setMaximumHeight(HEIGHT * 2)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setToolTip("Arraste o cenário para mover a janela. Clique numa plantação para selecioná-la.")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(100)
        self.drag_origin = None
        self.target = QRect()

    def sizeHint(self):
        return QSize(WIDTH, HEIGHT)

    def paintEvent(self, event):
        phase = self.qa_phase if self.qa_phase is not None else time.monotonic() - self.started
        image = self.renderer.render(self.farm, self.scene, self.qa_moment, phase, self.selected)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#242b25"))
        dpr = self.devicePixelRatioF()
        scale = max(1, min(int(self.width() * dpr / WIDTH), int(self.height() * dpr / HEIGHT)))
        width, height = round(WIDTH * scale / dpr), round(HEIGHT * scale / dpr)
        self.target = QRect((self.width() - width) // 2, (self.height() - height) // 2, width, height)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        painter.drawImage(self.target, image)
        painter.setPen(QColor("#b8955d"))
        painter.drawRect(self.target.adjusted(-1, -1, 0, 0))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self.drag_origin = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
        if self.scene == "fields" and self.target.contains(event.position().toPoint()):
            x = (event.position().x() - self.target.x()) * WIDTH / self.target.width()
            y = (event.position().y() - self.target.y()) * HEIGHT / self.target.height()
            for identifier, (px, py) in reversed(field_layout(self.farm)):
                if abs(x - px) < 39 and py - 70 < y < py + 12:
                    self.plot_selected.emit(identifier)
                    self.drag_origin = None
                    break

    def mouseMoveEvent(self, event):
        if self.drag_origin is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self.drag_origin)

    def mouseReleaseEvent(self, event):
        self.drag_origin = None
