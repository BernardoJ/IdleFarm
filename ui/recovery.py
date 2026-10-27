"""A recovery choice always precedes replacing existing player progress."""

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout

from game.state import fresh
from game.diagnostics import diagnostic_path
from game.storage import RecoveryRequired
from ui.window import STYLE, label


class RecoveryDialog(QDialog):
    def __init__(self, store, recovery, *, clock=time.time, parent=None):
        super().__init__(parent)
        self.store, self.recovery, self.clock = store, recovery, clock
        self.extra_details = []
        self.setWindowTitle("IdleFarm · recuperar sua fazenda")
        self.setMinimumWidth(520)
        self.setStyleSheet(STYLE)
        box = QVBoxLayout(self)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(12)
        title = label("RECUPERAR PROGRESSO")
        title.setObjectName("title")
        box.addWidget(title)
        self.message = label(
            "Não foi possível abrir o seu progresso salvo. Seus arquivos foram preservados. "
            "Você pode tentar novamente, recuperar uma cópia de segurança ou escolher uma nova fazenda."
        )
        box.addWidget(self.message)
        self.backup_info = label("", True)
        box.addWidget(self.backup_info)
        self.status = label()
        self.status.setObjectName("notice")
        self.status.hide()
        box.addWidget(self.status)
        actions = QHBoxLayout()
        self.retry_button = QPushButton("Tentar novamente")
        self.retry_button.setObjectName("retry_recovery")
        self.retry_button.setDefault(True)
        self.retry_button.clicked.connect(self.retry)
        actions.addWidget(self.retry_button)
        self.restore_button = QPushButton("Restaurar backup")
        self.restore_button.setObjectName("restore_backup")
        self.restore_button.setAutoDefault(False)
        self.restore_button.clicked.connect(self.restore)
        actions.addWidget(self.restore_button)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setObjectName("cancel_recovery")
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        actions.addWidget(self.cancel_button)
        box.addLayout(actions)
        choices = QHBoxLayout()
        self.details_button = QPushButton("Consultar detalhes")
        self.details_button.setObjectName("recovery_details")
        self.details_button.setAutoDefault(False)
        self.details_button.clicked.connect(self.toggle_details)
        choices.addWidget(self.details_button)
        choices.addStretch()
        self.new_button = QPushButton("Iniciar nova fazenda")
        self.new_button.setObjectName("new_farm")
        self.new_button.setAutoDefault(False)
        self.new_button.clicked.connect(self.start_new)
        choices.addWidget(self.new_button)
        box.addLayout(choices)
        self.details = QPlainTextEdit()
        self.details.setObjectName("recovery_details_text")
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(150)
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.details.hide()
        box.addWidget(self.details)
        self.update_recovery(recovery)

    def update_recovery(self, recovery):
        self.recovery = recovery
        available = recovery.backup_data is not None
        self.restore_button.setEnabled(available)
        self.backup_info.setText(
            "Encontramos uma cópia de segurança válida para recuperar sua fazenda."
            if available
            else "Nenhuma cópia de segurança válida está disponível. Você ainda pode tentar novamente ou consultar os detalhes."
        )
        self.update_details()

    def update_details(self):
        files = "\n".join(str(path.resolve()) for path in self.recovery.existing_paths)
        text = self.recovery.details + "\n\nArquivos existentes preservados:\n" + files
        log_path = diagnostic_path(self.store.path)
        if log_path.exists():
            text += "\n\nLog de diagnóstico:\n" + str(log_path.resolve())
        if self.extra_details:
            text += "\n\nÚltimas tentativas:\n" + "\n".join(self.extra_details)
        self.details.setPlainText(text)

    def toggle_details(self):
        visible = self.details.isHidden()
        self.details.setVisible(visible)
        self.details_button.setText("Ocultar detalhes" if visible else "Consultar detalhes")
        self.adjustSize()

    def show_failure(self, exc):
        if self.store.recovery is not None:
            self.update_recovery(self.store.recovery)
        self.extra_details.append(str(exc))
        self.update_details()
        self.status.setText(
            "Não foi possível concluir a recuperação. Seus arquivos continuam preservados. "
            "Confira o espaço disponível e tente novamente; os detalhes podem ajudar."
        )
        self.status.show()

    def retry(self):
        try:
            data = self.store.load()
        except RecoveryRequired as recovery:
            self.update_recovery(recovery)
            self.status.setText("O progresso ainda não pôde ser aberto. Nenhum arquivo foi substituído.")
            self.status.show()
            return
        except (OSError, ValueError) as exc:
            self.show_failure(exc)
            return
        if data is None:
            # Even if somebody removes files while the dialog is open, the
            # previous diagnosis must not silently become a fresh installation.
            self.restore_button.setEnabled(False)
            self.status.setText(
                "Não encontramos um progresso válido para abrir. "
                "Para começar outra partida, escolha Iniciar nova fazenda."
            )
            self.status.show()
            return
        self.accept()

    def restore(self):
        if not self.restore_button.isEnabled():
            return
        answer = QMessageBox.question(
            self,
            "Restaurar a cópia de segurança?",
            "Você retomará o progresso da cópia válida. O arquivo atual será preservado "
            "antes da restauração. Deseja continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.store.restore_backup()
        except (OSError, ValueError) as exc:
            self.show_failure(exc)
            return
        self.accept()

    def start_new(self):
        answer = QMessageBox.question(
            self,
            "Iniciar uma nova fazenda?",
            "Você começará outra partida. Os arquivos anteriores serão preservados "
            "para uma possível recuperação. Deseja continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.store.start_new(fresh(self.clock()))
        except (OSError, ValueError) as exc:
            self.show_failure(exc)
            return
        self.accept()
