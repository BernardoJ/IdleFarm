# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
import json
import subprocess

root = Path(SPECPATH)
source_commit = os.environ.get('IDLEFARM_BUILD_COMMIT')
if not source_commit:
    try:
        source_commit = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        source_commit = 'unknown'
provenance = root / 'build' / 'build-info.json'
provenance.parent.mkdir(parents=True, exist_ok=True)
provenance.write_text(json.dumps({'commit': source_commit}), encoding='utf-8')
a = Analysis(
    [str(root / 'main.py')], pathex=[str(root)], binaries=[],
    # Ship only final runtime assets, keeping high-resolution authoring sources out.
    datas=[(str(path), 'assets') for path in (root / 'assets').iterdir()
           if path.is_file() and path.suffix in ('.png', '.ico', '.json')]
          + [(str(root / 'config' / 'catalog.json'), 'config'), (str(provenance), 'config')],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'pytest', 'PIL'],
    noarchive=False, optimize=1,
)
# Avoid unrelated compatibility/ICU DLLs from the Windows runner's PATH.
a.binaries = [entry for entry in a.binaries
              if not Path(entry[0]).name.lower().startswith(('api-ms-', 'ext-ms-'))
              and Path(entry[0]).name.lower() != 'ucrtbase.dll'
              and not (Path(entry[0]).name.lower().startswith('icu')
                       and Path(entry[1]).parent.name.lower() != 'pyside6')]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name='IdleFarm',
    icon=str(root / 'assets' / 'icon.ico'),
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=os.environ.get('IDLEFARM_CONSOLE') == '1',
    disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    version=str(root / 'tools' / 'windows-version.txt') if os.name == 'nt' else None,
)
