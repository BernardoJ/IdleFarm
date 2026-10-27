"""IdleFarm desktop entry point. QA switches always require an isolated save path."""

import argparse
import json
import os
from pathlib import Path
import sys


def write_smoke_report(path, report):
    """Failure reports may target a directory that startup never got to create."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"Não foi possível escrever o relatório de teste: {exc}", file=sys.stderr)
        return False
    return True


def load_startup_farm(store, *, interactive=True):
    from PySide6.QtWidgets import QApplication, QDialog
    from game.engine import Farm
    from game.storage import RecoveryRequired
    from ui.recovery import RecoveryDialog

    while True:
        try:
            # Diagnose first: cancelling recovery must not initialize or save a
            # new model. Farm rechecks the files when it actually loads them.
            store.load()
            return Farm(store)
        except RecoveryRequired as recovery:
            if not interactive:
                raise
            app = QApplication.instance()
            quit_on_close = app.quitOnLastWindowClosed()
            app.setQuitOnLastWindowClosed(False)
            try:
                result = RecoveryDialog(store, recovery).exec()
            finally:
                app.setQuitOnLastWindowClosed(quit_on_close)
            if result != QDialog.Accepted:
                return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="IdleFarm · um canto para cultivar")
    parser.add_argument("--save", type=Path, help="Arquivo de save alternativo (testes/perfis)")
    parser.add_argument("--smoke", type=Path, help="Testar inicialização e escrever relatório JSON")
    args = parser.parse_args(argv)
    if args.smoke and not args.save:
        parser.error("--smoke exige --save para proteger o progresso real")
    from PySide6.QtCore import QLockFile, QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    from config.data import ROOT, SCENES
    from config.version import VERSION
    from visual.scene import WIDTH, HEIGHT
    from game.storage import RecoveryRequired, SaveStore
    from game.diagnostics import attach_log, detach_log
    from ui.window import FarmWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("IdleFarm")
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("IdleFarm")
    store = SaveStore(args.save)
    lock = None
    diagnostics = None
    try:
        store.path.parent.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(store.path) + ".lock")
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            raise RuntimeError("Este perfil do IdleFarm já está aberto em outra janela.")
        diagnostics = attach_log(store.path)
        farm = load_startup_farm(store, interactive=not bool(args.smoke))
        if farm is None:
            return 0
        window = FarmWindow(farm)
        window.show()
        if args.smoke:

            def finish():
                try:
                    startup_scene = window.scene.scene
                    for scene in SCENES:
                        window.area_actions[scene].trigger()
                        if window.scene.scene != scene or not window.area_actions[scene].isChecked():
                            raise RuntimeError("Navegação inválida: " + scene)
                        for phase in (0, 9, 16, 29):
                            image = window.renderer.render(farm, scene, phase=phase)
                            if image.isNull() or (image.width(), image.height()) != (WIDTH, HEIGHT):
                                raise RuntimeError("Cena inválida: " + scene)
                    for key in window.renderer.manifest["species"]:
                        for frame in range(6):
                            if window.renderer.icon(key, frame).isNull():
                                raise RuntimeError("Sprite inválido: " + key)
                    farm.save()
                    from tools.smoke_scenarios import check_features

                    feature_checks = check_features()
                    report = {
                        "ok": True,
                        "version": VERSION,
                        "build_commit": (
                            json.loads((ROOT / "config/build-info.json").read_text(encoding="utf-8"))[
                                "commit"
                            ]
                            if (ROOT / "config/build-info.json").exists()
                            else None
                        ),
                        "feature_checks": feature_checks,
                        "save_status": farm.persistence.status.value,
                        "startup_scene": startup_scene,
                        "logical_resolution": [WIDTH, HEIGHT],
                        "animal_frames": 72,
                        "interiors": [
                            key
                            for key, value in window.renderer.manifest["scenes"].items()
                            if value["interior"]
                        ],
                        "scenes": list(SCENES),
                        "coins": farm.state["coins"],
                        "assets_root": str(ROOT),
                        "packaged": bool(getattr(sys, "frozen", False)),
                        "save": str(store.path),
                        "platform": sys.platform,
                        "pid": os.getpid(),
                    }
                    if not write_smoke_report(args.smoke, report):
                        app.exit(1)
                        return
                    window.close()
                    app.quit()
                except Exception as exc:
                    # Smoke errors are reported as failed checks, never hidden
                    # or treated as a successful build.
                    write_smoke_report(args.smoke, {"ok": False, "error": str(exc)})
                    app.exit(1)

            QTimer.singleShot(400, finish)
        return app.exec()
    except RecoveryRequired as exc:
        # Interactive startup handles this in load_startup_farm. Automation must
        # fail without a modal dialog and leave the profile bytes untouched.
        if args.smoke:
            write_smoke_report(
                args.smoke,
                {
                    "ok": False,
                    "recovery_required": True,
                    "backup_available": exc.backup_data is not None,
                    "error": str(exc),
                },
            )
        return 1
    except (OSError, ValueError, RuntimeError) as exc:
        if args.smoke:
            write_smoke_report(args.smoke, {"ok": False, "error": str(exc)})
        else:
            QMessageBox.critical(None, "IdleFarm · não foi possível iniciar", str(exc))
        return 1
    finally:
        detach_log(diagnostics)
        if lock is not None and lock.isLocked():
            lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
