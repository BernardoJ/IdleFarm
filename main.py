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
    from game.engine import Farm
    from game.storage import SaveStore
    from ui.window import FarmWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("IdleFarm")
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
                for scene in SCENES:
                    window.navigate(scene)
                    image = window.renderer.render(farm, scene)
                    if image.isNull() or image.size().width() != 256:
                        raise RuntimeError("Cena inválida: " + scene)
                farm.save()
                report = {
                    "ok": True,
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
