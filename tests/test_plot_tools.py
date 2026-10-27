"""A batch proposal must be explicit, affordable and refreshed before acceptance."""

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from ui.plot_tools import ReplantDialog


def configure(farm, coins, plots):
    farm.state["coins"] = coins
    farm.state["plots"] = [None] * plots
    farm.save()


def test_confirmed_dialog_is_only_a_proposal_and_never_charges(app, farm):
    before, saved = deepcopy(farm.state), farm.store.path.read_bytes()
    dialog = ReplantDialog(farm)
    try:
        assert dialog.quantity.value() == 2
        assert dialog.confirm.isEnabled()
        assert "Custo total: 10 moedas" in dialog.summary.text()
        assert "Saldo: 50 moedas" in dialog.summary.text()
        QTest.mouseClick(dialog.confirm, Qt.LeftButton)
        assert dialog.result() == QDialog.Accepted
        assert dialog.selection == ("wheat", (0, 1))
        assert farm.state == before and farm.store.path.read_bytes() == saved
    finally:
        dialog.close()


def test_crop_and_quantity_changes_show_exact_cost(app, farm):
    configure(farm, 20, 4)
    dialog = ReplantDialog(farm)
    try:
        assert dialog.quantity.value() == 4
        dialog.crop.setCurrentIndex(dialog.crop.findData("carrot"))
        assert dialog.quantity.value() == 2
        assert "4 terrenos livres; saldo permite 2" in dialog.summary.text()
        assert "Custo total: 20 moedas" in dialog.summary.text()
        dialog.quantity.setValue(1)
        assert "Custo total: 10 moedas" in dialog.summary.text()
        assert "Saldo após o plantio: 10 moedas" in dialog.summary.text()
        dialog.accept()
        assert dialog.selection == ("carrot", (0,))
        assert farm.state["coins"] == 20
    finally:
        dialog.close()


def test_partial_affordability_requires_reviewed_quantity_confirmation(app, farm):
    configure(farm, 12, 5)
    dialog = ReplantDialog(farm)
    try:
        assert "5 terrenos livres; saldo permite 2" in dialog.summary.text()
        assert dialog.quantity.value() == dialog.quantity.maximum() == 2
        assert "Custo total: 10 moedas" in dialog.summary.text()
        assert dialog.selection is None
        dialog.accept()
        assert dialog.selection == ("wheat", (0, 1))
        assert farm.state["plots"] == [None] * 5
    finally:
        dialog.close()


def test_insufficient_balance_cannot_confirm_even_one_plot(app, farm):
    configure(farm, 4, 2)
    dialog = ReplantDialog(farm)
    try:
        assert dialog.quantity.value() == 0
        assert not dialog.confirm.isEnabled()
        assert "Saldo insuficiente" in dialog.summary.text()
        assert "Saldo: 4 moedas" in dialog.summary.text()
        QTest.mouseClick(dialog.confirm, Qt.LeftButton)
        dialog.accept()
        assert dialog.selection is None and dialog.result() != QDialog.Accepted
        assert farm.state["coins"] == 4
    finally:
        dialog.close()


def test_no_free_plots_cannot_confirm(app, farm):
    farm.plant(0, "wheat")
    farm.plant(1, "carrot")
    before, saved = deepcopy(farm.state), farm.store.path.read_bytes()
    dialog = ReplantDialog(farm)
    try:
        assert "Não há terrenos livres" in dialog.summary.text()
        assert not dialog.confirm.isEnabled() and dialog.quantity.value() == 0
        dialog.accept()
        assert dialog.selection is None
        assert farm.state == before and farm.store.path.read_bytes() == saved
    finally:
        dialog.close()


def test_cancel_does_not_change_progress_or_save(app, farm):
    before, saved = deepcopy(farm.state), farm.store.path.read_bytes()
    dialog = ReplantDialog(farm)
    try:
        dialog.crop.setCurrentIndex(dialog.crop.findData("carrot"))
        dialog.quantity.setValue(1)
        QTest.mouseClick(dialog.cancel, Qt.LeftButton)
        assert dialog.result() == QDialog.Rejected and dialog.selection is None
        assert farm.state == before and farm.store.path.read_bytes() == saved
    finally:
        dialog.close()


def test_changed_balance_requires_new_review_instead_of_silent_partial_batch(app, farm):
    dialog = ReplantDialog(farm)
    try:
        assert dialog.quantity.value() == 2
        farm.state["coins"] = 6
        farm.save()
        saved = farm.store.path.read_bytes()
        dialog.accept()
        assert dialog.selection is None and dialog.result() != QDialog.Accepted
        assert dialog.quantity.value() == 1 and "confirme novamente" in dialog.feedback.text()
        assert "Saldo: 6 moedas" in dialog.summary.text()
        dialog.accept()
        assert dialog.selection == ("wheat", (0,))
        assert farm.state["coins"] == 6 and farm.store.path.read_bytes() == saved
    finally:
        dialog.close()


def test_changed_eligible_plots_require_new_review(app, farm):
    dialog = ReplantDialog(farm)
    try:
        farm.plant(0, "wheat")
        before = deepcopy(farm.state)
        dialog.accept()
        assert dialog.selection is None and dialog.quantity.value() == 1
        assert "confirme novamente" in dialog.feedback.text()
        dialog.accept()
        assert dialog.selection == ("wheat", (1,))
        assert farm.state == before
    finally:
        dialog.close()


def test_changed_balance_is_reviewed_even_when_original_batch_still_affordable(app, farm):
    dialog = ReplantDialog(farm)
    try:
        farm.state["coins"] += 15
        farm.save()
        dialog.accept()
        assert dialog.selection is None and "Saldo: 65 moedas" in dialog.summary.text()
        dialog.accept()
        assert dialog.selection == ("wheat", (0, 1))
    finally:
        dialog.close()


def test_dialog_only_lists_unlocked_crops(app, farm):
    dialog = ReplantDialog(farm, "pumpkin")
    try:
        keys = [dialog.crop.itemData(index) for index in range(dialog.crop.count())]
        assert keys == ["wheat", "carrot"]
        assert dialog.crop.currentData() == "wheat"
    finally:
        dialog.close()
