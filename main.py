"""IdleFarm desktop entry point. QA switches always require an isolated save path."""

import argparse
import json
import os
from pathlib import Path
import sys


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
    from game.engine import Farm
    from game.storage import SaveStore
    from ui.window import FarmWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("IdleFarm")
    app.setApplicationVersion(VERSION)
    app.setOrganizationName("IdleFarm")
    store = SaveStore(args.save)
    try:
        store.path.parent.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(store.path) + ".lock")
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            raise RuntimeError("Este perfil do IdleFarm já está aberto em outra janela.")
        farm = Farm(store)
        window = FarmWindow(farm)
        window.show()
    except (OSError, ValueError, RuntimeError) as exc:
        if args.smoke:
            args.smoke.write_text(json.dumps({"ok": False, "error": str(exc)}), encoding="utf-8")
        else:
            QMessageBox.critical(None, "IdleFarm · não foi possível iniciar", str(exc))
        return 1
    if args.smoke:

        def finish():
            try:
                startup_scene = window.scene.scene
                for scene in SCENES:
                    window.navigate(scene)
                    for phase in (0, 9, 16, 29):
                        image = window.renderer.render(farm, scene, phase=phase)
                        if image.isNull() or (image.width(), image.height()) != (WIDTH, HEIGHT):
                            raise RuntimeError("Cena inválida: " + scene)
                for key in window.renderer.manifest["species"]:
                    for frame in range(6):
                        if window.renderer.icon(key, frame).isNull():
                            raise RuntimeError("Sprite inválido: " + key)
                farm.save()
                report = {
                    "ok": True,
                    "version": VERSION,
                    "startup_scene": startup_scene,
                    "logical_resolution": [WIDTH, HEIGHT],
                    "animal_frames": 72,
                    "interiors": [
                        key for key, value in window.renderer.manifest["scenes"].items() if value["interior"]
                    ],
                    "scenes": list(SCENES),
                    "coins": farm.state["coins"],
                    "assets_root": str(ROOT),
                    "packaged": bool(getattr(sys, "frozen", False)),
                    "save": str(store.path),
                    "platform": sys.platform,
                    "pid": os.getpid(),
                }
                args.smoke.parent.mkdir(parents=True, exist_ok=True)
                args.smoke.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                window.close()
                app.quit()
            except Exception as exc:
                args.smoke.write_text(json.dumps({"ok": False, "error": str(exc)}), encoding="utf-8")
                app.exit(1)

        QTimer.singleShot(400, finish)
    result = app.exec()
    lock.unlock()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
