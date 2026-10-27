"""Review a batch planting proposal without charging or changing the farm."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from config.data import CROPS


def money(value):
    return f"{value:,}".replace(",", ".")


class ReplantDialog(QDialog):
    def __init__(self, farm, crop="wheat", parent=None):
        super().__init__(parent)
        self.farm = farm
        self.selection = None
        self._reviewed_quote = None
        self.setWindowTitle("Plantar terrenos livres")
        self.setMinimumWidth(420)
        box = QVBoxLayout(self)
        heading = QLabel("Escolha a cultura e confira a quantidade e o custo antes de confirmar.")
        heading.setWordWrap(True)
        box.addWidget(heading)
        row = QHBoxLayout()
        row.addWidget(QLabel("Cultura"))
        self.crop = QComboBox()
        self.crop.setObjectName("batch_crop")
        for key, info in CROPS.items():
            if key in farm.state["unlocked"]:
                self.crop.addItem(info["name"], key)
        chosen = self.crop.findData(crop)
        if chosen >= 0:
            self.crop.setCurrentIndex(chosen)
        row.addWidget(self.crop, 1)
        row.addWidget(QLabel("Terrenos"))
        self.quantity = QSpinBox()
        self.quantity.setObjectName("batch_quantity")
        row.addWidget(self.quantity)
        box.addLayout(row)
        self.summary = QLabel()
        self.summary.setObjectName("batch_summary")
        self.summary.setWordWrap(True)
        box.addWidget(self.summary)
        self.feedback = QLabel()
        self.feedback.setObjectName("batch_feedback")
        self.feedback.setWordWrap(True)
        box.addWidget(self.feedback)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel = QPushButton("Cancelar")
        self.cancel.setObjectName("batch_cancel")
        self.cancel.clicked.connect(self.reject)
        buttons.addWidget(self.cancel)
        self.confirm = QPushButton("Confirmar plantio")
        self.confirm.setObjectName("batch_confirm")
        self.confirm.clicked.connect(self.accept)
        buttons.addWidget(self.confirm)
        box.addLayout(buttons)
        self.crop.currentIndexChanged.connect(lambda: self.refresh_quote(reset_quantity=True))
        self.quantity.valueChanged.connect(self.refresh_quote)
        self.refresh_quote(reset_quantity=True)

    @staticmethod
    def _signature(crop, quote):
        return (
            crop,
            tuple(quote["plots"]),
            quote["count"],
            quote["cost"],
            quote["balance"],
            quote["available_count"],
            quote["affordable_count"],
        )

    def refresh_quote(self, value=None, *, reset_quantity=False):
        self.feedback.clear()
        key = self.crop.currentData()
        if key is None:
            self.quantity.setRange(0, 0)
            self.summary.setText("Não há culturas desbloqueadas para plantar.")
            self.confirm.setEnabled(False)
            self._reviewed_quote = None
            return
        available = self.farm.planting_quote(key)
        limit = available["affordable_count"]
        previous = self.quantity.value()
        was_blocked = self.quantity.blockSignals(True)
        try:
            self.quantity.setRange(1 if limit else 0, limit)
            self.quantity.setValue(limit if reset_quantity else min(previous, limit))
        finally:
            self.quantity.blockSignals(was_blocked)
        quote = self.farm.planting_quote(key, self.quantity.value())
        self._reviewed_quote = self._signature(key, quote)
        lines = [
            f"{quote['available_count']} terrenos livres; saldo permite {quote['affordable_count']}.",
            f"Plantar: {quote['count']} × {CROPS[key]['name']}.",
            f"Custo total: {money(quote['cost'])} moedas · Saldo: {money(quote['balance'])} moedas.",
        ]
        if not quote["available_count"]:
            lines.append("Não há terrenos livres para plantar.")
        elif not limit:
            lines.append(f"Saldo insuficiente: cada semente custa {money(CROPS[key]['seed'])} moedas.")
        else:
            lines.append(f"Saldo após o plantio: {money(quote['balance'] - quote['cost'])} moedas.")
        self.summary.setText("\n".join(lines))
        self.confirm.setEnabled(quote["count"] > 0 and quote["cost"] <= quote["balance"])

    def accept(self):
        key = self.crop.currentData()
        if key is None:
            return
        quote = self.farm.planting_quote(key, self.quantity.value())
        changed = self._signature(key, quote) != self._reviewed_quote
        invalid = (
            not quote["count"] or quote["count"] != self.quantity.value() or quote["cost"] > quote["balance"]
        )
        if changed or invalid:
            self.refresh_quote()
            self.feedback.setText(
                "Seu saldo ou os terrenos disponíveis mudaram. Confira os valores e confirme novamente."
            )
            return
        self.selection = key, tuple(quote["plots"])
        super().accept()

    def reject(self):
        self.selection = None
        super().reject()
