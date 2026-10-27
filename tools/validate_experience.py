"""Capture real tutorial, management, persistence and recovery widgets in isolation."""
# ruff: noqa: E402 -- set repository path and headless Qt before importing the UI

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
    os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "idlefarm-qa-qt-cache"))

from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QToolButton

from config.version import VERSION
from game.engine import Farm
from game.persistence import SaveStatus
from game.state import fresh
from game.storage import RecoveryRequired, SaveStore
from tools.simulation import VirtualClock, full_playthrough
from tools.font_checks import check_readable_fonts
from ui.plot_tools import ReplantDialog
from ui.recovery import RecoveryDialog
from ui.window import FarmWindow
from visual.scene import field_layout, time_label


def capture(widget, output, name, app, clipped):
    if isinstance(widget, FarmWindow) and widget.scene.qa_moment is not None:
        moment = widget.scene.qa_moment
        widget.time_info.setText(time_label(moment.hour) + moment.strftime(" · %H:%M"))
    app.processEvents()
    widget.repaint()
    app.processEvents()
    if not widget.grab().save(str(output / name)):
        raise OSError(f"Não foi possível gravar a captura {name}")
    for button in widget.findChildren(QPushButton) + widget.findChildren(QToolButton):
        if (
            button.isVisible()
            and QFontMetrics(button.font()).horizontalAdvance(button.text()) > button.width() - 14
        ):
            clipped.append(
                {"capture": name, "text": button.text(), "width": button.width(), "kind": "button"}
            )
    for item in widget.findChildren(QLabel):
        if item.isVisible() and item.text() and item.wordWrap():
            required = item.heightForWidth(item.width())
            if required > item.height() + 2:
                clipped.append(
                    {
                        "capture": name,
                        "text": item.text(),
                        "required_height": required,
                        "height": item.height(),
                        "kind": "label",
                    }
                )
    return check_readable_fonts(widget)


def show_farm(farm, app):
    window = FarmWindow(farm)
    window.heartbeat.stop()
    window.scene.timer.stop()
    window.scene.qa_moment = datetime(2026, 1, 1, 12)
    window.scene.qa_phase = 1
    window.time_info.setText("DIA · 12:00")
    window.show()
    app.processEvents()
    if not window.pages.isVisible():
        window.toggle_manage()
    app.processEvents()
    return window


def capture_management(output, app, clipped, report, profiles):
    clock = VirtualClock()
    farm = Farm(SaveStore(profiles / "management" / "save.json"), clock)
    full_playthrough(farm, clock)
    farm.harvest_ready()
    farm.plant_batch("wheat", [0, 2])
    farm.plant_batch("carrot", [1, 3])
    clock.skip(3600)
    farm.advance()
    farm.save()
    window = show_farm(farm, app)
    writer = farm.store.save
    batch = None
    try:
        selected = len(farm.state["plots"]) - 1
        window.select_plot(selected)
        window.ready_filter.setChecked(True)
        window.refresh()
        visible = [identifier for identifier, _ in field_layout(farm, window.scene.selected)]
        filtered = [window.plots.itemData(row) for row in range(window.plots.count())]
        report["management"] = {
            "owned_plots": len(farm.state["plots"]),
            "ready_plot_ids": farm.ready_plots(),
            "growing_plot_ids": [index for index in (1, 3) if farm.remaining(index) > 0],
            "selected_plot_id": window.selected_plot,
            "scene_selected_plot_id": window.scene.selected,
            "filtered_plot_ids": filtered,
            "rendered_plot_ids": visible,
        }
        report["checks"].update(
            {
                "selected_empty_plot_outside_filter_retained": selected in filtered
                and farm.state["plots"][selected] is None,
                "selected_plot_visible": selected in visible
                and window.scene.selected == window.selected_plot,
                "representative_cap": len(visible) <= 5,
                "ready_and_growing_present": farm.ready_plots() == [0, 2]
                and farm.remaining(1) > 0
                and farm.remaining(3) > 0,
            }
        )
        report["font_checks"]["management-filter.png"] = capture(
            window, output, "management-filter.png", app, clipped
        )

        batch = ReplantDialog(farm, "carrot", parent=window)
        batch.show()
        app.processEvents()
        quote = farm.planting_quote(batch.crop.currentData(), batch.quantity.value())
        report["batch_proposal"] = {
            "crop": batch.crop.currentData(),
            "count": quote["count"],
            "cost": quote["cost"],
            "balance": quote["balance"],
            "free_plot_count": quote["available_count"],
        }
        report["checks"]["affordable_proposal_requires_confirmation"] = (
            batch.selection is None and batch.confirm.isEnabled() and 0 < quote["cost"] <= quote["balance"]
        )
        report["font_checks"]["batch-confirmation.png"] = capture(
            batch, output, "batch-confirmation.png", app, clipped
        )
        batch.close()
        batch = None

        def fail_write(snapshot):
            raise OSError("Falha de gravação simulada para validação visual.")

        farm.store.save = fail_write
        window.act(lambda: farm.plant(selected, "wheat"), "Semente plantada.")
        report["save_failure"] = {
            "status": farm.persistence.status.value,
            "dirty": farm.persistence.dirty,
            "indicator_text": window.save_info.text(),
            "retry_visible": window.retry_save.isVisible(),
            "applied_plant_plot_id": selected,
        }
        report["checks"]["save_failure_remains_explicit"] = (
            farm.persistence.status == SaveStatus.ERROR
            and farm.persistence.dirty
            and window.retry_save.isVisible()
            and farm.state["plots"][selected] is not None
        )
        report["font_checks"]["save-error.png"] = capture(window, output, "save-error.png", app, clipped)
    finally:
        # Never leave the simulated writer installed when closeEvent saves.
        farm.store.save = writer
        report["checks"]["save_retry_recovers"] = (
            window.save_now() and farm.persistence.status == SaveStatus.SAVED
        )
        if batch is not None:
            batch.close()
        window.close()
        app.processEvents()


