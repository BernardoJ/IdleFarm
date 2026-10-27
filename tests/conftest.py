import os
import pytest
from game.engine import Farm
from game.storage import SaveStore

os.environ.setdefault("QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen")
if os.name != "nt":
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/idlefarm-qt-cache")


class Clock:
    def __init__(self, now=1_800_000_000.0):
        self.value = now

    def __call__(self):
        return self.value

    def skip(self, seconds):
        self.value += seconds


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def farm(tmp_path, clock):
    return Farm(SaveStore(tmp_path / "save.json"), clock)


@pytest.fixture(scope="session")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
