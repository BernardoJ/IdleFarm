"""Bounded rendering with original atlases and local-time lighting."""

from datetime import datetime
import math
import time
from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QWidget

from config.data import ANIMALS, CROPS, ROOT, SCENES

POSITIONS = ((53, 105), (91, 121), (132, 106), (173, 122), (211, 105))
ANIMAL_KEYS = tuple(ANIMALS)
CROP_KEYS = tuple(CROPS)


def lighting(hour):
    stops = (
        (0, (17, 29, 60, 145)),
        (5, (17, 29, 60, 145)),
        (6.5, (142, 100, 137, 55)),
        (8, (235, 244, 194, 0)),
        (16, (235, 244, 194, 0)),
        (18, (221, 132, 68, 65)),
        (20, (17, 29, 60, 145)),
        (24, (17, 29, 60, 145)),
    )
    for (lo, a), (hi, b) in zip(stops, stops[1:]):
        if lo <= hour <= hi:
            t = (hour - lo) / (hi - lo)
            t = t * t * (3 - 2 * t)
            return QColor(*(round(a[i] * (1 - t) + b[i] * t) for i in range(4)))
    return QColor(17, 29, 60, 145)


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
        self.backgrounds = {key: self._load(key + ".png") for key in SCENES}
        self.animals = self._load("animals.png")
        self.crops = self._load("crops.png")

    @staticmethod
    def _load(name):
        image = QImage(str(ROOT / "assets" / name))
        if image.isNull():
            raise RuntimeError(f"Recurso gráfico ausente: {name}")
        return image

    def icon(self, key, frame=0):
        if key in CROPS:
            return self.crops.copy(CROP_KEYS.index(key) * 32, 3 * 32, 32, 32)
        return self.animals.copy(ANIMAL_KEYS.index(key) * 32, frame * 32, 32, 32)

    def render(self, farm, scene, moment=None, phase=0, selected=0):
        moment = moment or datetime.now()
        hour = moment.hour + moment.minute / 60 + moment.second / 3600
        image = self.backgrounds[scene].copy()
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        # Low-cost ambient movement, independent from the simulation clock.
        for i in range(3):
            x = int((phase * (1 + i * 0.25) + i * 79) % 302) - 35
            y = 10 + i * 9
            for dx, dy, w, h in ((0, 5, 23, 3), (5, 1, 12, 6), (12, 3, 18, 5)):
                painter.fillRect(x + dx, y + dy, w, h, QColor("#d8d7b4"))
        reps = farm.representatives(scene)
        for index, identifier in enumerate(reps):
            x, y = POSITIONS[index]
            if scene == "fields":
                crop = farm.state["plots"][identifier]["crop"]
                stage = farm.stage(identifier)
                source = QRect(CROP_KEYS.index(crop) * 32, stage * 32, 32, 32)
                painter.drawImage(QPoint(x - 16, y - 24), self.crops, source)
                if identifier == selected:
                    painter.setPen(QColor("#e9ce8a"))
                    painter.drawRect(x - 17, y - 12, 33, 18)
                if stage == 3 and int(phase * 2 + index) % 3 == 0:
                    painter.fillRect(x + 9, y - 24, 1, 5, QColor("#f7e7a2"))
                    painter.fillRect(x + 7, y - 22, 5, 1, QColor("#f7e7a2"))
            else:
                frame = int(phase * 2 + index) % 4
                # Small bounded stroll, with occasional still/resting frames.
                dx = round(math.sin(phase * 0.45 + index * 2) * 4)
                source = QRect(ANIMAL_KEYS.index(identifier) * 32, frame * 32, 32, 32)
                painter.drawImage(QPoint(x - 16 + dx, y - 27), self.animals, source)
        tint = lighting(hour)
        painter.fillRect(image.rect(), tint)
        night = max(0, min(1, (tint.alpha() - 60) / 85))
        if night:
            # Stepped warm window light; no blur or filtered pixels.
            for x, y in ((40, 78), (94, 80)):
                for size, alpha in ((13, 20), (8, 40), (4, 100)):
                    painter.fillRect(
                        x - size // 2, y - size // 2, size, size, QColor(245, 185, 91, round(alpha * night))
                    )
            for i in range(10):
                if math.sin(phase * 1.7 + i) > 0:
                    x = int(23 + i * 23 + math.sin(phase + i) * 3)
                    y = int(89 + (i * 17) % 43 + math.cos(phase * 0.8 + i) * 2)
                    painter.fillRect(x, y, 1, 1, QColor("#e9d494"))
            for i in range(16):
                painter.fillRect(
                    12 + (i * 47) % 237, 3 + (i * 11) % 25, 1, 1, QColor(202, 214, 208, round(100 * night))
                )
        else:
            painter.setPen(QColor("#4c655d"))
            for i in range(3):
                x = int((phase * 9 + i * 12) % 285) - 15
                y = 16 + i * 3
                dy = int(phase * 4) % 2
                painter.drawLine(x - 2, y - dy, x, y + 1)
                painter.drawLine(x, y + 1, x + 2, y - dy)
        for i in range(4):
            x = int((phase * 5 + i * 67) % 256)
            y = int(61 + (phase * 3 + i * 19) % 75)
            painter.fillRect(x, y, 2, 1, QColor("#b2b46a"))
        painter.end()
        return image


class SceneWidget(QWidget):
    plot_selected = Signal(int)

    def __init__(self, farm, renderer, parent=None):
        super().__init__(parent)
        self.farm, self.renderer = farm, renderer
        self.scene = farm.state["preferences"]["scene"]
        self.selected = 0
        self.started = time.monotonic()
        self.qa_moment = None
        self.setMinimumHeight(288)
        self.setMaximumHeight(288)
        self.setToolTip("Arraste o cenário para mover a janela. Clique numa plantação para selecioná-la.")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(83)
        self.drag_origin = None
        self.target = QRect()

    def paintEvent(self, event):
        image = self.renderer.render(
            self.farm, self.scene, self.qa_moment, time.monotonic() - self.started, self.selected
        )
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#22372e"))
        # Integer scale in PHYSICAL pixels, including fractional Windows DPI.
        dpr = self.devicePixelRatioF()
        scale = max(1, min(int(self.width() * dpr / 256), int(self.height() * dpr / 144)))
        w, h = round(256 * scale / dpr), round(144 * scale / dpr)
        self.target = QRect((self.width() - w) // 2, (self.height() - h) // 2, w, h)
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(self.target, image)
        p.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self.drag_origin = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
        if self.scene == "fields" and self.target.contains(event.position().toPoint()):
            x = (event.position().x() - self.target.x()) * 256 / self.target.width()
            y = (event.position().y() - self.target.y()) * 144 / self.target.height()
            for identifier, (px, py) in zip(self.farm.representatives("fields"), POSITIONS):
                if abs(x - px) < 18 and abs(y - py) < 17:
                    self.plot_selected.emit(identifier)
                    self.drag_origin = None
                    break

    def mouseMoveEvent(self, event):
        if self.drag_origin is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self.drag_origin)

    def mouseReleaseEvent(self, event):
        self.drag_origin = None
