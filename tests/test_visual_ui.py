from datetime import datetime
from pathlib import Path
import json
import os
import subprocess
import sys
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from config.data import ANIMALS, CROPS, SCENES
from tools.simulation import full_playthrough
from ui.window import FarmWindow
from visual.scene import Renderer, lighting


def test_representation_is_diverse_and_never_controls_production(farm, clock):
    full_playthrough(farm, clock)
    for scene in SCENES:
        reps = farm.representatives(scene)
        assert len(reps) <= 5
        if scene == "fields":
            assert {farm.state["plots"][i]["crop"] for i in reps} == set(CROPS)
        else:
            assert set(reps) == {key for key, a in ANIMALS.items() if a["building"] == scene}
    assert len(farm.representatives("coop")) == 5
    assert farm.count("chicken") == 9
    assert farm.hourly("coop") == 9 * 30 + 40 + 55


def test_empty_scenes_do_not_invent_owned_animals_or_crops(farm):
    assert all(farm.representatives(scene) == [] for scene in SCENES)


@pytest.mark.parametrize("hour", [0, 5, 6, 8, 12, 17, 18, 20, 23])
def test_local_light_is_bounded_and_continuous(hour):
    a = lighting(hour)
    b = lighting(hour + 0.00001)
    assert max(abs(x - y) for x, y in zip(a.getRgb(), b.getRgb())) <= 1


def test_all_scenes_all_light_states_render_original_assets(app, farm, clock):
    full_playthrough(farm, clock)
    renderer = Renderer()
    checksums = set()
    for scene in SCENES:
        day = renderer.render(farm, scene, datetime(2026, 1, 1, 12), phase=1)
        night = renderer.render(farm, scene, datetime(2026, 1, 1, 23), phase=1)
        assert day.width() == 256 and day.height() == 144
        assert bytes(day.constBits()) != bytes(night.constBits())
        checksums.add(bytes(day.constBits()))
    assert len(checksums) == 6
    for species in ANIMALS:
        assert not renderer.icon(species).isNull()


def test_real_ui_actions_and_navigation(app, farm, clock):
    window = FarmWindow(farm)
    window.show()
    app.processEvents()
    assert window.plots.count() == 2 and window.plant.isEnabled()
    QTest.mouseClick(window.plant, Qt.LeftButton)
    assert farm.state["coins"] == 45 and farm.state["plots"][0]["crop"] == "wheat"
    assert not window.plant.isEnabled() and not window.harvest.isEnabled()
    clock.skip(3600)
    window.tick()
    assert window.harvest.isEnabled()
    QTest.mouseClick(window.harvest, Qt.LeftButton)
    assert farm.state["coins"] == 65
    for scene in SCENES:
        QTest.mouseClick(window.tabs[scene], Qt.LeftButton)
        assert window.scene.scene == scene
        assert window.pages.currentIndex() == SCENES.index(scene)
    # The rest of this test earns money through the same real engine, then buys through Qt.
    from tools.simulation import earn_to

    earn_to(farm, clock, 500)
    window.refresh()
    window.navigate("coop")
    QTest.mouseClick(window.build_buttons["coop"], Qt.LeftButton)
    assert "coop" in farm.state["buildings"]
    QTest.mouseClick(window.animal_rows["chicken"][1], Qt.LeftButton)
    assert farm.count("chicken") == 1
    window.close()
    app.processEvents()


def test_source_app_smoke_from_other_working_directory(tmp_path):
    root = Path(__file__).resolve().parents[1]
    report = tmp_path / "result.json"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "main.py"),
            "--save",
            str(tmp_path / "save.json"),
            "--smoke",
            str(report),
        ],
        cwd=tmp_path,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["ok"] and not data["packaged"] and data["scenes"] == list(SCENES)


def test_single_profile_lock_prevents_concurrent_accounting(app, tmp_path):
    from PySide6.QtCore import QLockFile

    root = Path(__file__).resolve().parents[1]
    save = tmp_path / "save.json"
    report = tmp_path / "locked.json"
    lock = QLockFile(str(save) + ".lock")
    assert lock.tryLock(0)
    try:
        run = subprocess.run(
            [sys.executable, str(root / "main.py"), "--save", str(save), "--smoke", str(report)],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=45,
        )
        assert run.returncode == 1
        assert not json.loads(report.read_text(encoding="utf-8"))["ok"]
        assert not save.exists()
    finally:
        lock.unlock()


def test_smoke_requires_isolated_profile(tmp_path):
    root = Path(__file__).resolve().parents[1]
    run = subprocess.run(
        [sys.executable, str(root / "main.py"), "--smoke", str(tmp_path / "report.json")],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert run.returncode == 2
    assert not (tmp_path / "report.json").exists()
