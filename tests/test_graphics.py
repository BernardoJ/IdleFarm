"""Regression checks for the new render pipeline, original saves and visual bounds."""

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import shutil

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest

from config.data import ANIMALS, CROPS, SCENES
from game.engine import Farm
from game.storage import SaveStore
from tools.simulation import full_playthrough
from ui.window import FarmWindow
from visual.animation import Pose, pose
from visual.scene import CELL, HEIGHT, POSITIONS, WIDTH, Renderer


@pytest.fixture
def renderer(app):
    return Renderer()


def test_real_v010_profile_loads_without_migration_or_lost_progress(tmp_path, clock):
    source = Path(__file__).parent / "fixtures/v0.1.0-save.json"
    original = json.loads(source.read_text(encoding="utf-8"))
    store = SaveStore(tmp_path / "save.json")
    shutil.copyfile(source, store.path)
    clock.value = original["last_accounted"]
    farm = Farm(store, clock)
    assert farm.state == original
    assert farm.state["version"] == 1
    assert len(farm.state["plots"]) == 12 and sum(a["count"] for a in farm.state["animals"]) == 20
    assert Farm(store, clock).state == original
    clock.skip(6 * 3600)
    reopened = Farm(store, clock)
    assert reopened.offline_reward > 0
    assert Farm(store, clock).offline_reward == 0
    assert all(reopened.remaining(i) == 0 for i in range(12))


def test_all_final_art_and_complete_distinct_animal_poses(renderer):
    assert len(renderer.light.plates) == 24
    assert renderer.manifest["species"] == list(ANIMALS)
    assert sum(s["interior"] for s in renderer.manifest["scenes"].values()) == 5
    for key in SCENES:
        assert renderer.backgrounds[key].size() == renderer.foregrounds[key].size()
        assert (renderer.backgrounds[key].width(), renderer.backgrounds[key].height()) == (WIDTH, HEIGHT)
    for key in ANIMALS:
        checksums = set()
        for frame in range(6):
            image = renderer.animal_frames[key, frame]
            assert (image.width(), image.height()) == (CELL, CELL)
            x, y, w, h = renderer.manifest["sprite_bounds"][key][frame]
            assert 0 < x < x + w < CELL and 0 < y < y + h < CELL
            assert not renderer.icon(key, frame).isNull()
            checksums.add(bytes(image.constBits()))
        assert len(checksums) == 6
    assert renderer.icon("cow").width() > renderer.icon("goat").width()
    assert renderer.icon("horse").height() > renderer.icon("sheep").height()
    for key in CROPS:
        assert len({bytes(renderer.crop_frames[key, stage].constBits()) for stage in range(4)}) == 4


def test_behaviour_cycles_hold_feet_and_stay_on_walkable_floor(renderer):
    for scene in SCENES[1:]:
        xmin, ymin, xmax, ymax = renderer.manifest["scenes"][scene]["walkable"]
        for key, animal in ANIMALS.items():
            if animal["building"] != scene:
                continue
            for index in range(5):
                states = [pose(scene, key, index, second / 2) for second in range(144)]
                assert {s.behaviour for s in states} >= {"idle", "walk", "feed", "rest"}
                assert all(xmin <= s.x <= xmax and ymin <= s.y <= ymax for s in states)
                idle = [pose(scene, key, 0, moment) for moment in (0, 1, 2)]
                assert len({(s.x, s.y) for s in idle}) == 1
                assert max(s.x for s in states) - min(s.x for s in states) == 10


def test_rendering_and_animation_cannot_change_economy_or_save(renderer, farm, clock):
    full_playthrough(farm, clock)
    original, saved = deepcopy(farm.state), farm.store.path.read_bytes()
    for scene in SCENES:
        assert len(farm.representatives(scene)) <= 5
        for phase in (0, 3, 10, 16, 22, 29, 35, 3600, 86400):
            image = renderer.render(farm, scene, datetime(2026, 1, 1, 23), phase)
            assert not image.isNull()
            if scene != "fields":
                entities = renderer.entities(farm, scene, phase)
                assert [p.y for _, p in entities] == sorted(p.y for _, p in entities)
                assert all(ANIMALS[key]["building"] == scene for key, _ in entities)
    assert farm.state == original and farm.store.path.read_bytes() == saved
    assert len(renderer.light.plates) == 24


def test_foreground_really_occludes_actor_pixels(renderer, farm, monkeypatch):
    moment = datetime(2026, 1, 1, 12)
    monkeypatch.setattr(renderer, "entities", lambda *args: [])
    empty = renderer.render(farm, "barn", moment)
    sprite = QImage(CELL, CELL, QImage.Format_ARGB32_Premultiplied)
    sprite.fill(QColor("#ff00ff"))
    renderer.animal_frames["cow", 0] = sprite
    monkeypatch.setattr(renderer, "entities", lambda *args: [("cow", Pose(120, 235, 0, "idle"))])
    occupied = renderer.render(farm, "barn", moment)
    assert occupied.pixelColor(120, 190) != empty.pixelColor(120, 190)
    assert renderer.foregrounds["barn"].pixelColor(120, 220).alpha() == 255
    assert occupied.pixelColor(120, 220) == empty.pixelColor(120, 220)


@pytest.mark.parametrize("scene", SCENES[1:])
def test_windows_dim_and_local_lanterns_remain_luminous(renderer, farm, scene):
    day = renderer.render(farm, scene, datetime(2026, 1, 1, 12))
    night = renderer.render(farm, scene, datetime(2026, 1, 1, 23))
    x, y, w, h = renderer.manifest["scenes"][scene]["windows"][0]
    assert (
        day.pixelColor(x + w // 2, y + h // 2).lightness()
        > night.pixelColor(x + w // 2, y + h // 2).lightness()
    )
    lx, ly = renderer.manifest["scenes"][scene]["lamps"][0]
    lamp = night.pixelColor(lx, ly)
    assert lamp.red() > 220 and lamp.red() > lamp.blue()
    assert lamp.lightness() > night.pixelColor(256, 180).lightness()


def test_plot_selection_uses_new_resolution_and_resized_scene(app, farm, clock):
    full_playthrough(farm, clock)
    window = FarmWindow(farm)
    try:
        window.show()
        window.resize(1040, 1000)
        app.processEvents()
        window.scene.repaint()
        target = window.scene.target
        for identifier, (x, y) in zip(farm.representatives("fields"), POSITIONS):
            point = QPoint(
                round(target.x() + x * target.width() / WIDTH),
                round(target.y() + (y - 15) * target.height() / HEIGHT),
            )
            QTest.mouseClick(window.scene, Qt.LeftButton, pos=point)
            assert window.plots.currentIndex() == identifier
        assert target.width() <= window.scene.width() and target.height() <= window.scene.height()
    finally:
        window.close()
        app.processEvents()