def capture_tutorial(output, app, clipped, report, profiles):
    clock = VirtualClock()
    farm = Farm(SaveStore(profiles / "tutorial" / "save.json"), clock)
    farm.plant(0, "wheat")
    clock.skip(15)
    farm.advance()
    farm.save()
    window = show_farm(farm, app)
    try:
        report["tutorial"] = {
            "phase": farm.tutorial_phase,
            "plot_id": farm.tutorial_plot,
            "duration_seconds": farm.crop_duration(0),
            "remaining_seconds": farm.remaining(0),
            "displayed_text": window.tutorial_info.text(),
        }
        report["checks"]["one_minute_tutorial_visible"] = (
            farm.crop_duration(0) == 60
            and farm.tutorial_phase == "growing"
            and window.tutorial_info.isVisible()
        )
        report["font_checks"]["tutorial.png"] = capture(window, output, "tutorial.png", app, clipped)
    finally:
        window.close()
        app.processEvents()


def capture_recovery(output, app, clipped, report, profiles):
    clock = VirtualClock()
    profile = profiles / "recovery"
    profile.mkdir()
    store = SaveStore(profile / "save.json")
    store.path.write_bytes(b'{"coins":')
    store.backup.write_text(json.dumps(fresh(clock())), encoding="utf-8")
    primary, backup = store.path.read_bytes(), store.backup.read_bytes()
    try:
        store.load()
    except RecoveryRequired as recovery:
        dialog = RecoveryDialog(store, recovery, clock=clock)
    else:
        raise AssertionError("O perfil de validação deve exigir uma decisão de recuperação.")
    try:
        dialog.show()
        report["font_checks"]["recovery.png"] = capture(dialog, output, "recovery.png", app, clipped)
        dialog.toggle_details()
        report["font_checks"]["recovery-details.png"] = capture(
            dialog, output, "recovery-details.png", app, clipped
        )
        report["recovery"] = {
            "backup_available": dialog.restore_button.isEnabled(),
            "details_read_only": dialog.details.isReadOnly(),
            "primary_player_message": dialog.message.text(),
        }
    finally:
        dialog.close()
        app.processEvents()
    report["checks"]["recovery_does_not_replace_progress"] = (
        store.path.read_bytes() == primary
        and store.backup.read_bytes() == backup
        and not list(profile.glob("*.corrupt-*"))
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "qa-output/experience")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    quit_on_close = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)
    clipped = []
    report = {"version": VERSION, "checks": {}, "font_checks": {}}
    try:
        with tempfile.TemporaryDirectory(prefix="idlefarm-experience-qa-") as directory:
            profiles = Path(directory)
            capture_management(output, app, clipped, report, profiles)
            capture_tutorial(output, app, clipped, report, profiles)
            capture_recovery(output, app, clipped, report, profiles)
    finally:
        app.setQuitOnLastWindowClosed(quit_on_close)
    captures = [
        "management-filter.png",
        "batch-confirmation.png",
        "save-error.png",
        "tutorial.png",
        "recovery.png",
        "recovery-details.png",
    ]
    report.update(
        {
            "ok": not clipped
            and all(report["checks"].values())
            and all(check["ok"] for check in report["font_checks"].values()),
            "font_failures": [
                {"capture": name, **failure}
                for name, check in report["font_checks"].items()
                for failure in check["missing"]
            ],
            "clipped_controls": clipped,
            "captures": captures,
            "capture_count": len(captures),
            "device_pixel_ratio": app.primaryScreen().devicePixelRatio() if app.primaryScreen() else 1,
            "platform": sys.platform,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "profiles": "temporary and isolated; no real saves read or written",
        }
    )
    (output / "validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if os.getenv("GITHUB_ACTIONS") == "true":
        for control in clipped:
            print("::error title=IdleFarm experience layout::" + json.dumps(control, ensure_ascii=True))
        for failure in report["font_failures"]:
            print("::error title=IdleFarm fonts::" + json.dumps(failure, ensure_ascii=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
