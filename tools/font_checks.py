"""Verify actual Qt glyph support and painting before accepting UI evidence."""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QImage, QPainter, QRawFont
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QLabel,
    QPlainTextEdit,
    QSpinBox,
    QWidget,
)

REQUIRED = "AWaçãoÁÉÍÓÚÇÃÕàâêôü…×·"


class ReadableFontError(RuntimeError):
    def __init__(self, report):
        super().__init__("A interface não possui fontes legíveis; a validação visual foi reprovada.")
        self.report = report


def _raw_font(font):
    return QRawFont.fromFont(font)


def _render_glyph(font, text):
    image = QImage(64, 64, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setFont(font)
    painter.setPen(Qt.black)
    painter.drawText(QRect(0, 0, 64, 64), Qt.AlignCenter, text)
    painter.end()
    return bytes(image.constBits())


def _font_failures(font, characters):
    raw = _raw_font(font)
    family = font.family()
    if not raw.isValid():
        return [{"family": family, "reason": "invalid_raw_font"}]
    failures = []
    missing = "".join(char for char in sorted(characters) if not raw.supportsCharacter(ord(char)))
    if missing:
        failures.append({"family": family, "reason": "missing_characters", "characters": missing[:48]})
    first, second = _render_glyph(font, "A"), _render_glyph(font, "W")
    if not any(first) or not any(second):
        failures.append({"family": family, "reason": "blank_glyphs"})
    elif first == second:
        failures.append({"family": family, "reason": "identical_glyphs"})
    return failures


def check_readable_fonts(root, *, raise_on_error=False):
    """Check visible text, once per applied QFont key, without a global cache."""
    root.ensurePolished()
    groups = {}
    checked = 0
    for widget in (root, *root.findChildren(QWidget)):
        if not widget.isVisible():
            continue
        if isinstance(widget, (QLabel, QAbstractButton, QSpinBox)):
            text = widget.text()
        elif isinstance(widget, QComboBox):
            text = widget.currentText()
        elif isinstance(widget, QPlainTextEdit):
            text = widget.toPlainText()
        else:
            continue
        if not text.strip():
            continue
        widget.ensurePolished()
        font = QFont(widget.font())
        group = groups.setdefault(font.key(), [font, set(REQUIRED)])
        group[1].update(char for char in text if not char.isspace() and ord(char) <= 0x024F)
        checked += 1
    missing = [failure for font, chars in groups.values() for failure in _font_failures(font, chars)]
    report = {
        "ok": not missing,
        "platform": QApplication.platformName(),
        "font_count": len(groups),
        "checked_widgets": checked,
        "missing": missing,
    }
    if missing and raise_on_error:
        raise ReadableFontError(report)
    return report
