"""Bounded cached light plates with windows, warm lamps and local actor light."""

from dataclasses import dataclass
from datetime import datetime
import math
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPolygon


@dataclass(frozen=True)
class LightFrame:
    background: QImage
    foreground: QImage
    night: float
    daylight: float
    warmth: float


def weights(hour):
    stops = (
        (0, "night"),
        (5, "night"),
        (6.5, "dawn"),
        (8, "day"),
        (16, "day"),
        (18, "dusk"),
        (20, "night"),
        (24, "night"),
    )
    for (lo, first), (hi, second) in zip(stops, stops[1:]):
        if lo <= hour <= hi:
            t = (hour - lo) / (hi - lo)
            return first, second, t * t * (3 - 2 * t)
    return "night", "night", 0


def blend(first, second, amount):
    if amount == 0:
        return first.copy()
    result = first.copy()
    painter = QPainter(result)
    painter.setOpacity(amount)
    painter.drawImage(0, 0, second)
    painter.end()
    return result


class Lighting:
    def __init__(self, backgrounds, foregrounds, scenes):
        self.scenes = scenes
        self.plates = {}
        for scene, source in backgrounds.items():
            for kind in ("day", "dawn", "dusk", "night"):
                image = source.copy()
                painter = QPainter(image)
                interior = scenes[scene]["interior"]
                tint = {
                    "day": (255, 255, 255),
                    "dawn": (211, 194, 191),
                    "dusk": (228, 172, 126),
                    "night": (111, 128, 164) if interior else (78, 105, 157),
                }[kind]
                painter.setCompositionMode(QPainter.CompositionMode_Multiply)
                painter.fillRect(image.rect(), QColor(*tint))
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                if kind == "night":
                    for x, y, w, h in scenes[scene]["windows"]:
                        painter.fillRect(x, y, w, h, QColor(20, 36, 67, 175))
                        painter.fillRect(x + w // 3, y + 4, 1, 1, QColor("#b6c6d0"))
                    for x, y in scenes[scene]["lamps"]:
                        self.pool(painter, x, y, 1)
                painter.end()
                foreground = image.copy()
                painter = QPainter(foreground)
                painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
                painter.drawImage(0, 0, foregrounds[scene])
                painter.end()
                self.plates[scene, kind] = image, foreground

    def at(self, scene, moment=None):
        moment = moment or datetime.now()
        hour = moment.hour + moment.minute / 60 + moment.second / 3600 + moment.microsecond / 3_600_000_000
        a, b, t = weights(hour)
        first, second = self.plates[scene, a], self.plates[scene, b]
        night = (1 - t if a == "night" else 0) + (t if b == "night" else 0)
        daylight = (1 - t if a == "day" else 0) + (t if b == "day" else 0)
        warmth = (1 - t if a == "dusk" else 0) + (t if b == "dusk" else 0)
        return LightFrame(
            blend(first[0], second[0], t), blend(first[1], second[1], t), night, daylight, warmth
        )

    @staticmethod
    def pool(painter, x, y, amount):
        # Discrete light rings preserve pixel edges and reveal the wall and floor.
        for radius, alpha in ((75, 7), (54, 10), (34, 15), (19, 24), (9, 40)):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(247, 169, 74, round(alpha * amount)))
            painter.drawEllipse(x - radius, y - radius // 2, radius * 2, radius)
            painter.drawEllipse(x - radius, y + 26, radius * 2, radius // 2)

    def actor(self, source, scene, x, y, light):
        sprite = source.copy()
        painter = QPainter(sprite)
        painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
        if light.night:
            nearest = min(math.hypot(x - lx, y - ly) for lx, ly in self.scenes[scene]["lamps"])
            shadow = min(1, nearest / 170)
            painter.fillRect(sprite.rect(), QColor(24, 38, 71, round(125 * light.night * shadow)))
            painter.fillRect(sprite.rect(), QColor(236, 156, 67, round(35 * light.night * (1 - shadow))))
        if light.warmth:
            painter.fillRect(sprite.rect(), QColor(236, 150, 78, round(light.warmth * 35)))
        painter.end()
        return sprite

    def beams(self, painter, scene, light, phase):
        if not light.daylight and not light.warmth:
            return
        painter.setPen(Qt.NoPen)
        color = QColor(255, 219, 143, round(10 * light.daylight + 16 * light.warmth))
        painter.setBrush(color)
        for x, y, w, h in self.scenes[scene]["windows"]:
            painter.drawPolygon(
                QPolygon(
                    [
                        QPoint(x, y + h),
                        QPoint(x + w, y + h),
                        QPoint(x + w + 52, y + h + 134),
                        QPoint(x + 16, y + h + 134),
                    ]
                )
            )
            for i in range(5):
                px = x + 14 + (i * 17) % max(1, w + 20) + round(math.sin(phase * 0.3 + i) * 3)
                py = y + h + 20 + int((phase * 3 + i * 23) % 100)
                painter.fillRect(px, py, 1, 1, QColor(255, 234, 180, 100))

    def lamps(self, painter, scene, light, phase):
        for index, (x, y) in enumerate(self.scenes[scene]["lamps"]):
            painter.setPen(QColor("#302d2b"))
            painter.setBrush(QColor("#4b473b"))
            painter.drawRect(x - 3, y - 4, 7, 12)
            painter.drawArc(x - 2, y - 8, 5, 6, 0, 180 * 16)
            brightness = 1 if int(phase * 5 + index) % 7 else 0.85
            painter.fillRect(x - 2, y - 2, 5, 7, QColor(246, 182, 78, round(130 + 100 * light.night)))
            if light.night > 0.1:
                painter.fillRect(x, y - 1, 1, 4, QColor(255, round(222 * brightness), 151))
