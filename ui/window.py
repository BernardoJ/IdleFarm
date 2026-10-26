"""Compact native desktop UI with fully functional farm management."""

from collections import deque
from datetime import datetime
import math
import time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontMetrics, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config.data import ANIMALS, BUILDINGS, CROPS, NAMES, ROOT, SCENES
from game.engine import GameError
from visual.scene import Renderer, SceneWidget, time_label

STYLE = """
QWidget { background: #263b32; color: #f0e5c8; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
QMainWindow { border: 2px solid #a68b58; }
QLabel { background: transparent; }
QLabel#title { font-size: 21px; font-weight: 800; color: #e6c780; letter-spacing: 3px; }
QLabel#coins { font-size: 19px; font-weight: bold; color: #f2ce7f; }
QLabel#muted { color: #b0bba1; font-size: 11px; }
QLabel#notice { color: #e8ce8e; padding: 4px; background: #314a3b; border-left: 3px solid #bba36b; }
QPushButton { background: #3f5740; border: 1px solid #849366; border-bottom: 3px solid #172d24;
              border-radius: 2px; padding: 5px 8px; min-height: 19px; }
QPushButton:hover { background: #526c49; border-color: #dcc58b; }
QPushButton:pressed, QPushButton:checked { background: #8b754b; color: #fff0cc; }
QPushButton:disabled { color: #8e9885; border-color: #50604b; background: #304536; }
QComboBox { padding: 5px; border: 1px solid #ae9868; background: #314a3b; min-height: 19px; }
QComboBox QAbstractItemView { background: #314a3b; selection-background-color: #7b724c; }
QCheckBox { spacing: 4px; }
QScrollArea { border: 1px solid #7c8056; background: #263b32; }
QScrollBar:vertical { width: 10px; background: #263b32; }
QScrollBar::handle:vertical { background: #8a9165; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QToolTip { color: #f4e7c6; background: #263b32; border: 1px solid #c1a76c; }
"""


def money(value):
    return f"{value:,}".replace(",", ".")


def duration(seconds):
    seconds = max(0, math.ceil(seconds))
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    return f"{h}h {m:02d}m" if h else f"{m:02d}m {s:02d}s"


def label(text="", muted=False):
    result = QLabel(text)
    result.setWordWrap(True)
    if muted:
        result.setObjectName("muted")
    return result


