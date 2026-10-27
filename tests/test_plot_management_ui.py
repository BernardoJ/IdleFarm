"""Large-farm workflows keep real plot IDs, confirmation and unsaved changes."""

from copy import deepcopy
import json

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from config.data import CROPS
from game.persistence import SaveStatus
from ui.window import FarmWindow
from visual.scene import field_layout


def big_farm(farm, clock):
    farm.state.update(coins=1000, plots=[None] * 8, unlocked=list(CROPS))
    farm.state["tutorial"] = {"done": True, "plot": None}
    farm.save()
    farm.plant_batch("wheat", [0, 2])
    clock.skip(3600)
    farm.plant(1, "carrot")
    return farm


def show(window, app):
    window.show()
    if not window.pages.isVisible():
        window.toggle_manage()
    app.processEvents()


def dialog_result(monkeypatch, result, selection):
    class Proposal:
        def __init__(self, *args, **kwargs):
            self.selection = selection

        def exec(self):
            return result

        def deleteLater(self):
            pass

    monkeypatch.setattr("ui.plot_tools.ReplantDialog", Proposal)


def test_filter_keeps_real_selected_plot_and_harvest_does_not_use_combo_row(app, farm, clock):
    big_farm(farm, clock)
    window = FarmWindow(farm)
    try:
        show(window, app)
        window.select_plot(7)
        QTest.mouseClick(window.ready_filter, Qt.LeftButton)
        assert [window.plots.itemData(i) for i in range(window.plots.count())] == [0, 2, 7]
        assert window.plots.currentData() == 7 and window.scene.selected == 7
        assert "fora do filtro" in window.plots.currentText()
        assert "Prontas (2)" == window.ready_filter.text()
        window.plots.setCurrentIndex(window.plots.findData(2))
        assert window.plots.currentIndex() == 1 and window.selected_plot == 2
        before = farm.state["coins"]
        QTest.mouseClick(window.harvest, Qt.LeftButton)
        assert farm.state["plots"][2] is None
        assert farm.state["plots"][1]["crop"] == "carrot"
        assert farm.state["plots"][0]["crop"] == "wheat"
        assert farm.state["coins"] == before + 20
        assert window.plots.currentData() == 2 and "fora do filtro" in window.plots.currentText()
        assert 2 in [key for key, _ in field_layout(farm, window.scene.selected)]
        QTest.mouseClick(window.ready_filter, Qt.LeftButton)
        assert window.plots.count() == 8 and window.plots.currentData() == 2
    finally:
        window.close()
        app.processEvents()


def test_next_free_follows_plot_order_even_with_filter_and_reports_full_farm(app, farm, clock):
    big_farm(farm, clock)
    window = FarmWindow(farm)
    try:
        show(window, app)
        window.ready_filter.setChecked(True)
        QTest.mouseClick(window.next_free, Qt.LeftButton)
        assert window.selected_plot == 3 and window.plots.currentData() == 3
        QTest.mouseClick(window.next_free, Qt.LeftButton)
        assert window.selected_plot == 4 and window.scene.selected == 4
        farm.plant_batch("wheat", farm.free_plots())
        window.refresh()
        window.go_next_free()
        assert window.selected_plot == 4 and "ocupados" in window.notice.text()
    finally:
        window.close()
        app.processEvents()


def test_harvest_menu_collects_only_ready_once_and_persists_summary(app, farm, clock):
    big_farm(farm, clock)
    window = FarmWindow(farm)
    try:
        before = farm.state["coins"]
        window.harvest_ready_action.trigger()
        assert farm.state["coins"] == before + 40
        assert farm.state["plots"][0] is None and farm.state["plots"][2] is None
        assert farm.state["plots"][1]["crop"] == "carrot"
        assert "2 colheita(s)" in window.notice.text()
        assert json.loads(farm.store.path.read_text()) == farm.state
        window.do_harvest_ready()
        assert farm.state["coins"] == before + 40
    finally:
        window.close()
        app.processEvents()


