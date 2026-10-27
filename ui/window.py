"""Compact native desktop UI with fully functional farm management."""

from collections import deque
from datetime import datetime
import math
import time
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QActionGroup, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from config.data import ANIMALS, BUILDINGS, CROPS, NAMES, ROOT, SCENES
from config.version import VERSION
from game.engine import GameError, PendingSaveError
from game.persistence import SaveStatus
from visual.scene import Renderer, SceneWidget, time_label

STYLE = """
QWidget { background: #2c342b; color: #f4e7c6; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
QMainWindow { border: 3px solid #a68b58; }
QLabel { background: transparent; }
QLabel#title { font-family: Georgia, serif; font-size: 23px; font-weight: bold; color: #e8c581; letter-spacing: 3px; }
QLabel#coins { font-size: 18px; font-weight: bold; color: #f2ce7f; padding: 4px 8px;
              border: 1px solid #97835a; background: #26392e; }
QLabel#muted { color: #c0bda2; font-size: 11px; }
QLabel#notice { color: #f0d9a5; padding: 5px; background: #3e4431; border-left: 3px solid #bba36b; }
QPushButton, QToolButton { background: #6b593c; border: 1px solid #b79b65;
              border-top: 2px solid #c4aa75; border-bottom: 3px solid #3d3023;
              border-radius: 0px; padding: 5px 8px; min-height: 19px; }
QPushButton:hover, QToolButton:hover { background: #806b46; border-color: #e4cb91; }
QPushButton:pressed, QPushButton:checked, QToolButton:pressed { background: #8b754b; color: #fff0cc; }
QPushButton:disabled { color: #a49e88; border-color: #655f48; background: #444a39; }
QToolButton::menu-indicator { subcontrol-position: right center; right: 6px; }
QToolButton { padding-right: 20px; }
QMenu { background: #3c4431; border: 2px solid #b79b65; padding: 5px; }
QMenu::item { padding: 8px 28px; }
QMenu::item:selected { background: #806b46; }
QLabel#current_area { font-size: 15px; font-weight: bold; color: #e6c780; }
QComboBox { padding: 5px; border: 1px solid #ae9868; background: #3c4431; min-height: 19px; }
QComboBox QAbstractItemView { background: #314a3b; selection-background-color: #7b724c; }
QCheckBox { spacing: 4px; }
QScrollArea { border: 2px solid #958359; background: #2c342b; }
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
        self.icons = {
            key: QIcon(QPixmap.fromImage(self.renderer.icon(key))) for key in (*SCENES, *CROPS, *ANIMALS)
        }
        self.messages = deque(maxlen=3)
        self.last_save = time.monotonic()
        self.last_save_attempt = self.last_save
        self.setWindowTitle(f"IdleFarm {VERSION} · um canto para cultivar")
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
        header.addWidget(label("v" + VERSION, True))
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
        navigation = QHBoxLayout()
        self.area_icon = QLabel()
        self.area_icon.setFixedSize(48, 27)
        navigation.addWidget(self.area_icon)
        self.current_area = label()
        self.current_area.setObjectName("current_area")
        navigation.addWidget(self.current_area)
        navigation.addStretch()
        self.area_menu_button = QToolButton()
        self.area_menu_button.setObjectName("area_menu_button")
        self.area_menu_button.setText("Áreas da fazenda")
        self.area_menu_button.setAccessibleName("Menu de áreas da fazenda")
        self.area_menu_button.setToolTip("Escolha a área da fazenda que deseja visitar.")
        self.area_menu = QMenu(self.area_menu_button)
        self.area_actions = {}
        area_group = QActionGroup(self.area_menu)
        area_group.setExclusive(True)
        for key in SCENES:
            action = self.area_menu.addAction(NAMES[key])
            action.setIcon(self.icons[key])
            action.setCheckable(True)
            action.setObjectName("area_" + key)
            area_group.addAction(action)
            action.triggered.connect(lambda checked=False, k=key: self.navigate(k))
            self.area_actions[key] = action
        self.area_menu_button.setMenu(self.area_menu)
        self.area_menu_button.setPopupMode(QToolButton.InstantPopup)
        navigation.addWidget(self.area_menu_button)
        layout.addLayout(navigation)
        self.scene = SceneWidget(farm, self.renderer)
        self.scene.plot_selected.connect(self.select_plot)
        layout.addWidget(self.scene)
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
        save_row = QHBoxLayout()
        self.save_info = label()
        self.save_info.setObjectName("save_state")
        save_row.addWidget(self.save_info, 1)
        self.retry_save = QPushButton("Tentar salvar")
        self.retry_save.clicked.connect(self.save_now)
        save_row.addWidget(self.retry_save)
        layout.addLayout(save_row)
        farm.persistence.subscribe(self.refresh_save_state)
        self.notice = label("Bem-vindo! Selecione um terreno e plante sua primeira semente.")
        self.notice.setObjectName("notice")
        self.notice.setMinimumHeight(29)
        layout.addWidget(self.notice)
        self.heartbeat = QTimer(self)
        self.heartbeat.timeout.connect(self.tick)
        self.heartbeat.start(1000)
        self.navigate("fields", save=False)
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
        self.crops.setIconSize(QSize(28, 26))
        for key, crop in CROPS.items():
            self.crops.addItem(self.icons[key], crop["name"], key)
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
        generation = self.farm.persistence.saved_generation
        try:
            result = action()
            if self.farm.persistence.saved_generation != generation:
                self.last_save_attempt = self.last_save = time.monotonic()
            self.notify(message)
            self.refresh()
            return result
        except PendingSaveError as exc:
            self.last_save_attempt = time.monotonic()
            self.notify(message + " Alterações ainda não salvas; tente salvar novamente.")
            self.refresh()
            return exc.result
        except (GameError, OSError) as exc:
            if isinstance(exc, OSError):
                self.last_save_attempt = time.monotonic()
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

    def refresh_save_state(self):
        state = self.farm.persistence
        messages = {
            SaveStatus.SAVED: "Tudo salvo",
            SaveStatus.SAVING: "Salvando…",
            SaveStatus.PENDING: "Alterações não salvas",
            SaveStatus.ERROR: "Erro ao salvar · alterações não salvas",
        }
        self.save_info.setText(messages[state.status])
        self.save_info.setToolTip(state.last_error or "O progresso é salvo após ações e automaticamente.")
        self.retry_save.setVisible(state.status == SaveStatus.ERROR)

    def save_now(self):
        self.last_save_attempt = time.monotonic()
        try:
            saved = self.farm.save()
            if saved:
                self.last_save = self.last_save_attempt
            return saved
        except OSError:
            self.notify(
                "Não foi possível salvar. O progresso continua pendente nesta janela. Tente novamente."
            )
            return False
        finally:
            self.refresh_save_state()

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
        self.current_area.setText(NAMES[scene])
        self.area_icon.setPixmap(self.icons[scene].pixmap(48, 27))
        for key, action in self.area_actions.items():
            action.setChecked(key == scene)
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
        gained = self.farm.advance()
        if gained:
            self.notify(f"Produção da fazenda · +{money(gained)} moedas.")
        failed = self.farm.persistence.last_error is not None
        due = time.monotonic() - self.last_save_attempt >= (10 if failed else 30)
        if self.farm.persistence.dirty and (due or (gained and not failed)):
            self.save_now()
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
            self.notice.setText("Crescer também é saber esperar.")
        self.refresh_save_state()

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
                "O jogo começa nas plantações. Use o menu Áreas da fazenda para visitar uma área por vez, construir instalações e comprar animais. Cada animal produz individualmente; novas compras da mesma espécie custam 12% a mais. Cachorros são companheiros e não geram moedas. A produção total e a próxima entrega aparecem no gerenciamento."
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
