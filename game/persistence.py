"""Observable save generations; delayed completions cannot acknowledge newer data."""

from enum import Enum
import logging
from weakref import WeakMethod


class SaveStatus(str, Enum):
    SAVED = "saved"
    SAVING = "saving"
    PENDING = "pending"
    ERROR = "error"


class SaveProgress:
    def __init__(self):
        self.generation = 0
        self.saved_generation = -1
        self.saving = False
        self.last_error = None
        self._listeners = []

    @property
    def dirty(self):
        return self.generation > self.saved_generation

    @property
    def status(self):
        if self.saving:
            return SaveStatus.SAVING
        if self.last_error is not None:
            return SaveStatus.ERROR
        return SaveStatus.PENDING if self.dirty else SaveStatus.SAVED

    def subscribe(self, callback):
        self._listeners.append(WeakMethod(callback))

    def _notify(self):
        self._listeners = [reference for reference in self._listeners if reference() is not None]
        for reference in self._listeners:
            reference()()

    def changed(self):
        self.generation += 1
        self._notify()

    def begin(self):
        self.saving = True
        self._notify()
        return self.generation

    def complete(self, generation):
        self.saved_generation = max(self.saved_generation, generation)
        self.last_error = None
        self.saving = False
        self._notify()

    def fail(self, error):
        self.last_error = str(error)
        self.saving = False
        logging.getLogger(__name__).warning("Falha de gravação; alterações ainda não salvas: %s", error)
        self._notify()
