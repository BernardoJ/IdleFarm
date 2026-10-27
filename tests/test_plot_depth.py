"""Mouse selection must choose the same topmost plot that the player sees."""

from datetime import datetime

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest

import visual.scene as scene_module
from visual.scene import CELL, HEIGHT, WIDTH, Renderer, SceneWidget


@pytest.fixture
def scene_widget(app, farm):
    farm.plant(0, "wheat")
    farm.plant(1, "carrot")
    renderer = Renderer()
    widget = SceneWidget(farm, renderer)
    widget.qa_moment = datetime(2026, 1, 1, 12)
    widget.qa_phase = 0
    widget.resize(700, 420)
    widget.show()
    app.processEvents()
    try:
        yield widget
    finally:
        widget.timer.stop()
        widget.close()
        app.processEvents()


def logical_click(widget, x, y):
    target = widget.target
    point = QPoint(
        round(target.x() + x * target.width() / WIDTH),
        round(target.y() + y * target.height() / HEIGHT),
    )
    QTest.mouseClick(widget, Qt.LeftButton, pos=point)


@pytest.mark.parametrize(
    "positions,expected",
    [
        (((220, 180), (230, 210)), 1),
        (((230, 210), (220, 180)), 0),
        (((220, 190), (230, 190)), 1),
    ],
    ids=["front-listed-last", "front-listed-first", "equal-y-last-drawn-wins"],
)
def test_overlapping_click_selects_last_drawn_plot(scene_widget, monkeypatch, positions, expected):
    monkeypatch.setattr(scene_module, "POSITIONS", positions)
    renderer = scene_widget.renderer
    colors = (QColor("#da3652"), QColor("#36ce52"))
    for crop, color in zip(("wheat", "carrot"), colors):
        sprite = QImage(CELL, CELL, QImage.Format_ARGB32_Premultiplied)
        sprite.fill(color)
        renderer.crop_frames[crop, 0] = sprite
    monkeypatch.setattr(renderer.light, "actor", lambda sprite, *args: sprite)
    image = renderer.render(scene_widget.farm, "fields", scene_widget.qa_moment, selected=-1)
    assert image.pixelColor(225, 160) == colors[expected]
    emitted = []
    scene_widget.plot_selected.connect(emitted.append)
    logical_click(scene_widget, 225, 160)
    assert emitted == [expected]
    assert scene_widget.drag_origin is None


@pytest.mark.parametrize("identifier,point", [(0, (130, 150)), (1, (330, 200))])
def test_non_overlapping_click_preserves_normal_selection(scene_widget, monkeypatch, identifier, point):
    monkeypatch.setattr(scene_module, "POSITIONS", ((130, 170), (330, 220)))
    emitted = []
    scene_widget.plot_selected.connect(emitted.append)
    logical_click(scene_widget, *point)
    assert emitted == [identifier]


@pytest.mark.parametrize("ratio", [1, 1.25, 1.5, 2])
@pytest.mark.parametrize("size", [(700, 420), (1184, 576)])
def test_topmost_selection_uses_scene_rectangle_at_each_pixel_ratio(
    app, scene_widget, monkeypatch, ratio, size
):
    monkeypatch.setattr(scene_module, "POSITIONS", ((220, 180), (230, 210)))
    # Exercise the same integer physical-pixel geometry used on fractional-DPI displays.
    monkeypatch.setattr(scene_widget, "devicePixelRatioF", lambda: ratio)
    scene_widget.resize(*size)
    scene_widget.repaint()
    app.processEvents()
    emitted = []
    scene_widget.plot_selected.connect(emitted.append)
    logical_click(scene_widget, 225, 160)
    assert emitted == [1]
    logical_click(scene_widget, 190, 120)
    assert emitted == [1, 0]


def test_empty_space_keeps_window_dragging_available(scene_widget):
    emitted = []
    scene_widget.plot_selected.connect(emitted.append)
    logical_click(scene_widget, 250, 30)
    assert emitted == []