class FarmWindow(QMainWindow):
    def __init__(self, farm):
        super().__init__()
        self.farm = farm
        self.renderer = Renderer()
        self.messages = deque(maxlen=3)
        self.last_save = time.monotonic()
        self.setWindowTitle("IdleFarm · um canto para cultivar")
        self.setWindowIcon(QIcon(str(ROOT / "assets/icon.png")))
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(570)
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        self.setCentralWidget(root)
        header = QHBoxLayout()
        title = label("IDLEFARM")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        self.coins = label()
        self.coins.setObjectName("coins")
        header.addWidget(self.coins)
        layout.addLayout(header)
        bar = QHBoxLayout()
        self.time_info = label("", True)
        self.time_info.setWordWrap(False)
        bar.addWidget(self.time_info)
        bar.addStretch()
        self.top = QCheckBox("Sempre no topo")
        self.top.setChecked(farm.state["preferences"]["on_top"])
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.top.isChecked())
        self.top.toggled.connect(self.toggle_top)
        bar.addWidget(self.top)
        help_button = QPushButton("Como jogar")
        help_button.clicked.connect(self.help)
        bar.addWidget(help_button)
        layout.addLayout(bar)
        self.scene = SceneWidget(farm, self.renderer)
        self.scene.plot_selected.connect(self.select_plot)
        layout.addWidget(self.scene)
        tabs = QHBoxLayout()
        tabs.setSpacing(3)
        self.tabs = {}
        for key in SCENES:
            button = QPushButton(NAMES[key])
            button.setCheckable(True)
            button.setObjectName("tab_" + key)
            button.ensurePolished()
            # Native Windows font metrics can differ from Linux despite the same QSS.
            button.setMinimumWidth(QFontMetrics(button.font()).horizontalAdvance(NAMES[key]) + 20)
            button.clicked.connect(lambda checked=False, k=key: self.navigate(k))
            tabs.addWidget(button)
            self.tabs[key] = button
        layout.addLayout(tabs)
        self.manage = QPushButton("Ocultar gerenciamento")
        self.manage.clicked.connect(self.toggle_manage)
        layout.addWidget(self.manage)
        self.pages = QStackedWidget()
        self.pages.setFixedHeight(246)
        layout.addWidget(self.pages)
        self.create_fields()
        self.animal_rows = {}
        self.build_buttons = {}
        self.build_info = {}
        for building in BUILDINGS:
            self.create_building(building)
        self.production = label("", True)
        layout.addWidget(self.production)
        self.notice = label("Bem-vindo! Selecione um terreno e plante sua primeira semente.")
        self.notice.setObjectName("notice")
        self.notice.setMinimumHeight(29)
        layout.addWidget(self.notice)
        self.heartbeat = QTimer(self)
        self.heartbeat.timeout.connect(self.tick)
        self.heartbeat.start(1000)
        self.navigate(farm.state["preferences"]["scene"], save=False)
        self.refresh()
        self.setMinimumWidth(max(570, root.minimumSizeHint().width() + 4))
        self.resize(max(610, self.minimumWidth()), self.sizeHint().height())
        screen = QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            if self.sizeHint().height() > area.height() - 64:
                self.pages.hide()
                self.manage.setText("Gerenciar fazenda")
                self.adjustSize()
            self.resize(min(self.width(), area.width()), min(self.height(), area.height() - 24))
            self.move(
                max(area.left(), area.right() - self.width() - 18),
                max(area.top(), area.bottom() - self.height() - 44),
            )
        if farm.offline_reward:
            self.notify(
                f"Bem-vindo de volta! Animais produziram +{money(farm.offline_reward)} moedas (até 4h)."
            )
        if farm.store and farm.store.warning:
            self.notify(farm.store.warning)

    def scroll_page(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(9, 8, 9, 8)
        box.setSpacing(7)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.pages.addWidget(scroll)
        return box

    def create_fields(self):
        box = self.scroll_page()
        row = QHBoxLayout()
        self.plots = QComboBox()
        self.plots.setObjectName("plots")
        self.plots.currentIndexChanged.connect(self.plot_changed)
        row.addWidget(label("Terreno"))
        row.addWidget(self.plots, 1)
        self.expand = QPushButton()
        self.expand.setObjectName("expand")
        self.expand.clicked.connect(lambda: self.act(self.farm.expand, "Novo terreno adquirido."))
        row.addWidget(self.expand)
        box.addLayout(row)
        row = QHBoxLayout()
        self.crops = QComboBox()
        self.crops.setObjectName("crops")
        for key, crop in CROPS.items():
            self.crops.addItem(crop["name"], key)
        self.crops.currentIndexChanged.connect(self.refresh)
        row.addWidget(label("Semente"))
        row.addWidget(self.crops, 1)
        self.plant = QPushButton("Plantar")
        self.plant.setObjectName("plant")
        self.plant.clicked.connect(
            lambda: self.act(
                lambda: self.farm.plant(self.plots.currentIndex(), self.crops.currentData()),
                "Semente plantada. A natureza cuida do tempo.",
            )
        )
        row.addWidget(self.plant)
        self.harvest = QPushButton("Colher")
        self.harvest.setObjectName("harvest")
        self.harvest.clicked.connect(self.do_harvest)
        row.addWidget(self.harvest)
        box.addLayout(row)
        self.crop_info = label()
        box.addWidget(self.crop_info)
        self.plot_info = label()
        box.addWidget(self.plot_info)
        self.unlock_info = label("", True)
        box.addWidget(self.unlock_info)
        self.recover = QPushButton("Sementes de recomeço · recuperar 5 moedas")
        self.recover.clicked.connect(
            lambda: self.act(self.farm.recover, "Um novo começo! Você já pode plantar trigo.")
        )
        box.addWidget(self.recover)
        box.addStretch()

    def create_building(self, building):
        box = self.scroll_page()
        info = BUILDINGS[building]
        row = QHBoxLayout()
        heading = label(info["description"])
        row.addWidget(heading, 1)
        build = QPushButton()
        build.setObjectName("build_" + building)
        build.clicked.connect(
            lambda: self.act(lambda: self.farm.construct(building), info["name"] + " construído!")
        )
        row.addWidget(build)
        self.build_buttons[building] = build
        box.addLayout(row)
        self.build_info[building] = label("", True)
        box.addWidget(self.build_info[building])
        for key, animal in ANIMALS.items():
            if animal["building"] != building:
                continue
            row = QHBoxLayout()
            icon = QLabel()
            icon.setFixedSize(40, 40)
            icon.setPixmap(
                QPixmap.fromImage(self.renderer.icon(key)).scaled(
                    40, 40, Qt.KeepAspectRatio, Qt.FastTransformation
                )
            )
            row.addWidget(icon)
            text = label()
            text.setMinimumHeight(46)
            row.addWidget(text, 1)
            buy = QPushButton()
            buy.setObjectName("buy_" + key)
            buy.clicked.connect(
                lambda checked=False, k=key: self.act(
                    lambda: self.farm.buy_animal(k), ANIMALS[k]["name"] + " chegou à fazenda!"
                )
            )
            row.addWidget(buy)
            box.addLayout(row)
            self.animal_rows[key] = (text, buy)
        box.addStretch()

    def act(self, action, message):
        try:
            result = action()
            self.notify(message)
            self.refresh()
            return result
        except (GameError, OSError) as exc:
            self.notify(str(exc))
            self.refresh()
            return None

    def do_harvest(self):
        result = self.act(lambda: self.farm.harvest(self.plots.currentIndex()), "Colheita realizada!")
        if result is not None:
            self.notify(f"Colheita realizada · +{money(result)} moedas.")

    def notify(self, text):
        self.messages.append((time.monotonic(), text))
        self.notice.setText(text)

    def select_plot(self, index):
        self.plots.setCurrentIndex(index)

    def plot_changed(self):
        if hasattr(self, "scene"):
            self.scene.selected = self.plots.currentIndex()
        if hasattr(self, "animal_rows"):
            self.refresh()

    def navigate(self, scene, save=True):
        if save:
            try:
                self.farm.preference("scene", scene)
            except OSError as exc:
                self.notify(str(exc))
        self.scene.scene = scene
        self.pages.setCurrentIndex(SCENES.index(scene))
        for key, button in self.tabs.items():
            button.setChecked(key == scene)
        self.scene.update()

    def toggle_top(self, checked):
        old = self.farm.state["preferences"]["on_top"]
        result = self.act(lambda: self.farm.preference("on_top", checked), "Preferência de janela salva.")
        if result is None and self.farm.state["preferences"]["on_top"] != checked:
            self.top.blockSignals(True)
            self.top.setChecked(old)
            self.top.blockSignals(False)
            return
        self.setWindowFlag(Qt.WindowStaysOnTopHint, checked)
        self.show()

    def toggle_manage(self):
        visible = not self.pages.isVisible()
        self.pages.setVisible(visible)
        self.manage.setText("Ocultar gerenciamento" if visible else "Gerenciar fazenda")
        self.adjustSize()

    def tick(self):
        try:
            gained = self.farm.advance()
            if gained:
                self.notify(f"Produção da fazenda · +{money(gained)} moedas.")
            if gained or time.monotonic() - self.last_save >= 30:
                self.farm.save()
                self.last_save = time.monotonic()
        except OSError:
            self.notify("Não foi possível salvar. Verifique o espaço e a permissão da pasta de saves.")
        self.refresh()

    def refresh(self):
        if not hasattr(self, "animal_rows"):
            return
        state = self.farm.state
        coins = state["coins"]
        self.coins.setText(money(coins) + " moedas")
        moment = datetime.now()
        self.time_info.setText(time_label(moment.hour) + moment.strftime(" · %H:%M"))
        self.plots.blockSignals(True)
        current = max(0, self.plots.currentIndex())
        while self.plots.count() < len(state["plots"]):
            self.plots.addItem("")
        for index, plot in enumerate(state["plots"]):
            status = (
                "livre"
                if plot is None
                else CROPS[plot["crop"]]["name"]
                + " · "
                + ("pronta!" if not self.farm.remaining(index) else duration(self.farm.remaining(index)))
            )
            self.plots.setItemText(index, f"{index + 1:02d} · {status}")
        self.plots.setCurrentIndex(current)
        self.plots.blockSignals(False)
        for i, (key, crop) in enumerate(CROPS.items()):
            unlocked = key in state["unlocked"]
            self.crops.model().item(i).setEnabled(unlocked)
            self.crops.setItemText(i, crop["name"] + ("" if unlocked else f" · receita {crop['unlock']}"))
        key = self.crops.currentData()
        crop = CROPS[key]
        plot = state["plots"][current]
        self.crop_info.setText(
            f"{crop['name']}  ·  semente {crop['seed']} moedas  ·  cresce em {duration(crop['seconds'])}  ·  colheita +{crop['reward']}"
        )
        self.plot_info.setText(
            "Terra preparada. Escolha a cultura e plante."
            if not plot
            else f"{CROPS[plot['crop']]['name']} · "
            + (
                "Pronta para colher!"
                if not self.farm.remaining(current)
                else "Tempo restante: " + duration(self.farm.remaining(current))
            )
        )
        self.plant.setEnabled(plot is None and coins >= crop["seed"] and key in state["unlocked"])
        self.harvest.setEnabled(plot is not None and self.farm.remaining(current) == 0)
        price = self.farm.expansion_price()
        self.expand.setText(f"+ Terreno · {money(price)}")
        self.expand.setEnabled(coins >= price)
        self.recover.setVisible(self.farm.can_recover())
        self.unlock_info.setText(
            f"Receita acumulada: {money(state['earned'])} · Novas culturas em 200 / 800 / 1.600 moedas. Colheita manual; crescimento continua sem limite offline."
        )
        for building in BUILDINGS:
            owned = building in state["buildings"]
            button = self.build_buttons[building]
            button.setText("Construído" if owned else f"Construir · {money(BUILDINGS[building]['cost'])}")
            button.setEnabled(not owned and coins >= BUILDINGS[building]["cost"])
            self.build_info[building].setText(
                ("Instalação adquirida" if owned else "Instalação ainda não construída")
                + f" · Produção: {self.farm.hourly(building):.1f} moedas/h"
            )
        for key, (text, buy) in self.animal_rows.items():
            animal = ANIMALS[key]
            count = self.farm.count(key)
            price = self.farm.animal_price(key)
            detail = (
                f"+{animal['reward']} a cada {duration(animal['seconds'])}"
                if animal["reward"]
                else "Companhia · sem produção"
            )
            next_time = self.farm.next_production(key)
            total = f" · total +{count * animal['reward']}/ciclo" if animal["reward"] else ""
            text.setText(
                f"{animal['name']} · {count} adquirido(s){total}\n{detail}"
                + (" · próxima em " + duration(next_time) if next_time is not None else "")
            )
            text.setToolTip(
                f"Rendimento total por ciclo: {count * animal['reward']} moedas. Cada compra aumenta o preço desta espécie em 12%."
            )
            buy.setText(f"Comprar · {money(price)}")
            buy.setEnabled(animal["building"] in state["buildings"] and coins >= price)
        total = sum(a["count"] for a in state["animals"])
        self.production.setText(
            f"{len(state['plots'])} terrenos  ·  {total} animais  ·  {self.farm.hourly():.1f} moedas/h  ·  Produzido: {money(state['animal_earned'])}  ·  Offline: até 4h"
        )
        if self.messages and time.monotonic() - self.messages[-1][0] > 12:
            self.notice.setText("Tudo salvo. Crescer também é saber esperar.")

    def help(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Como cuidar da sua fazenda")
        dialog.setMinimumWidth(400)
        box = QVBoxLayout(dialog)
        box.addWidget(
            label(
                "Plante trigo e cenoura nos dois terrenos iniciais. O custo é debitado ao plantar; a recompensa só chega ao colher. Clique na plantação do cenário ou escolha seu terreno na lista. Todos os terrenos continuam funcionando, mesmo além dos cinco representantes visuais."
            )
        )
        box.addWidget(
            label(
                "Culturas desbloqueiam com receita acumulada: milho em 200, morango em 800 e abóbora em 1.600. Expansões começam em 120 moedas (+35% por terreno)."
            )
        )
        box.addWidget(
            label(
                "Construa instalações nas abas e compre animais. Cada animal produz individualmente; novas compras da mesma espécie custam 12% a mais. Cachorros são companheiros e não geram moedas. A produção total e a próxima entrega aparecem no gerenciamento."
            )
        )
        box.addWidget(
            label(
                "Ao reabrir, os animais produzem por até 4h. Plantações crescem durante todo o tempo real decorrido e esperam a colheita. O jogo salva automaticamente e após cada ação. Sem fontes de renda e com menos de 5 moedas, use as sementes de recomeço."
            )
        )
        close = QPushButton("Vamos cultivar")
        close.clicked.connect(dialog.accept)
        box.addWidget(close)
        dialog.exec()

    def closeEvent(self, event):
        try:
            self.farm.advance()
            self.farm.save()
            self.heartbeat.stop()
            self.scene.timer.stop()
            event.accept()
        except OSError as exc:
            QMessageBox.warning(self, "Não foi possível salvar", str(exc))
            event.ignore()
