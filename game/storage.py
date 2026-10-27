"""Atomic saves and explicit, non-destructive recovery of existing progress."""

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile

from game.state import validate

LOGGER = logging.getLogger(__name__)


def default_path():
    if os.getenv("IDLEFARM_SAVE_PATH"):
        return Path(os.environ["IDLEFARM_SAVE_PATH"]).expanduser()
    base = Path(os.getenv("APPDATA", os.getenv("XDG_DATA_HOME", str(Path.home() / ".local/share"))))
    return base / "IdleFarm" / "save.json"


@dataclass(frozen=True)
class RecoveryIssue:
    path: Path
    reason: str


class RecoveryRequired(OSError):
    """Existing progress needs an explicit player decision before any replacement."""

    def __init__(self, primary, issues, existing_paths, backup_data=None):
        super().__init__("Não foi possível carregar o progresso. Os arquivos existentes foram preservados.")
        self.primary = primary
        self.issues = tuple(issues)
        self.existing_paths = tuple(existing_paths)
        self.backup_data = backup_data
        self.details = "\n".join(f"{issue.path}: {issue.reason}" for issue in self.issues)


class SaveStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else default_path()
        self.backup = self.path.with_suffix(self.path.suffix + ".bak")
        self.warning = ""
        self.recovery = None

    @staticmethod
    def _read(path):
        return validate(json.loads(path.read_text(encoding="utf-8")))

    def load(self):
        """Inspect files without moving, modifying or replacing any of them."""
        issues = []
        existing = []
        backup_data = None
        for path in (self.path, self.backup):
            if not path.exists():
                continue
            existing.append(path)
            try:
                data = self._read(path)
                if path == self.path:
                    self.recovery = None
                    return data
                backup_data = data
            except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
                issue = RecoveryIssue(path, str(exc))
                issues.append(issue)
                LOGGER.warning("Progresso rejeitado em %s: %s", path, exc)
        # Older versions moved bad saves away. Their presence still means this is
        # a recovery situation, even when neither usual filename remains.
        archives = sorted(self.path.parent.glob(self.path.name + ".corrupt-*"))
        archives += sorted(self.path.parent.glob(self.backup.name + ".corrupt-*"))
        existing.extend(archives)
        if not existing:
            self.recovery = None
            return None
        if not self.path.exists():
            issues.insert(0, RecoveryIssue(self.path, "Arquivo principal ausente; há progresso anterior."))
        self.recovery = RecoveryRequired(self.path, issues, existing, backup_data)
        raise self.recovery

    def _archive_existing(self):
        """Copy exact original bytes durably before an explicitly authorized reset."""
        archived = []
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        for path in (self.path, self.backup):
            if not path.exists():
                continue
            descriptor, name = tempfile.mkstemp(prefix=path.name + ".corrupt-" + stamp + "-", dir=path.parent)
            archive = Path(name)
            try:
                with os.fdopen(descriptor, "wb") as target, path.open("rb") as source:
                    shutil.copyfileobj(source, target)
                    target.flush()
                    os.fsync(target.fileno())
                archived.append(archive)
            except OSError:
                archive.unlink(missing_ok=True)
                raise
        return tuple(archived)

    def restore_backup(self):
        """Restore only after the recovery UI has obtained explicit confirmation."""
        try:
            self.load()
        except RecoveryRequired as recovery:
            if recovery.backup_data is None:
                raise ValueError("Não há uma cópia de segurança válida para restaurar.") from recovery
            data = validate(recovery.backup_data)
        else:
            raise ValueError("O progresso principal já pode ser aberto. Tente novamente.")
        self._archive_existing()
        self._write_atomic(data, rotate_backup=False)
        self.recovery = None
        self.warning = "Progresso restaurado da cópia de segurança. Arquivos anteriores preservados."
        return data

    def start_new(self, data):
        """Install a fresh state only after the player explicitly confirms a new farm."""
        data = validate(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._archive_existing()
        self._write_atomic(data, rotate_backup=False)
        self.recovery = None
        self.warning = "Nova fazenda criada. Os arquivos de progresso anteriores foram preservados."

    def save(self, data):
        data = validate(data)
        # Recheck the target before a replacement, including external corruption
        # that happened after startup. Failed diagnosis never writes a new farm.
        self.load()
        self._write_atomic(data, rotate_backup=True)

    def _write_atomic(self, data, *, rotate_backup):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".idlefarm-", suffix=".tmp", dir=self.path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            if rotate_backup and self.path.exists():
                backup_temp = temporary.with_suffix(".bak.tmp")
                try:
                    with self.path.open("rb") as source, backup_temp.open("wb") as target:
                        shutil.copyfileobj(source, target)
                        target.flush()
                        os.fsync(target.fileno())
                    os.replace(backup_temp, self.backup)
                finally:
                    backup_temp.unlink(missing_ok=True)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
