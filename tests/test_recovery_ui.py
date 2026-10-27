"""Recovery decisions never create a replacement farm without player consent."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import QLockFile, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QMessageBox

from game.state import fresh
from game.storage import RecoveryRequired, SaveStore
from main import load_startup_farm, main
from ui.recovery import RecoveryDialog


def damaged_store(tmp_path, clock, *, backup_valid=False):
    store = SaveStore(tmp_path / "save.json")
    store.path.write_bytes(b"primary is damaged\n")
    backup = fresh(clock())
    backup["coins"] = 137
    store.backup.write_bytes(json.dumps(backup).encode() if backup_valid else b"backup is damaged\r\n")
    with pytest.raises(RecoveryRequired) as failure:
        store.load()
    return store, failure.value


def snapshot(directory):
    return {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()}


def show_dialog(app, store, recovery, clock):
    dialog = RecoveryDialog(store, recovery, clock=clock)
    dialog.show()
    app.processEvents()
    return dialog


@pytest.mark.parametrize("backup_valid", [False, True])
def test_recovery_screen_explains_preservation_and_offers_only_valid_backup(
    app, tmp_path, clock, backup_valid
):
    store, recovery = damaged_store(tmp_path, clock, backup_valid=backup_valid)
    before = snapshot(tmp_path)
    dialog = show_dialog(app, store, recovery, clock)
    try:
        assert "preservados" in dialog.message.text()
        assert str(store.path) not in dialog.message.text()
        assert dialog.restore_button.isEnabled() == backup_valid
        assert dialog.details.isHidden() and dialog.details.isReadOnly()
        QTest.mouseClick(dialog.details_button, Qt.LeftButton)
        assert dialog.details.isVisible()
        assert str(store.path.resolve()) in dialog.details.toPlainText()
        QTest.mouseClick(dialog.details_button, Qt.LeftButton)
        assert dialog.details.isHidden()
        assert snapshot(tmp_path) == before
    finally:
        dialog.close()


@pytest.mark.parametrize("close_action", ["cancel", "window-close"])
def test_cancel_or_close_does_not_change_files(app, tmp_path, clock, close_action):
    store, recovery = damaged_store(tmp_path, clock)
    before = snapshot(tmp_path)
    dialog = show_dialog(app, store, recovery, clock)
    if close_action == "cancel":
        QTest.mouseClick(dialog.cancel_button, Qt.LeftButton)
    else:
        dialog.close()
    assert dialog.result() == QDialog.Rejected
    assert snapshot(tmp_path) == before


def test_retry_failed_validation_and_then_manual_repair_without_writing(app, tmp_path, clock):
    store, recovery = damaged_store(tmp_path, clock)
    before = snapshot(tmp_path)
    dialog = show_dialog(app, store, recovery, clock)
    try:
        QTest.mouseClick(dialog.retry_button, Qt.LeftButton)
        assert dialog.isVisible() and dialog.status.isVisible()
        assert snapshot(tmp_path) == before
        repaired = fresh(clock())
        repaired["coins"] = 194
        raw = json.dumps(repaired, indent=2).encode()
        store.path.write_bytes(raw)  # External/manual repair of the file.
        QTest.mouseClick(dialog.retry_button, Qt.LeftButton)
        assert dialog.result() == QDialog.Accepted
        assert store.path.read_bytes() == raw
    finally:
        dialog.close()


def test_disappearing_files_during_retry_do_not_start_a_new_farm(app, tmp_path, clock):
    store, recovery = damaged_store(tmp_path, clock)
    dialog = show_dialog(app, store, recovery, clock)
    try:
        store.path.unlink()
        store.backup.unlink()
        QTest.mouseClick(dialog.retry_button, Qt.LeftButton)
        assert dialog.isVisible() and dialog.result() == QDialog.Rejected
        assert not store.path.exists() and not store.backup.exists()
        assert "Iniciar nova fazenda" in dialog.status.text()
    finally:
        dialog.close()


@pytest.mark.parametrize("operation", ["new", "restore"])
def test_replacement_requires_confirmation_with_no_as_default(app, tmp_path, clock, monkeypatch, operation):
    store, recovery = damaged_store(tmp_path, clock, backup_valid=True)
    before = snapshot(tmp_path)
    asked = []

    def question(parent, title, text, buttons, default):
        asked.append((buttons, default))
        return QMessageBox.No

    monkeypatch.setattr(QMessageBox, "question", question)
    dialog = show_dialog(app, store, recovery, clock)
    try:
        button = dialog.new_button if operation == "new" else dialog.restore_button
        QTest.mouseClick(button, Qt.LeftButton)
        assert asked == [(QMessageBox.Yes | QMessageBox.No, QMessageBox.No)]
        assert dialog.isVisible() and dialog.result() == QDialog.Rejected
        assert snapshot(tmp_path) == before
    finally:
        dialog.close()


def test_confirmed_restore_keeps_original_bytes_and_opens_backup_progress(app, tmp_path, clock, monkeypatch):
    store, recovery = damaged_store(tmp_path, clock, backup_valid=True)
    old_primary, old_backup = store.path.read_bytes(), store.backup.read_bytes()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    dialog = show_dialog(app, store, recovery, clock)
    QTest.mouseClick(dialog.restore_button, Qt.LeftButton)
    assert dialog.result() == QDialog.Accepted
    assert store.load()["coins"] == 137
    assert store.backup.read_bytes() == old_backup
    archives = {path.read_bytes() for path in tmp_path.glob("*.corrupt-*")}
    assert old_primary in archives and old_backup in archives


def test_confirmed_new_farm_preserves_all_previous_files(app, tmp_path, clock, monkeypatch):
    store, recovery = damaged_store(tmp_path, clock)
    originals = {store.path.read_bytes(), store.backup.read_bytes()}
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    dialog = show_dialog(app, store, recovery, clock)
    QTest.mouseClick(dialog.new_button, Qt.LeftButton)
    assert dialog.result() == QDialog.Accepted
    new = store.load()
    assert new["coins"] == 50 and new["plots"] == [None, None]
    assert {path.read_bytes() for path in tmp_path.glob("*.corrupt-*")} == originals


@pytest.mark.parametrize("operation", ["new", "restore"])
def test_failed_recovery_write_keeps_dialog_open_and_preserves_files(
    app, tmp_path, clock, monkeypatch, operation
):
    store, recovery = damaged_store(tmp_path, clock, backup_valid=True)
    before = snapshot(tmp_path)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(store, "start_new" if operation == "new" else "restore_backup", fail)
    dialog = show_dialog(app, store, recovery, clock)
    try:
        QTest.mouseClick(dialog.new_button if operation == "new" else dialog.restore_button, Qt.LeftButton)
        assert dialog.result() == QDialog.Rejected and dialog.isVisible()
        assert dialog.status.isVisible() and "preservados" in dialog.status.text()
        assert "disk full" not in dialog.status.text() and "disk full" in dialog.details.toPlainText()
        assert snapshot(tmp_path) == before
    finally:
        dialog.close()


def test_cancelled_startup_does_not_construct_or_save_farm(app, tmp_path, clock, monkeypatch):
    import game.engine

    store, _ = damaged_store(tmp_path, clock)
    before = snapshot(tmp_path)

    def unexpected_farm(*args):
        raise AssertionError("Recovery cancellation must not initialize a farm")

    monkeypatch.setattr(game.engine, "Farm", unexpected_farm)
    monkeypatch.setattr(RecoveryDialog, "exec", lambda self: QDialog.Rejected)
    quit_on_close = app.quitOnLastWindowClosed()
    assert load_startup_farm(store) is None
    assert app.quitOnLastWindowClosed() == quit_on_close
    assert snapshot(tmp_path) == before


def test_valid_primary_starts_without_opening_recovery(app, tmp_path, clock, monkeypatch):
    store = SaveStore(tmp_path / "save.json")
    progress = fresh(clock())
    progress["coins"] = 173
    store.save(progress)

    def unexpected_dialog(*args):
        raise AssertionError("Valid progress must not require recovery")

    monkeypatch.setattr(RecoveryDialog, "exec", unexpected_dialog)
    farm = load_startup_farm(store)
    assert farm.state["coins"] == 173
    assert farm.store is store


def test_main_cancel_releases_profile_lock_and_preserves_bytes(app, tmp_path, clock, monkeypatch):
    store, _ = damaged_store(tmp_path, clock)
    before = snapshot(tmp_path)
    monkeypatch.setattr(RecoveryDialog, "exec", lambda self: QDialog.Rejected)
    assert main(["--save", str(store.path)]) == 0
    after = snapshot(tmp_path)
    assert {name: after[name] for name in before} == before
    assert set(after) - set(before) <= {store.path.name + ".diagnostic.log"}
    lock = QLockFile(str(store.path) + ".lock")
    try:
        assert lock.tryLock(0)
    finally:
        lock.unlock()


def test_main_error_creates_nested_smoke_report_and_releases_lock(app, tmp_path, monkeypatch):
    import main as entry

    save = tmp_path / "profile" / "save.json"
    report = tmp_path / "nested" / "reports" / "error.json"

    def fail(*args, **kwargs):
        raise OSError("blocked")

    monkeypatch.setattr(entry, "load_startup_farm", fail)
    assert main(["--save", str(save), "--smoke", str(report)]) == 1
    assert json.loads(report.read_text())["ok"] is False
    assert not save.exists()
    lock = QLockFile(str(save) + ".lock")
    try:
        assert lock.tryLock(0)
    finally:
        lock.unlock()


@pytest.mark.parametrize("backup_valid", [False, True])
def test_smoke_rejects_damaged_profile_noninteractively_and_preserves_files(tmp_path, clock, backup_valid):
    root = Path(__file__).resolve().parents[1]
    store, _ = damaged_store(tmp_path, clock, backup_valid=backup_valid)
    originals = {store.path: store.path.read_bytes(), store.backup: store.backup.read_bytes()}
    report = tmp_path / "new-report-dir" / "recovery.json"
    result = subprocess.run(
        [sys.executable, str(root / "main.py"), "--save", str(store.path), "--smoke", str(report)],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1, result.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    assert not data["ok"] and data["recovery_required"]
    assert data["backup_available"] == backup_valid
    assert all(path.read_bytes() == raw for path, raw in originals.items())
    assert not list(tmp_path.glob("*.corrupt-*"))
    assert not Path(str(store.path) + ".lock").exists()


def test_first_installation_smoke_creates_new_profile_without_recovery(tmp_path):
    root = Path(__file__).resolve().parents[1]
    save = tmp_path / "brand-new-profile" / "save.json"
    report = tmp_path / "new-reports" / "startup.json"
    result = subprocess.run(
        [sys.executable, str(root / "main.py"), "--save", str(save), "--smoke", str(report)],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(report.read_text(encoding="utf-8"))["ok"]
    assert json.loads(save.read_text(encoding="utf-8"))["coins"] == 50
    assert not Path(str(save) + ".lock").exists()


def test_recovery_text_remains_uncut_on_small_logical_screen_at_double_dpi(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = """
import json
from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
from game.state import fresh
from game.storage import RecoveryRequired, SaveStore
from ui.recovery import RecoveryDialog

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
store = SaveStore(Path(sys.argv[1]) / 'save.json')
store.path.write_bytes(b'broken primary')
store.backup.write_text(json.dumps(fresh(1_800_000_000)), encoding='utf-8')
primary, backup = store.path.read_bytes(), store.backup.read_bytes()
try:
    store.load()
except RecoveryRequired as recovery:
    dialog = RecoveryDialog(store, recovery)
dialog.show()

def check_text():
    app.processEvents()
    for item in (dialog.title, dialog.message, dialog.backup_info, dialog.status):
        if not item.isHidden():
            required = item.heightForWidth(item.width())
            assert item.height() >= required, (item.text(), item.height(), required)
    assert dialog.details.isReadOnly()
    assert dialog.details.minimumHeight() < dialog.details.maximumHeight() == 150

check_text()
dialog.resize(520, 260)
check_text()
dialog.toggle_details()
check_text()
dialog.resize(520, 260)
check_text()
dialog.show_failure(OSError('simulated write failure'))
check_text()
dialog.toggle_details()
check_text()
dialog.toggle_details()
check_text()
dialog.close()
assert store.path.read_bytes() == primary and store.backup.read_bytes() == backup
"""
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_SCALE_FACTOR"] = "2"
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
