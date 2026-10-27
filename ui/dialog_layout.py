"""Keep wrapped player-facing text readable at the dialog's minimum width."""

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QDialog, QLayout


class ReadableDialog(QDialog):
    def __init__(self, parent=None, *, minimum_width):
        super().__init__(parent)
        self._protecting_layout = False
        self._wrapped_labels = ()
        self._readable_minimum_width = minimum_width
        self.setMinimumWidth(minimum_width)

    def protect_wrapped_labels(self, layout, *labels):
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        margins = layout.contentsMargins()
        # A vertical layout's strut preserves the requested cross-axis minimum
        # without consuming height, including differing native Qt margins.
        layout.addStrut(max(0, self._readable_minimum_width - margins.left() - margins.right()))
        self._wrapped_labels = labels
        self._protect_wrapped_labels()

    def _protect_wrapped_labels(self):
        if getattr(self, "_protecting_layout", False) or self.layout() is None:
            return
        self._protecting_layout = True
        try:
            self.layout().activate()
            changed = False
            for item in getattr(self, "_wrapped_labels", ()):
                if item.isHidden():
                    continue
                required = item.heightForWidth(max(1, item.width())) if item.text() else 0
                if required >= 0 and item.minimumHeight() != required:
                    item.setMinimumHeight(required)
                    changed = True
            if changed:
                self.layout().activate()
        finally:
            self._protecting_layout = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._protect_wrapped_labels()

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.LayoutRequest:
            self._protect_wrapped_labels()
        return result