def test_cancelling_replant_leaves_money_plots_and_disk_unchanged(app, farm, clock, monkeypatch):
    big_farm(farm, clock)
    window = FarmWindow(farm)
    try:
        before, disk = deepcopy(farm.state), farm.store.path.read_bytes()
        dialog_result(monkeypatch, QDialog.Rejected, None)
        window.do_replant_batch()
        assert farm.state == before and farm.store.path.read_bytes() == disk
    finally:
        window.close()
        app.processEvents()


def test_confirmed_replant_preserves_selected_plot_and_disk(app, farm, clock, monkeypatch):
    big_farm(farm, clock)
    window = FarmWindow(farm)
    try:
        window.select_plot(7)
        before = farm.state["coins"]
        dialog_result(monkeypatch, QDialog.Accepted, ("carrot", (3, 5, 7)))
        window.do_replant_batch()
        assert farm.state["coins"] == before - 30
        assert all(farm.state["plots"][i]["crop"] == "carrot" for i in (3, 5, 7))
        assert window.selected_plot == 7 and window.plots.currentData() == 7
        assert 7 in [key for key, _ in field_layout(farm, 7)]
        assert "3 terreno(s)" in window.notice.text()
        assert json.loads(farm.store.path.read_text()) == farm.state
    finally:
        window.close()
        app.processEvents()


def test_failed_batch_write_stays_pending_and_retry_never_replants(app, farm, clock, monkeypatch):
    big_farm(farm, clock)
    window = FarmWindow(farm)
    original = farm.store.save
    disk = farm.store.path.read_bytes()

    def fail(snapshot):
        raise OSError("full")

    try:
        before = farm.state["coins"]
        dialog_result(monkeypatch, QDialog.Accepted, ("wheat", (3, 4, 5)))
        monkeypatch.setattr(farm.store, "save", fail)
        window.do_replant_batch()
        assert farm.state["coins"] == before - 15
        assert farm.store.path.read_bytes() == disk
        assert all(farm.state["plots"][i]["crop"] == "wheat" for i in (3, 4, 5))
        assert farm.persistence.status == SaveStatus.ERROR
        assert "Erro ao salvar" in window.save_info.text()
        assert "não salvas" in window.notice.text()
        monkeypatch.setattr(farm.store, "save", original)
        assert window.save_now()
        assert farm.state["coins"] == before - 15
        assert json.loads(farm.store.path.read_text()) == farm.state
    finally:
        monkeypatch.setattr(farm.store, "save", original)
        window.close()
        app.processEvents()


def test_tutorial_controls_show_actual_first_duration_then_normal_cycle(app, farm, clock):
    window = FarmWindow(farm)
    try:
        show(window, app)
        assert "1 minuto" in window.tutorial_info.text()
        QTest.mouseClick(window.plant, Qt.LeftButton)
        assert farm.tutorial_phase == "growing" and "01m 00s" in window.crop_info.text()
        clock.skip(60)
        window.tick()
        assert window.harvest.isEnabled() and "pronto!" in window.tutorial_info.text()
        QTest.mouseClick(window.harvest, Qt.LeftButton)
        assert farm.tutorial_phase == "completed" and not window.tutorial_info.isVisible()
        assert "Tutorial concluído" in window.notice.text()
        QTest.mouseClick(window.plant, Qt.LeftButton)
        assert farm.remaining(0) == 3600
    finally:
        window.close()
        app.processEvents()


def test_first_resume_tick_saves_watermark_even_without_animal_income(app, farm, clock, monkeypatch):
    window = FarmWindow(farm)
    original = farm.store.save
    snapshots = []

    def record(snapshot):
        snapshots.append(snapshot)
        original(snapshot)

    monkeypatch.setattr(farm.store, "save", record)
    try:
        clock.skip(8 * 3600)
        window.tick()
        assert len(snapshots) == 1 and farm.last_capped
        assert json.loads(farm.store.path.read_text())["last_accounted"] == clock()
        window.tick()
        assert len(snapshots) == 1
    finally:
        window.close()
        app.processEvents()
