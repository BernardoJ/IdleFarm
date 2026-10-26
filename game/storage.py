"""Atomic, recoverable storage. Never silently destroys an unreadable save."""

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import tempfile

from game.state import validate


def default_path():
    if os.getenv("IDLEFARM_SAVE_PATH"):
        return Path(os.environ["IDLEFARM_SAVE_PATH"]).expanduser()
    base = Path(os.getenv("APPDATA", os.getenv("XDG_DATA_HOME", str(Path.home() / ".local/share"))))
    return base / "IdleFarm" / "save.json"


class SaveStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else default_path()
        self.backup = self.path.with_suffix(self.path.suffix + ".bak")
        self.warning = ""

    def load(self):
        errors = []
        for path in (self.path, self.backup):
            if not path.exists():
                continue
            try:
                data = validate(json.loads(path.read_text(encoding="utf-8")))
                if path == self.backup:
                    self.warning = "Salvamento recuperado pela cópia de segurança."
                return data
            except (OSError, ValueError, TypeError, KeyError) as exc:
                errors.append(str(exc))
                # Keep the original bytes, including partial writes, for recovery.
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                path.replace(path.with_name(path.name + ".corrupt-" + stamp))
        if errors:
            self.warning = "Save ilegível preservado como .corrupt. Uma nova fazenda foi criada."
        return None

    def save(self, data):
        validate(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".idlefarm-", suffix=".tmp", dir=self.path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            if self.path.exists():
                backup_temp = temporary.with_suffix(".bak.tmp")
                try:
                    shutil.copyfile(self.path, backup_temp)
                    os.replace(backup_temp, self.backup)
                finally:
                    backup_temp.unlink(missing_ok=True)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
