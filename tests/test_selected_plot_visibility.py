"""Selected plot IDs stay visible and clickable within five fixed visual slots."""

from copy import deepcopy
from datetime import datetime

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest

from config.data import CROPS
from visual.scene import HEIGHT, POSITIONS, WIDTH, Renderer, SceneWidget, field_layout


@pytest.fixture
def large_farm(farm, clock):
    farm.state["plots"] = [
        {"crop": tuple(CROPS)[index % len(CROPS)], "planted_at": clock()} for index in range(12)
    ]
    farm.state["unlocked"] = list(CROPS)
    return farm


def test_selection_beyond_first_five_keeps_species_and_other_slot_positions(large_farm):
    before = dict(field_layout(large_farm))
    assert 10 not in before
    after = dict(field_layout(large_farm, 10))
    assert len(after) == 5 and 10 in after
    assert after[10] == before[0]
    assert all(after[index] == position for index, position in before.items() if index != 0)
    assert {large_farm.state["plots"][index]["crop"] for index in after} == set(CROPS)


def test_redundant_species_replacement_retains_original_diverse_representatives(large_farm):
    # Four distinct crops plus a second wheat, then an off-screen pumpkin.
    crops = ("wheat", "carrot", "corn", "strawberry", "wheat", "pumpkin")
    large_farm.state["plots"] = [{"crop": crop, "planted_at": large_farm.now} for crop in crops]
    # Temporarily lock the baseline to a representative set with one redundant crop.
    original = large_farm.representatives
    large_farm.representatives = lambda scene: [0, 1, 2, 3, 4] if scene == "fields" else original(scene)
    before = dict(field_layout(large_farm))
    after = dict(field_layout(large_farm, 5))
    assert set(after) == {0, 1, 2, 3, 5}
    assert after[5] == before[4]
    assert all(after[index] == before[index] for index in range(4))


def test_empty_selected_plot_is_highlighted_without_inventing_a_crop(app, large_farm):
    large_farm.state["plots"][9] = None
    renderer = Renderer()
    before = deepcopy(large_farm.state)
    slots = dict(field_layout(large_farm, 9))
    assert len(slots) == 5 and 9 in slots
    x, y = slots[9]
    selected = renderer.render(large_farm, "fields", datetime(2026, 1, 1, 12), selected=9)
    assert selected.pixelColor(x - 37, y + 5) == QColor("#ffdf91")
    assert selected.pixelColor(x - 37, y - 30) == QColor("#ffdf91")
    assert large_farm.state == before


def test_new_empty_farm_shows_only_selected_soil_markers(app, farm):
    renderer = Renderer()
    unselected = renderer.render(farm, "fields", datetime(2026, 1, 1, 12), selected=-1)
    selected = renderer.render(farm, "fields", datetime(2026, 1, 1, 12), selected=1)
    assert field_layout(farm, 1) == [(1, POSITIONS[0])]
    # Empty selections add small corner marks, never any crop pixels.
    changed = sum(unselected.pixel(x, y) != selected.pixel(x, y) for y in range(HEIGHT) for x in range(WIDTH))
    assert 0 < changed < 100
    assert farm.representatives("fields") == []


@pytest.mark.parametrize("selected", [None, -1, 12, True, "10"])
def test_invalid_or_absent_selection_preserves_baseline(large_farm, selected):
    assert field_layout(large_farm, selected) == field_layout(large_farm)


def test_selection_after_expansion_and_repeated_changes_keeps_five_slots(large_farm):
    large_farm.state["plots"].append(None)
    for selected in (12, 11, 8, 6, 12, 2):
        layout = field_layout(large_farm, selected)
        assert len(layout) <= 5
        assert selected in dict(layout)
        assert len({position for _, position in layout}) == len(layout)
        assert all(position in POSITIONS for _, position in layout)


def test_selection_follows_the_same_plot_through_batch_state_changes(large_farm, clock):
    selected = 9
    assert selected in dict(field_layout(large_farm, selected))
    # A completed harvest batch leaves empty owned plots; replant fills those same IDs.
    large_farm.state["plots"] = [None] * len(large_farm.state["plots"])
    assert field_layout(large_farm, selected) == [(selected, POSITIONS[0])]
    large_farm.state["plots"] = [{"crop": "wheat", "planted_at": clock()} for _ in large_farm.state["plots"]]
    assert selected in dict(field_layout(large_farm, selected))
    assert len(field_layout(large_farm, selected)) == 5


@pytest.mark.parametrize("empty", [False, True])
def test_selected_offscreen_plot_is_the_drawn_highlight_and_click_target(app, large_farm, empty):
    selected = 10
    if empty:
        large_farm.state["plots"][selected] = None
    renderer = Renderer()
    widget = SceneWidget(large_farm, renderer)
    widget.selected = selected
    widget.qa_moment = datetime(2026, 1, 1, 12)
    widget.qa_phase = 0
    widget.resize(700, 420)
    try:
        widget.show()
        app.processEvents()
        x, y = dict(field_layout(large_farm, selected))[selected]
        image = renderer.render(large_farm, "fields", widget.qa_moment, selected=selected)
        assert image.pixelColor(x - 37, y + 5) == QColor("#ffdf91")
        point = QPoint(
            round(widget.target.x() + x * widget.target.width() / WIDTH),
            round(widget.target.y() + (y - 15) * widget.target.height() / HEIGHT),
        )
        emitted = []
        widget.plot_selected.connect(emitted.append)
        QTest.mouseClick(widget, Qt.LeftButton, pos=point)
        assert emitted == [selected]
    finally:
        widget.timer.stop()
        widget.close()
        app.processEvents()


def test_layout_and_selected_render_leave_economy_and_save_untouched(app, large_farm):
    large_farm.save()
    before = deepcopy(large_farm.state)
    saved = large_farm.store.path.read_bytes()
    renderer = Renderer()
    for selected in (11, 7, 2):
        field_layout(large_farm, selected)
        renderer.render(large_farm, "fields", datetime(2026, 1, 1, 23), selected=selected)
    assert large_farm.state == before
    assert large_farm.store.path.read_bytes() == saved
