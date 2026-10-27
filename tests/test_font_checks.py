"""Font evidence must reject unavailable and universal-box glyph renderers."""

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QLabel

from tools import font_checks


class RawFont:
    def __init__(self, valid=True, missing=()):
        self.valid, self.missing = valid, set(missing)

    def isValid(self):
        return self.valid

    def supportsCharacter(self, codepoint):
        return chr(codepoint) not in self.missing


def fake_font():
    return SimpleNamespace(family=lambda: "QA font")


def test_missing_raw_font_is_a_failed_check(monkeypatch):
    monkeypatch.setattr(font_checks, "_raw_font", lambda font: RawFont(valid=False))
    failures = font_checks._font_failures(fake_font(), set("AWação"))
    assert failures == [{"family": "QA font", "reason": "invalid_raw_font"}]


def test_missing_portuguese_glyphs_cannot_pass_with_ascii_support(monkeypatch):
    monkeypatch.setattr(font_checks, "_raw_font", lambda font: RawFont(missing="ç"))
    monkeypatch.setattr(font_checks, "_render_glyph", lambda font, text: text.encode())
    failures = font_checks._font_failures(fake_font(), set("AWação…×·"))
    assert failures == [{"family": "QA font", "reason": "missing_characters", "characters": "ç"}]


def test_universal_box_renderer_fails_even_when_font_claims_glyph_support(monkeypatch):
    monkeypatch.setattr(font_checks, "_raw_font", lambda font: RawFont())
    monkeypatch.setattr(font_checks, "_render_glyph", lambda font, text: b"same nonblank box")
    assert font_checks._font_failures(fake_font(), set("AW")) == [
        {"family": "QA font", "reason": "identical_glyphs"}
    ]


def test_blank_glyph_rendering_cannot_be_accepted(monkeypatch):
    monkeypatch.setattr(font_checks, "_raw_font", lambda font: RawFont())
    monkeypatch.setattr(font_checks, "_render_glyph", lambda font, text: bytes(64 * 64 * 4))
    assert font_checks._font_failures(fake_font(), set("AW")) == [
        {"family": "QA font", "reason": "blank_glyphs"}
    ]


def test_readable_font_error_keeps_failed_report(app, monkeypatch):
    monkeypatch.setattr(font_checks, "_raw_font", lambda font: RawFont(valid=False))
    widget = QLabel("Ação e recuperação… × ·")
    widget.show()
    try:
        with pytest.raises(font_checks.ReadableFontError) as failure:
            font_checks.check_readable_fonts(widget, raise_on_error=True)
        assert not failure.value.report["ok"]
        assert failure.value.report["font_count"] == 1
        assert failure.value.report["missing"][0]["reason"] == "invalid_raw_font"
    finally:
        widget.close()


def test_platform_native_font_renderer_supports_actual_portuguese_widgets(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = """
import json
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget
from tools.font_checks import check_readable_fonts
app = QApplication([])
window = QWidget()
window.setStyleSheet('QWidget { font-family: "Segoe UI"; font-size: 12px; } QLabel#title { font-family: Georgia; font-size: 23px; font-weight: bold; }')
layout = QVBoxLayout(window)
title = QLabel('RECUPERAÇÃO')
title.setObjectName('title')
layout.addWidget(title)
layout.addWidget(QLabel('Ação · plantações · memória · café · … × ·'))
layout.addWidget(QPushButton('Próximo livre'))
combo = QComboBox()
combo.addItem('Cenoura · pronta!')
layout.addWidget(combo)
quantity = QSpinBox()
quantity.setSuffix(' terrenos')
layout.addWidget(quantity)
details = QPlainTextEdit('Diagnóstico e recuperação')
details.setReadOnly(True)
layout.addWidget(details)
layout.addWidget(QLabel(''))
image_only = QLabel()
image_only.setPixmap(QPixmap(8,8))
layout.addWidget(image_only)
window.show()
app.processEvents()
report = check_readable_fonts(window, raise_on_error=True)
assert report['ok'] and report['font_count'] >= 2 and report['checked_widgets'] == 6, report
print(json.dumps(report))
window.close()
"""
    env = os.environ.copy()
    expected = "windows" if sys.platform == "win32" else "offscreen"
    env["QT_QPA_PLATFORM"] = expected
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["platform"] == expected and report["missing"] == []
