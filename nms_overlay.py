"""NMS End-Game Overlay — checklist do No Man's Sky como overlay no jogo.

- Janela pequena, sempre no topo, semi-transparente, tema Deep Space.
- Le os topicos direto do .md do Obsidian e salva o [x] de volta nele.
- Modo TRAVADO (F8): cliques atravessam a janela -> nao atrapalha o jogo.
- Modo LIVRE (F8): da pra clicar e marcar as conquistas.
- IMPORTANTE: deixe o NMS em modo "Janela sem bordas" (tela cheia
  exclusiva esconde qualquer overlay, isso vale pra qualquer programa).

Uso: iniciar.bat na pasta do projeto (ou python nms_overlay.py)
Atalhos: tecla de trava (padrao F8, clique nela p/ trocar) = trava/destrava.
"""

import ctypes
import json
import os
import re
import shutil
import sys

# No executavel (PyInstaller), config e checklist vivem em lugares distintos:
# config fica junto do .exe (persiste entre execucoes); assets vem do cache
# extraido (_MEIPASS).
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    RESOURCE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = BASE_DIR
CONFIG_PATH = os.path.join(BASE_DIR, "overlay_config.json")
# Checklist padrao embutido no projeto; troque o caminho em
# overlay_config.json (md_path) para usar um .md da sua vault/maquina.
DEFAULT_MD = os.path.join(RESOURCE_DIR, "checklist", "nms-endgame-checklist.md")

RE_ITEM = re.compile(r"^(\s*)- \[([ xX])\](.*)$")
RE_H2 = re.compile(r"^##\s+(.*)$")
RE_H3 = re.compile(r"^###\s+(.*)$")

# ---------------------------------------------------------------- config ---
DEFAULT_CONFIG = {
    "md_path": DEFAULT_MD,
    "opacity": 0.88,
    "width": 340,
    "height": 480,
    "locked": False,  # comeca livre pra configurar; trave ao jogar
    "hotkey_vk": 0x77,  # F8; troque clicando no botao da tecla
    "hotkey_name": "F8",
    "focus_hotkey_vk": 0x79,  # F9: chama o overlay p/ frente sem alt-tab
    "focus_hotkey_name": "F9",
    "x": None,  # posicao lembrada; None = canto inferior-direito
    "y": None,
    "view": {"home": True, "sec": 0},  # tela inicial = overview
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# --------------------------------------------------------------- parser ---
def parse_markdown(path):
    """Le o .md e devolve (linhas, secoes).

    secoes = [{"titulo": str, "blocos": [...] }]
    bloco = ("item", {...}) | ("sub", titulo)  # sub = cabecalho ### dentro da secao
    item = {"line": idx, "checked": bool, "indent": str, "text": str}
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    sections = []
    current = None
    for idx, raw in enumerate(lines):
        line = raw.rstrip("\n")
        m2 = RE_H2.match(line)
        if m2:
            current = {"titulo": m2.group(1).strip(), "blocos": []}
            sections.append(current)
            continue
        if current is None:
            continue
        m3 = RE_H3.match(line)
        if m3:
            current["blocos"].append(("sub", m3.group(1).strip()))
            continue
        mi = RE_ITEM.match(line)
        if mi:
            current["blocos"].append((
                "item",
                {"line": idx,
                 "checked": mi.group(2).lower() == "x",
                 "indent": mi.group(1),
                 "text": mi.group(3).strip()},
            ))
    return lines, sections


def set_line_checked(lines, idx, checked):
    """Troca so o caractere dentro do [ ] preservando o resto da linha."""
    line = lines[idx]
    mark = "x" if checked else " "
    lines[idx] = re.sub(r"- \[[ xX]\]", "- [%s]" % mark, line, count=1)


def section_progress(section):
    items = [b[1] for b in section["blocos"] if b[0] == "item"]
    if not items:
        return 0, 0
    done = sum(1 for it in items if it["checked"])
    return done, len(items)


# ------------------------------------------------------------------ GUI ---
from PySide6.QtCore import (
    Qt, QTimer, QPoint, QEvent, QAbstractNativeEventFilter, Signal,
    QPropertyAnimation, QEasingCurve, QAbstractAnimation, QUrl,
)
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QScrollArea, QCheckBox, QLineEdit, QSlider, QProgressBar,
    QFileDialog, QMessageBox, QSizeGrip, QSizePolicy, QMenu,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
)

def qt_key_to_vk(key):
    """Mapeia Qt.Key_* -> (codigo VK do Windows, nome). None se nao suportada."""
    k = int(key)
    if int(Qt.Key_F1) <= k <= int(Qt.Key_F24):
        n = k - int(Qt.Key_F1) + 1
        return 0x6F + n, "F%d" % n
    if int(Qt.Key_A) <= k <= int(Qt.Key_Z):
        ch = chr(ord("A") + (k - int(Qt.Key_A)))
        return ord(ch), ch
    if int(Qt.Key_0) <= k <= int(Qt.Key_9):
        ch = chr(ord("0") + (k - int(Qt.Key_0)))
        return ord(ch), ch
    extra = {
        int(Qt.Key_Insert): (0x2D, "Insert"),
        int(Qt.Key_Delete): (0x2E, "Delete"),
        int(Qt.Key_Home): (0x24, "Home"),
        int(Qt.Key_End): (0x23, "End"),
        int(Qt.Key_PageUp): (0x21, "PgUp"),
        int(Qt.Key_PageDown): (0x22, "PgDn"),
        int(Qt.Key_Up): (0x26, "Cima"),
        int(Qt.Key_Down): (0x28, "Baixo"),
        int(Qt.Key_Left): (0x25, "Esq"),
        int(Qt.Key_Right): (0x27, "Dir"),
        int(Qt.Key_Pause): (0x13, "Pause"),
    }
    return extra.get(k)


# Identidade "Deep Space": dark elegante, accent ciano discreto,
# sucesso verde suave, foco dourado. Texto sempre 100% opaco;
# so os fundos usam rgba() (slider de transparencia nao apaga letra).
ACCENT = "#43c8f5"  # ciano discreto (interacoes, links, destaques)
TEXT = "#eef2fa"  # branco suave
DIM = "#98a2b8"  # cinza secundario
SUCCESS = "#3ddc97"  # verde suave (concluido)
FOCUS_YELLOW = "#ffd60a"  # dourado do foco
BORDER = "#2a3450"  # borda sutil solida
FONT = '"Segoe UI", Consolas, monospace'

BG_RGB = (7, 11, 22)
PANE_RGB = (17, 23, 40)
INPUT_RGB = (26, 34, 56)
FOCUS_RGB = (46, 34, 8)


def build_qss(bg_alpha=0.88):
    """Monta o QSS com alfa SO nos fundos; texto/bordas sempre 100% opacos.

    O slider antigo usava setWindowOpacity(), que mistura a janela INTEIRA
    (texto junto) e apagava as letras. Agora a janela fica sempre opaca e
    so as camadas de fundo usam rgba() — da p/ deixar o fundo bem
    transparente sem perder leitura.
    """
    try:
        a = min(1.0, max(0.15, float(bg_alpha)))
    except (TypeError, ValueError):
        a = 0.88
    ia = max(a, 0.75)  # inputs afundam demais se transparentes; piso maior

    def rgba(rgb, alpha):
        return "rgba(%d, %d, %d, %.3f)" % (rgb[0], rgb[1], rgb[2], alpha)

    bg = rgba(BG_RGB, a)
    pane = rgba(PANE_RGB, a)
    inp = rgba(INPUT_RGB, ia)
    focusbg = rgba(FOCUS_RGB, a)
    chunk = ("qlineargradient(x1:0, y1:0, x2:1, y2:0, "
             "stop:0 #2aa9dd, stop:1 #7fe3ff)")
    return """
QWidget#root { background: %(bg)s; border: 1px solid %(border)s; border-radius: 14px; }
QWidget#page { background: %(pane)s; border-radius: 10px; }
QWidget#inner { background: transparent; }
QWidget#item { background: transparent; border-radius: 8px; }
QWidget#item:hover { background: rgba(255, 255, 255, 0.045); }
QWidget#card { background: %(inp)s; border: 1px solid %(border)s; border-radius: 10px; }
QWidget#card:hover { border-color: %(accent)s; background: rgba(255, 255, 255, 0.05); }
QWidget#focusCard { background: %(focusbg)s; border: 1px solid %(yellow)s; border-radius: 12px; }
QLabel { color: %(text)s; font-family: %(font)s; background: transparent; }
QLabel#iconMark { color: %(accent)s; font-size: 15px; font-weight: bold; }
QLabel#appTitle { color: %(text)s; font-weight: 600; font-size: 13px; }
QLabel#eyebrow { color: %(dim)s; font-size: 10px; }
QLabel#secTitleBig { color: %(text)s; font-weight: 600; font-size: 13px; }
QLabel#pctBig { color: %(text)s; font-weight: 600; font-size: 30px; }
QLabel#dashSub { color: %(dim)s; font-size: 11px; }
QLabel#cardTitle { color: %(text)s; font-weight: 600; font-size: 12px; }
QLabel#cardCount { color: %(dim)s; font-size: 11px; }
QLabel#sub { color: %(text)s; font-weight: 600; font-size: 12px; padding-top: 10px; }
QLabel#dim { color: %(dim)s; font-size: 10px; }
QLabel#item { color: %(text)s; font-family: %(font)s; font-size: 12px; background: transparent; }
QLabel#itemDone { color: %(dim)s; font-family: %(font)s; font-size: 12px; background: transparent; }
QLabel#focusEyebrow { color: %(yellow)s; font-size: 10px; font-weight: 600; }
QLabel#focusCtx { color: %(dim)s; font-size: 11px; }
QLabel#focus { color: %(yellow)s; font-weight: 600; font-family: %(font)s; font-size: 14px; background: transparent; }
QLabel#focusDone { color: %(text)s; font-family: %(font)s; font-size: 12px; background: transparent; }
QPushButton { color: %(text)s; background: transparent; border: 1px solid %(border)s;
    border-radius: 8px; padding: 5px 10px; font-family: %(font)s; font-size: 11px; }
QPushButton:hover { border-color: %(accent)s; }
QPushButton#tool { color: %(dim)s; border: 1px solid transparent; border-radius: 7px; padding: 3px 7px; font-size: 12px; }
QPushButton#tool:hover { color: %(text)s; border-color: %(border)s; background: rgba(255, 255, 255, 0.05); }
QPushButton#ghost { color: %(accent)s; border: 1px solid transparent; border-radius: 7px;
    padding: 4px 8px; font-family: %(font)s; font-size: 11px; }
QPushButton#ghost:hover { border-color: %(border)s; background: rgba(255, 255, 255, 0.05); }
QPushButton#lockPill { color: %(dim)s; background: transparent; border: 1px solid %(border)s;
    border-radius: 11px; padding: 3px 10px; font-family: %(font)s; font-size: 11px; }
QPushButton#lockPill:hover { color: %(text)s; border-color: %(dim)s; }
QPushButton#lockPillOn { color: #06121c; background: %(accent)s; border: 1px solid %(accent)s;
    border-radius: 11px; padding: 3px 10px; font-family: %(font)s; font-size: 11px; font-weight: 600; }
QPushButton#star { color: %(dim)s; background: transparent; border: none; padding: 0 2px; font-family: %(font)s; font-size: 13px; }
QPushButton#star:hover { color: %(yellow)s; }
QPushButton#starOn { color: %(yellow)s; background: transparent; border: none; padding: 0 2px; font-family: %(font)s; font-size: 13px; }
QLineEdit { color: %(text)s; background: %(inp)s; border: 1px solid %(border)s;
    border-radius: 8px; padding: 6px 10px; font-family: %(font)s; font-size: 12px; }
QLineEdit:focus { border-color: %(accent)s; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget { background: transparent; }
QCheckBox { background: transparent; spacing: 0px; }
QCheckBox::indicator { width: 17px; height: 17px; border: 1.5px solid %(dim)s; border-radius: 9px; background: transparent; }
QCheckBox::indicator:hover { border-color: %(accent)s; }
QCheckBox::indicator:checked { background: %(success)s; border-color: %(success)s; }
QCheckBox::indicator:unchecked { background: transparent; }
QCheckBox#bigCheck::indicator { width: 22px; height: 22px; border-radius: 11px; border-width: 2px; }
QProgressBar { border: none; border-radius: 6px; background: %(inp)s;
    text-align: center; color: transparent; font-size: 1px; min-height: 12px; max-height: 12px; }
QProgressBar::chunk { background: %(chunk)s; border-radius: 6px; }
QProgressBar#cardBar { border: none; border-radius: 3px; background: %(inp)s; min-height: 6px; max-height: 6px; }
QProgressBar#cardBar::chunk { background: %(chunk)s; border-radius: 3px; }
QSlider::groove:horizontal { height: 4px; background: %(inp)s; border: none; border-radius: 2px; }
QSlider::handle:horizontal { width: 12px; background: %(dim)s; border: none; border-radius: 6px; margin: -5px 0; }
QSlider::handle:horizontal:hover { background: %(accent)s; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: %(border)s; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: %(dim)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSizeGrip { background: transparent; }
QToolTip { color: %(text)s; background: #141b30; border: 1px solid %(border)s; font-family: %(font)s; }
QMenu { background: #141b30; border: 1px solid %(border)s; border-radius: 8px; padding: 4px; }
QMenu::item { color: %(text)s; font-family: %(font)s; font-size: 12px; padding: 7px 14px; border-radius: 5px; }
QMenu::item:selected { background: rgba(67, 200, 245, 0.16); }
""" % {"bg": bg, "pane": pane, "inp": inp, "focusbg": focusbg,
        "chunk": chunk, "accent": ACCENT, "border": BORDER,
        "yellow": FOCUS_YELLOW, "success": SUCCESS,
        "text": TEXT, "dim": DIM, "font": FONT}


QSS = build_qss(0.88)

# Win32: hotkey global + click-through (sem injecao no jogo, so flags da janela)
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
HOTKEY_ID = 9001
FOCUS_HOTKEY_ID = 9002
SW_RESTORE = 9
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x20
WS_EX_LAYERED = 0x80000


class HotkeyFilter(QAbstractNativeEventFilter):
    """Recebe WM_HOTKEY pelo dispatcher do Qt (confiavel).

    O polling com PeekMessageW competia com o proprio loop do Qt, que
    tambem consome mensagens nativas — o F8 parecia "morto" e a janela
    travada nao tinha como destravar. O filtro nao tem essa disputa.
    """

    def __init__(self, overlay):
        super().__init__()
        self._ov = overlay

    def nativeEventFilter(self, eventType, message):
        try:
            et = bytes(eventType)
        except Exception:
            try:
                et = eventType.data()
            except Exception:
                return False, 0
        if b"windows" not in et.lower():
            return False, 0
        try:
            msg = MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                QTimer.singleShot(0, self._ov.toggle_lock)
                return True, 0
            if msg.message == WM_HOTKEY and msg.wParam == FOCUS_HOTKEY_ID:
                QTimer.singleShot(0, self._ov.toggle_overlay_focus)
                return True, 0
        except Exception:
            pass
        return False, 0


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", ctypes.c_void_p),
                ("message", ctypes.c_uint),
                ("wParam", ctypes.c_size_t),
                ("lParam", ctypes.c_size_t),
                ("time", ctypes.c_uint),
                ("pt_x", ctypes.c_long),
                ("pt_y", ctypes.c_long)]


class SectionCard(QWidget):
    """Card clicavel de uma secao no overview (nome + conta + minibarra)."""

    activated = Signal(int)

    def __init__(self, idx, title, parent=None):
        super().__init__(parent)
        self._idx = idx
        self.setObjectName("card")
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)
        txt = QVBoxLayout()
        txt.setContentsMargins(0, 0, 0, 0)
        txt.setSpacing(2)
        self.name = QLabel(title, objectName="cardTitle")
        self.name.setWordWrap(True)
        txt.addWidget(self.name)
        self.count = QLabel("", objectName="cardCount")
        txt.addWidget(self.count)
        lay.addLayout(txt, 1)
        self.bar = QProgressBar(objectName="cardBar")
        self.bar.setFixedWidth(72)
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar, 0, Qt.AlignVCenter)
        self.setToolTip("Abrir: " + title)

    def set_progress(self, done, total):
        self.bar.setValue(int(done * 100 / total) if total else 0)
        pct = int(done * 100 / total) if total else 0
        self.count.setText("%d de %d  •  %d%%" % (done, total, pct))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.activated.emit(self._idx)
            e.accept()
        else:
            super().mousePressEvent(e)


class ChecklistItem(QWidget):
    """Uma missao na lista: check custom + texto com wrap + estrela."""

    def __init__(self, text, checked, indent_px=0, parent=None):
        super().__init__(parent)
        self.setObjectName("item")
        self.setAttribute(Qt.WA_Hover, True)
        hl = QHBoxLayout(self)
        hl.setContentsMargins(indent_px + 8, 7, 8, 7)
        hl.setSpacing(10)
        self.cb = QCheckBox()
        self.cb.setToolTip(text)
        self.cb.setAccessibleName(text)
        self.cb.setChecked(checked)
        self.cb.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        hl.addWidget(self.cb, 0, Qt.AlignTop)
        self.lbl = QLabel(text, objectName="item")
        self.lbl.setWordWrap(True)
        self.lbl.setToolTip(text)
        self.lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.lbl.setCursor(Qt.PointingHandCursor)
        hl.addWidget(self.lbl, 1)
        self.star = QPushButton("☆", objectName="star")
        self.star.setFixedWidth(24)
        self.star.setCursor(Qt.PointingHandCursor)
        self.star.setToolTip("Focar nesta missão")
        hl.addWidget(self.star, 0, Qt.AlignTop)


class Overlay(QWidget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.lines = []
        self.sections = []
        self.checkboxes = []  # (QCheckBox, item, section)
        self.focus_btns = []  # (QPushButton estrela, item, section)
        self.home_page = None
        self.home_rows = []  # SectionCard (tem .name/.count/.bar/.activated)
        self.detail_heads = []  # (titulo_lbl, conta_lbl, sec_index)
        self._sec_idx = None  # secao visivel atual (None = overview)
        self.focus = None  # {"sec": titulo, "text": texto} ou None
        self._saved_size = None  # geometria p/ voltar ao sair do foco
        self._syncing = False  # trava eco checkbox lista <-> cartao
        self._backed_up = False
        self._drag = None
        self._hotkey_ok = False
        self._focus_hotkey_ok = False
        self._game_hwnd = None  # janela do jogo p/ devolver o foco
        self._focus_prev_lock = None  # trava anterior ao "chamar"
        self._capture_which = "lock"
        self._capturing = False
        self._mtime = None
        self._pending = None
        self._rebuilding = False

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(240, 320)
        self.resize(cfg.get("width", 340), cfg.get("height", 480))
        self.setWindowOpacity(1.0)  # janela sempre opaca: o alfa vai so no fundo
        try:
            self._bg_alpha = min(1.0, max(0.15, float(
                cfg.get("opacity", 0.88))))
        except (TypeError, ValueError):
            self._bg_alpha = 0.88
        self.setStyleSheet(build_qss(self._bg_alpha))

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(0)
        frame = QWidget(objectName="root")
        try:
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(28)
            shadow.setOffset(0, 3)
            shadow.setColor(QColor(0, 0, 0, 150))
            frame.setGraphicsEffect(shadow)
        except Exception:
            pass
        root.addWidget(frame)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        # ---- header (arrastar por aqui) ----
        self.titlebar = QWidget()
        tb = QHBoxLayout(self.titlebar)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(8)
        icon = QLabel("◆", objectName="iconMark")
        tb.addWidget(icon)
        self.lbl_title = QLabel("NMS ENDGAME", objectName="appTitle")
        tb.addWidget(self.lbl_title)
        # Um controle so p/ a trava: pill mostra estado + tecla juntos
        # (chip separado de F8 confundia). Clique alterna; a troca da
        # tecla mora no menu ⋯.
        self.btn_lock = QPushButton(objectName="lockPill")
        self.btn_lock.clicked.connect(self.toggle_lock)
        tb.addWidget(self.btn_lock)
        tb.addStretch(1)
        self.btn_menu = QPushButton("⋯", objectName="tool")
        self.btn_menu.setToolTip("Mais opções")
        self.btn_menu.clicked.connect(self._show_menu)
        tb.addWidget(self.btn_menu)
        self._refresh_lock_ui()
        for txt, tip, fn in (("–", "Minimizar", self.showMinimized),
                             ("✕", "Fechar", self.close),):
            b = QPushButton(txt, objectName="tool")
            b.setToolTip(tip)
            b.clicked.connect(fn)
            tb.addWidget(b)
        lay.addWidget(self.titlebar)
        # Drag robusto: filtro direto na barra (+ textos, que nao tem
        # clique proprio). Botoes ficam FORA do filtro e funcionam normal.
        # Nao depende de propagacao ate Overlay.mousePressEvent (que segue
        # como fallback).
        self.titlebar.installEventFilter(self)
        for _w in self.titlebar.findChildren(QLabel):
            _w.installEventFilter(self)

        # ---- dashboard: progresso geral ----
        self.dash = QWidget()
        dh = QHBoxLayout(self.dash)
        dh.setContentsMargins(0, 0, 0, 0)
        dh.setSpacing(12)
        self.lbl_pct = QLabel("0%", objectName="pctBig")
        dh.addWidget(self.lbl_pct)
        dcol = QVBoxLayout()
        dcol.setContentsMargins(0, 0, 0, 0)
        dcol.setSpacing(5)
        self.lbl_total = QLabel("0 de 0 missões", objectName="dashSub")
        dcol.addWidget(self.lbl_total)
        self.bar_total = QProgressBar()
        dcol.addWidget(self.bar_total)
        dh.addLayout(dcol, 1)
        lay.addWidget(self.dash)

        # ---- views: overview (cards) + detalhe por secao ----
        self.views = QStackedWidget()
        self.views.currentChanged.connect(self._on_page_changed)
        lay.addWidget(self.views, 1)

        # ---- rodape: busca + recarregar + transparencia ----
        self.foot = QWidget()
        fr2 = QHBoxLayout(self.foot)
        fr2.setContentsMargins(0, 0, 0, 0)
        fr2.setSpacing(8)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Buscar missão…")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._apply_filter)
        self.filter.returnPressed.connect(self._jump_to_match)
        fr2.addWidget(self.filter, 1)
        self.btn_reload = QPushButton("↻", objectName="tool")
        self.btn_reload.setToolTip("Recarregar do Obsidian")
        self.btn_reload.clicked.connect(self.reload_md)
        fr2.addWidget(self.btn_reload)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(25, 100)
        self.slider.setValue(int(self._bg_alpha * 100))
        self.slider.setFixedWidth(64)
        self.slider.setToolTip(
            "Transparência do fundo (o texto fica sempre legível)")
        self.lbl_alpha = QLabel("", objectName="dim")
        self.lbl_alpha.setFixedWidth(34)
        self.lbl_alpha.setToolTip("Transparência do fundo")
        fr2.addWidget(self.slider)
        fr2.addWidget(self.lbl_alpha)
        self.slider.valueChanged.connect(self._on_alpha_changed)
        self.slider.sliderReleased.connect(self._apply_pending_alpha)
        # Debounce: reaplicar o QSS na janela inteira e caro;
        # sem isso cada tick do arrasto congela a UI.
        self._alpha_timer = QTimer(self)
        self._alpha_timer.setSingleShot(True)
        self._alpha_timer.setInterval(150)
        self._alpha_timer.timeout.connect(self._apply_pending_alpha)
        self._pending_alpha = None
        self.lbl_alpha.setText("%d%%" % int(round(self._bg_alpha * 100)))
        lay.addWidget(self.foot)

        # hint discreta + alca de redimensionar
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        self.hint = QLabel(objectName="dim")
        self.hint.setWordWrap(True)
        bottom.addWidget(self.hint, 1)
        self.grip = QSizeGrip(frame)
        self.grip.setToolTip("Arrastar p/ redimensionar")
        bottom.addWidget(self.grip, 0, Qt.AlignBottom | Qt.AlignRight)
        lay.addLayout(bottom)

        # ---- cartao de foco: "objetivo atual" (compacto p/ o jogo) ----
        self.focus_card = QWidget(objectName="focusCard")
        fc = QVBoxLayout(self.focus_card)
        fc.setContentsMargins(14, 12, 14, 12)
        fc.setSpacing(8)
        self.focus_eyebrow = QLabel("◆ OBJETIVO ATUAL", objectName="focusEyebrow")
        fc.addWidget(self.focus_eyebrow)
        self.focus_lbl = QLabel("", objectName="focus")
        self.focus_lbl.setWordWrap(True)
        self.focus_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        fc.addWidget(self.focus_lbl)
        self.focus_sec = QLabel("", objectName="dim")
        self.focus_sec.setWordWrap(True)
        fc.addWidget(self.focus_sec)
        self.focus_ctx = QLabel("", objectName="focusCtx")
        fc.addWidget(self.focus_ctx)
        frow = QHBoxLayout()
        frow.setContentsMargins(0, 0, 0, 0)
        frow.setSpacing(8)
        self.focus_cb = QCheckBox(objectName="bigCheck")
        self.focus_cb.setToolTip("Marcar como concluída")
        self.focus_cb.toggled.connect(self._on_focus_card_toggled)
        frow.addWidget(self.focus_cb, 0, Qt.AlignVCenter)
        self.focus_done_lbl = QLabel("Marcar como concluída",
                                     objectName="focusDone")
        self.focus_done_lbl.setCursor(Qt.PointingHandCursor)
        self.focus_done_lbl.mousePressEvent = (
            lambda _e: self.focus_cb.toggle())
        frow.addWidget(self.focus_done_lbl, 0, Qt.AlignVCenter)
        frow.addStretch(1)
        self.btn_unfocus = QPushButton("Sair do foco", objectName="ghost")
        self.btn_unfocus.setToolTip("Voltar para a lista")
        self.btn_unfocus.clicked.connect(self.unfocus)
        frow.addWidget(self.btn_unfocus)
        fc.addLayout(frow)
        self.focus_card.setVisible(False)
        lay.insertWidget(1, self.focus_card)
        self._set_hint()

        if not self.load_md(cfg.get("md_path", DEFAULT_MD)):
            self._pick_file()
        self._place_bottom_right()
        self._register_hotkey()
        self._register_focus_hotkey()
        # filtro nativo do Qt: recebe WM_HOTKEY sem disputar PeekMessage
        # com o loop do Qt (o polling antigo perdia a tecla e a janela
        # travada nao destravava mais). Guarda a ref p/ nao ser coletado.
        self._native_filter = HotkeyFilter(self)
        try:
            QApplication.instance().installNativeEventFilter(
                self._native_filter)
        except Exception:
            pass
        self._apply_lock(initial=True)
        self._restore_view()
        self._restore_focus()
        # Vigia anti-trava: se a hotkey morrer com a janela TRAVADA
        # (ex.: outro programa roubou o registro), readquire; se nao
        # der, _apply_lock destrava sozinho com aviso. Nunca prende.
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(15000)
        self._watch_timer.timeout.connect(self._watch_hotkey)
        self._watch_timer.start()

    # ------------------------------------------------------------- dados ---
    def load_md(self, path):
        if not path or not os.path.isfile(path):
            return False
        had_views = self.views.count() > 0
        keep_home = self._sec_idx is None
        keep_title = None
        if not keep_home and 0 <= self._sec_idx < len(self.sections):
            keep_title = self.sections[self._sec_idx]["titulo"]
        try:
            self.lines, self.sections = parse_markdown(path)
        except OSError as e:
            QMessageBox.warning(self, "NMS Overlay", "Nao abri o .md:\n%s" % e)
            return False
        if not self.sections:
            QMessageBox.warning(self, "NMS Overlay",
                                "Nenhuma secao '## ' encontrada no arquivo.")
            return False
        self.cfg["md_path"] = path
        try:
            self._mtime = os.path.getmtime(path)
        except OSError:
            self._mtime = None
        self._build_views()
        if had_views:
            # reload (botao ou troca de arquivo): mantem onde estava
            if keep_home:
                self.show_home()
            else:
                for idx, s in enumerate(self.sections):
                    if s["titulo"] == keep_title:
                        self.show_section(idx)
                        break
                else:
                    self.show_home()
        # primeira carga: nao toca na navegacao; _restore_view() do
        # __init__ aplica a view salva no config (overview por padrao)
        self._refresh_bars()
        return True

    def reload_md(self):
        self._backed_up = False
        if self.load_md(self.cfg.get("md_path")):
            self._set_hint("Recarregado do Obsidian.")

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir checklist do Obsidian", os.path.expanduser("~"),
            "Markdown (*.md)")
        if path:
            self.load_md(path)
        else:
            self.lines, self.sections = [], [
                {"titulo": "sem arquivo", "blocos": []}]
            self._build_views()
            self.show_home()

    def _refresh_item_label(self, lbl, checked, focused=False):
        lbl.setObjectName("focus" if focused else (
            "itemDone" if checked else "item"))
        # repolish p/ trocar a cor do QSS sem recriar o widget
        try:
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)
        except Exception:
            pass

    # --------------------------------------------------------------- foco ---
    def _is_focused(self, sec_title, text):
        f = self.focus
        return bool(f) and f.get("sec") == sec_title and f.get("text") == text

    def _find_focus_widgets(self):
        """Acha (item, sec, cb, lbl) do foco atual; tudo None se sumiu."""
        if not self.focus:
            return None, None, None, None
        for cb, payload, sec in self.checkboxes:
            if (sec["titulo"] == self.focus.get("sec")
                    and payload["text"] == self.focus.get("text")):
                lbl = None
                try:
                    lbs = cb.parent().findChildren(QLabel)
                    lbl = lbs[0] if lbs else None
                except Exception:
                    lbl = None
                return payload, sec, cb, lbl
        return None, None, None, None

    def toggle_focus(self, sec_title, text):
        if self._is_focused(sec_title, text):
            self.unfocus()
            return
        self.focus = {"sec": sec_title, "text": text}
        self.cfg["focus"] = dict(self.focus)
        save_config(self.cfg)
        self._refresh_focus_ui()

    def unfocus(self):
        if not self.focus and self.focus_card.isHidden():
            return
        self.focus = None
        self.cfg["focus"] = None
        save_config(self.cfg)
        self._refresh_focus_ui()

    def _restore_focus(self):
        f = self.cfg.get("focus")
        if isinstance(f, dict) and f.get("sec") and f.get("text") is not None:
            self.focus = {"sec": f["sec"], "text": f["text"]}
        else:
            self.focus = None
        self._refresh_focus_ui()

    def _refresh_focus_ui(self):
        for b, p, s in getattr(self, "focus_btns", []):
            on = self._is_focused(s["titulo"], p["text"])
            b.setText("★" if on else "☆")
            b.setObjectName("starOn" if on else "star")
            try:
                b.style().unpolish(b)
                b.style().polish(b)
            except Exception:
                pass
            try:
                lbs = b.parent().findChildren(QLabel)
                if lbs:
                    self._refresh_item_label(lbs[0], p["checked"], on)
            except Exception:
                pass
        item, sec, cb, lbl = self._find_focus_widgets()
        if item is None:
            if self.focus is not None:
                # missao sumiu do .md: sai do foco em silencio
                self.focus = None
                self.cfg["focus"] = None
                save_config(self.cfg)
            self.focus_card.setVisible(False)
            for w in (self.dash, self.views, self.foot, self.hint):
                w.setVisible(True)
            if self._saved_size is not None:
                self.resize(self._saved_size)
                self._saved_size = None
            return
        if self._saved_size is None:
            self._saved_size = self.size()
        self.focus_sec.setText(sec["titulo"])
        self.focus_lbl.setText(item["text"])
        self.focus_lbl.setToolTip(item["text"])
        done_s, total_s = section_progress(sec)
        self.focus_ctx.setText("%d de %d nesta seção" % (done_s, total_s))
        self.focus_cb.blockSignals(True)
        self.focus_cb.setChecked(item["checked"])
        self.focus_cb.setToolTip(item["text"])
        self.focus_cb.blockSignals(False)
        for w in (self.dash, self.views, self.foot, self.hint):
            w.setVisible(False)
        self.focus_card.setVisible(True)
        self._fade_in(self.focus_card)
        self.adjustSize()
        if self.width() < 260:
            self.resize(260, self.height())

    def _on_list_toggled(self, on, item, sec, lbl):
        self._on_toggle(on, item, sec)
        focused = self._is_focused(sec["titulo"], item["text"])
        self._refresh_item_label(lbl, on, focused)
        if focused and not self._syncing:
            self.focus_cb.blockSignals(True)
            self.focus_cb.setChecked(bool(on))
            self.focus_cb.blockSignals(False)

    def _on_focus_card_toggled(self, on):
        if self._syncing or not self.focus:
            return
        item, sec, cb, lbl = self._find_focus_widgets()
        if item is None or cb is None:
            return
        self._syncing = True
        try:
            if cb.isChecked() != bool(on):
                cb.setChecked(bool(on))  # dispara o save normal da lista
            else:
                self._on_toggle(bool(on), item, sec)
            if lbl is not None:
                self._refresh_item_label(lbl, bool(on), True)
        finally:
            self._syncing = False

    def _build_views(self):
        self._rebuilding = True
        try:
            while self.views.count():
                w = self.views.widget(0)
                self.views.removeWidget(w)
                w.deleteLater()
            self.checkboxes = []
            self.focus_btns = []
            self.detail_heads = []
            for idx, sec in enumerate(self.sections):
                page = self._build_detail_page(idx, sec)
                self.views.addWidget(page)
            self._build_home_page()
        finally:
            self._rebuilding = False
        self._refresh_focus_ui()

    def _build_detail_page(self, idx, sec):
        page = QWidget(objectName="page")
        vl = QVBoxLayout(page)
        vl.setContentsMargins(2, 2, 2, 2)
        vl.setSpacing(8)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        back = QPushButton("‹ Início", objectName="ghost")
        back.setToolTip("Voltar para a visão geral")
        back.clicked.connect(self.show_home)
        head.addWidget(back)
        title = QLabel(sec["titulo"], objectName="secTitleBig")
        title.setWordWrap(True)
        head.addWidget(title, 1)
        count = QLabel("", objectName="dim")
        head.addWidget(count, 0, Qt.AlignVCenter)
        vl.addLayout(head)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # SEMPRE visivel: com AsNeeded, aparecer/sumir muda a largura
        # do viewport em 8px -> requebra todas as labels (word-wrap) ->
        # o range muda e a posicao pula sozinha ("volta"), com relayout
        # full a cada flip ("trava"). Geometria constante mata o loop.
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        inner = QWidget(objectName="inner")
        il = QVBoxLayout(inner)
        il.setContentsMargins(6, 6, 6, 6)
        il.setSpacing(3)
        for kind, payload in sec["blocos"]:
            if kind == "sub":
                lbl_sub = QLabel("◆ " + payload, objectName="sub")
                lbl_sub.setWordWrap(True)
                il.addWidget(lbl_sub)
            else:
                row = ChecklistItem(payload["text"],
                                    payload["checked"],
                                    len(payload["indent"]) * 8)
                self._refresh_item_label(
                    row.lbl, payload["checked"],
                    self._is_focused(sec["titulo"], payload["text"]))
                row.cb.toggled.connect(
                    lambda on, it=payload, s=sec, l=row.lbl:
                    self._on_list_toggled(on, it, s, l))
                # clicar no texto marca/desmarca (facilita no jogo)
                row.lbl.mousePressEvent = (
                    lambda _e, _cb=row.cb: _cb.toggle())
                row.star.setToolTip("Focar nesta missão")
                row.star.clicked.connect(
                    lambda _c=False, t=sec["titulo"], x=payload["text"]:
                    self.toggle_focus(t, x))
                il.addWidget(row)
                self.checkboxes.append((row.cb, payload, sec))
                self.focus_btns.append((row.star, payload, sec))
        il.addStretch(1)
        scroll.setWidget(inner)
        vl.addWidget(scroll)
        self.detail_heads.append((title, count, idx))
        return page

    def _build_home_page(self):
        """Overview: cards clicaveis das secoes (nome + conta + barra)."""
        home = QWidget(objectName="page")
        hvl = QVBoxLayout(home)
        hvl.setContentsMargins(2, 2, 2, 2)
        hvl.setSpacing(8)
        eyebrow = QLabel("VISÃO GERAL", objectName="eyebrow")
        hvl.addWidget(eyebrow)
        hscroll = QScrollArea()
        hscroll.setWidgetResizable(True)
        hscroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        hscroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        hinner = QWidget(objectName="inner")
        hil = QVBoxLayout(hinner)
        hil.setContentsMargins(2, 2, 2, 2)
        hil.setSpacing(8)
        self.home_rows = []
        for idx, sec in enumerate(self.sections):
            card = SectionCard(idx, sec["titulo"])
            card.activated.connect(self.show_section)
            hil.addWidget(card)
            self.home_rows.append(card)
        hil.addStretch(1)
        hscroll.setWidget(hinner)
        hvl.addWidget(hscroll)
        self.home_page = home
        self.views.addWidget(home)

    # ---------------------------------------------------------- navegacao ---
    def _home_index(self):
        return len(self.sections)

    def _show_page(self, idx, _from_signal=False):
        n = self.views.count()
        if not n:
            return
        idx = max(0, min(int(idx), n - 1))
        if not _from_signal and self.views.currentIndex() != idx:
            self.views.setCurrentIndex(idx)  # volta via _on_page_changed
            return
        self._sec_idx = idx if idx < len(self.sections) else None
        new_view = {"home": self._sec_idx is None,
                    "sec": self._sec_idx or 0}
        if self.cfg.get("view") != new_view:
            self.cfg["view"] = new_view
            save_config(self.cfg)
        self._apply_filter(self.filter.text())
        self._fade_in(self.views.widget(idx))

    def show_home(self, _c=False):
        self._show_page(self._home_index())

    def show_section(self, idx):
        self._show_page(idx)

    def _on_page_changed(self, i):
        if getattr(self, "_rebuilding", False):
            return
        self._show_page(i, _from_signal=True)

    def _restore_view(self):
        v = self.cfg.get("view") or {}
        if v.get("home", True) or not self.sections:
            self._show_page(self._home_index())
        else:
            try:
                sec = int(v.get("sec", 0))
            except (TypeError, ValueError):
                sec = 0
            self._show_page(max(0, min(sec, len(self.sections) - 1)))

    def _fade_in(self, w, ms=140):
        """Transicao sutil de entrada (falha silenciosa = sem animacao)."""
        if w is None:
            return
        try:
            try:
                w.setGraphicsEffect(None)  # descarta fade anterior
            except RuntimeError:
                pass
            eff = QGraphicsOpacityEffect(w)
            w.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", self)
            anim.setDuration(ms)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)

            def _done():
                try:
                    if w.graphicsEffect() is eff:
                        w.setGraphicsEffect(None)
                except RuntimeError:
                    pass
                try:
                    eff.deleteLater()
                except RuntimeError:
                    pass

            anim.finished.connect(_done)
            anim.start(QAbstractAnimation.DeleteWhenStopped)
        except Exception:
            try:
                w.setGraphicsEffect(None)
            except Exception:
                pass

    def _menu_actions(self):
        """(texto, slot) do menu ⋯ — separado p/ ser testavel sem popup."""
        return [
            ("Recarregar do Obsidian", self.reload_md),
            ("Trocar tecla de trava (atual: %s)" % self.cfg.get(
                "hotkey_name", "F8"), self._start_hotkey_capture),
            ("Trocar tecla de foco (atual: %s)" % self.cfg.get(
                "focus_hotkey_name", "F9"),
             lambda: self._start_hotkey_capture("focus")),
            ("Redefinir posição e tamanho", self._reset_geometry),
            ("Abrir pasta do checklist", self._open_md_folder),
        ]

    def _show_menu(self):
        try:
            menu = QMenu(self)
            for text, slot in self._menu_actions():
                menu.addAction(text).triggered.connect(slot)
            menu.exec(self.btn_menu.mapToGlobal(
                QPoint(0, self.btn_menu.height())))
        except Exception:
            pass

    def _reset_geometry(self):
        self.cfg["x"] = None
        self.cfg["y"] = None
        self.resize(340, 480)
        self._place_bottom_right()
        save_config(self.cfg)
        self._set_hint("Posição e tamanho redefinidos.")

    def _open_md_folder(self):
        try:
            folder = os.path.dirname(
                os.path.abspath(self.cfg.get("md_path", "")))
            if os.path.isdir(folder):
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
                return
        except Exception:
            pass
        self._set_hint("Pasta do checklist não encontrada.")

    # ---------------------------------------------------------- interacao ---
    def _hint_base(self):
        return "%s trava • %s chama • ★ foca • Enter busca • Esc limpa" % (
            self.cfg.get("hotkey_name", "F8"),
            self.cfg.get("focus_hotkey_name", "F9"))

    def _set_hint(self, msg=None):
        self.hint.setText(msg if msg else self._hint_base())

    def _on_toggle(self, on, item, sec):
        item["checked"] = bool(on)
        if self._disk_changed():
            # o .md mudou por fora (Obsidian): mescla fora do handler do sinal
            self._pending = (sec["titulo"], item["text"], bool(on))
            QTimer.singleShot(0, self._do_external_reload)
        else:
            set_line_checked(self.lines, item["line"], on)
            self._save_md()
        self._refresh_bars()

    def _disk_changed(self):
        path = self.cfg.get("md_path")
        if not path or self._mtime is None:
            return False
        try:
            return os.path.getmtime(path) != self._mtime
        except OSError:
            return False

    def _do_external_reload(self):
        pending = self._pending
        self._pending = None
        cur_title = None
        was_home = self._sec_idx is None
        if (self._sec_idx is not None
                and 0 <= self._sec_idx < len(self.sections)):
            cur_title = self.sections[self._sec_idx]["titulo"]
        path = self.cfg.get("md_path")
        try:
            self.lines, self.sections = parse_markdown(path)
            self._mtime = os.path.getmtime(path)
        except OSError:
            return
        if pending:
            title, text, on = pending
            for s in self.sections:
                if s["titulo"] == title:
                    for kind, payload in s["blocos"]:
                        if kind == "item" and payload["text"] == text:
                            payload["checked"] = on
                            set_line_checked(self.lines, payload["line"], on)
                            break
                    break
            cur_title = title
        self._build_views()
        if was_home and not pending:
            self.show_home()
        else:
            for idx, s in enumerate(self.sections):
                if s["titulo"] == cur_title:
                    self.show_section(idx)
                    break
            else:
                self.show_home()
        self._save_md(silent=True)
        self._refresh_bars()
        if pending:
            self._set_hint("Mudou no Obsidian; mesclado e salvo.")

    def _save_md(self, silent=False):
        path = self.cfg.get("md_path")
        if not path:
            return
        try:
            if not self._backed_up:
                shutil.copyfile(path, path + ".bak")
                self._backed_up = True
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(self.lines)
            self._mtime = os.path.getmtime(path)
            if not silent:
                self._set_hint("Salvo no Obsidian.")
        except OSError as e:
            self._set_hint("Erro ao salvar: %s" % e)

    def _refresh_bars(self):
        done = sum(1 for _, it, _ in self.checkboxes if it["checked"])
        total = len(self.checkboxes)
        pct = int(done * 100 / total) if total else 0
        self.bar_total.setValue(pct)
        self.lbl_pct.setText("%d%%" % pct)
        self.lbl_total.setText("%d de %d missões" % (done, total))
        for idx, s in enumerate(self.sections):
            d, t = section_progress(s)
            if 0 <= idx < len(self.detail_heads):
                try:
                    _tl, cc, _i = self.detail_heads[idx]
                    cc.setText("%d/%d" % (d, t))
                except RuntimeError:
                    pass  # pagina antiga durante rebuild
            if 0 <= idx < len(self.home_rows):
                try:
                    self.home_rows[idx].set_progress(d, t)
                except RuntimeError:
                    pass

    def _secs_with_matches(self, q):
        hits = []
        for idx, s in enumerate(self.sections):
            if any(b[0] == "item" and q in b[1]["text"].lower()
                   for b in s["blocos"]):
                hits.append(idx)
        return hits

    def _jump_to_match(self):
        q = self.filter.text().strip().lower()
        if not q:
            return
        hits = self._secs_with_matches(q)
        if not hits:
            self._set_hint("Nada encontrado p/ '%s'." % q)
            return
        cur = self.views.currentIndex()
        if cur >= len(self.sections):
            cur = -1  # do overview, vai para o primeiro resultado
        nxt = next((h for h in hits if h > cur), hits[0])
        self.show_section(nxt)

    def _apply_filter(self, text):
        q = (text or "").strip().lower()
        cur = self.views.currentWidget()
        if (cur is not None and getattr(self, "home_page", None) is not None
                and cur is self.home_page):
            for card in self.home_rows:
                try:
                    card.setVisible(
                        not q or q in card.name.text().lower())
                except RuntimeError:
                    pass
        elif cur is not None:
            for cb in cur.findChildren(QCheckBox):
                # texto completo fica no toolTip (checkbox agora sem texto,
                # o visivel e o QLabel com word-wrap da mesma linha)
                try:
                    full = (cb.toolTip() or cb.text()
                            or cb.accessibleName() or "")
                except Exception:
                    full = ""
                vis = (not q) or (q in full.lower())
                parent = cb.parent()
                try:
                    if (parent is not None
                            and parent.objectName() == "item"):
                        parent.setVisible(vis)
                    else:
                        cb.setVisible(vis)
                except Exception:
                    cb.setVisible(vis)
        if not q:
            self._set_hint()
            return
        n_items = sum(1 for _, it, _ in self.checkboxes
                      if q in it["text"].lower())
        n_secs = len(self._secs_with_matches(q))
        self._set_hint("%d resultados em %d seções • Enter vai" % (
            n_items, n_secs))

    def _on_alpha_changed(self, v):
        self._bg_alpha = min(1.0, max(0.15, v / 100.0))
        self.cfg["opacity"] = round(self._bg_alpha, 2)
        self.lbl_alpha.setText("%d%%" % int(round(self._bg_alpha * 100)))
        # so agenda: o repolish full roda 1x ao soltar / apos 150ms parado
        self._pending_alpha = self._bg_alpha
        if not self._alpha_timer.isActive():
            self._alpha_timer.start()

    def _apply_pending_alpha(self):
        if self._pending_alpha is None:
            return
        a, self._pending_alpha = self._pending_alpha, None
        if self._alpha_timer.isActive():
            self._alpha_timer.stop()
        self.setStyleSheet(build_qss(a))

    # ------------------------------------------------------------ overlay ---
    def _place_bottom_right(self):
        x, y = self.cfg.get("x"), self.cfg.get("y")
        if isinstance(x, int) and isinstance(y, int):
            self.move(x, y)
            return
        scr = QApplication.primaryScreen().availableGeometry()
        m = 14
        self.move(scr.right() - self.width() - m,
                  scr.bottom() - self.height() - m)

    def _hwnd(self):
        return int(self.winId())

    def _set_click_through(self, on):
        try:
            u32 = ctypes.windll.user32
            hwnd = self._hwnd()
            ex = u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if on:
                u32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE,
                    ex | WS_EX_TRANSPARENT | WS_EX_LAYERED)
            else:
                u32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE, ex & ~WS_EX_TRANSPARENT)
        except (AttributeError, OSError):
            pass

    def toggle_lock(self):
        will_lock = not self.cfg.get("locked", False)
        if will_lock and not self._hotkey_ok:
            # tenta de novo antes de prender o mouse fora da janela.
            # Sem modal: em jogo o popup ficaria escondido e no teste
            # ele travaria tudo; so o hint ja informa.
            self._register_hotkey()
            if not self._hotkey_ok:
                self._set_hint(
                    "Hotkey %s indisponivel (em uso?). Sem ela nao da "
                    "p/ destravar, entao nao travei." % self.cfg.get(
                        "hotkey_name", "F8"))
                return
        self.cfg["locked"] = will_lock
        self._apply_lock()

    def toggle_overlay_focus(self):
        """Tecla de foco: chama o overlay p/ frente sem alt-tab.

        1o aperto: guarda a janela atual (o jogo), destrava os cliques
        e traz o overlay p/ o 1o plano. 2o aperto: restaura a trava
        anterior e devolve o foco ao jogo.
        """
        try:
            u32 = ctypes.windll.user32
            hwnd = self._hwnd()
            fg = u32.GetForegroundWindow()
        except (AttributeError, OSError):
            u32, hwnd, fg = None, None, None
        if hwnd is not None and fg == hwnd:
            # dispensar: volta a trava anterior e o foco ao jogo
            if self._focus_prev_lock is not None:
                self.cfg["locked"] = self._focus_prev_lock
                self._focus_prev_lock = None
                self._apply_lock()
            if u32 is not None and self._game_hwnd:
                try:
                    u32.SetForegroundWindow(self._game_hwnd)
                except (AttributeError, OSError):
                    pass
            self._set_hint()
            return
        # chamar: guarda o jogo, destrava e traz p/ frente
        if u32 is not None:
            self._game_hwnd = fg
        self._focus_prev_lock = bool(self.cfg.get("locked", False))
        if self.cfg.get("locked", False):
            self.cfg["locked"] = False
            self._apply_lock()
        try:
            if self.isMinimized():
                self.showNormal()
        except Exception:
            pass
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass
        if u32 is not None and hwnd is not None:
            try:
                if u32.IsIconic(hwnd):
                    u32.ShowWindow(hwnd, SW_RESTORE)
                u32.SetForegroundWindow(hwnd)
            except (AttributeError, OSError):
                pass
        self._set_hint("Overlay chamado; %s devolve o foco ao jogo." %
                       self.cfg.get("focus_hotkey_name", "F9"))

    def _watch_hotkey(self):
        # a tecla de foco nao prende ninguem: so readquire em silencio.
        if not self._focus_hotkey_ok:
            try:
                vk = int(self.cfg.get("focus_hotkey_vk", 0x79))
                if ctypes.windll.user32.RegisterHotKey(
                        None, FOCUS_HOTKEY_ID, MOD_NOREPEAT, vk):
                    self._focus_hotkey_ok = True
            except (AttributeError, OSError, ValueError):
                pass
        if not self.cfg.get("locked", False):
            return
        if not self._hotkey_ok:
            self._apply_lock()  # destrava sozinho com aviso
            return
        # Sonda sem perturbar: se ainda registrada (saudavel), o Windows
        # recusa (0) e nada muda; se morreu em silencio, readquire.
        try:
            vk = int(self.cfg.get("hotkey_vk", 0x77))
            if ctypes.windll.user32.RegisterHotKey(
                    None, HOTKEY_ID, MOD_NOREPEAT, vk):
                self._hotkey_ok = True
        except (AttributeError, OSError, ValueError):
            pass

    def _apply_lock(self, initial=False):
        locked = self.cfg.get("locked", False)
        if locked and not self._hotkey_ok:
            # anti-deadlock: sem hotkey global nao ha como destravar,
            # pois os cliques atravessam a janela. Forca destravado
            # (vale p/ inicializacao com locked:true salvo no config).
            locked = False
            self.cfg["locked"] = False
            self._set_hint(
                "Hotkey %s falhou; mantido destravado p/ nao prender." %
                self.cfg.get("hotkey_name", "F8"))
        self._set_click_through(locked)
        self._refresh_lock_ui()
        if not initial:
            save_config(self.cfg)

    def _refresh_lock_ui(self):
        locked = bool(self.cfg.get("locked", False))
        key = self.cfg.get("hotkey_name", "F8")
        self.btn_lock.setText(
            ("● Travado · " if locked else "○ Livre · ") + key)
        self.btn_lock.setObjectName("lockPillOn" if locked else "lockPill")
        self.btn_lock.setToolTip(
            "Clique para %s (ou pressione %s no jogo)" % (
                "destravar" if locked else "travar", key))
        try:
            self.btn_lock.style().unpolish(self.btn_lock)
            self.btn_lock.style().polish(self.btn_lock)
        except Exception:
            pass

    def _register_hotkey(self):
        self._unregister_hotkey()
        # libera ID do thread antes de registrar (outra instancia/teste
        # pode ter deixado registrado); ignora erro se nao havia nada.
        try:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        except (AttributeError, OSError):
            pass
        try:
            vk = int(self.cfg.get("hotkey_vk", 0x77))
            if ctypes.windll.user32.RegisterHotKey(
                    None, HOTKEY_ID, MOD_NOREPEAT, vk):
                self._hotkey_ok = True
                return
            try:
                err = ctypes.get_last_error()
            except Exception:
                err = "?"
            self._hotkey_ok = False
            self._set_hint(
                "Hotkey %s indisponivel (erro %s); use o botao TRAVAR "
                "so depois de trocar a tecla." % (
                    self.cfg.get("hotkey_name", "F8"), err))
            return
        except (AttributeError, OSError, ValueError):
            pass
        self._hotkey_ok = False
        self._set_hint("Hotkey %s indisponivel; troque a tecla."
                       % self.cfg.get("hotkey_name", "F8"))

    def _unregister_hotkey(self):
        if self._hotkey_ok:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            except (AttributeError, OSError):
                pass
            self._hotkey_ok = False

    def _register_focus_hotkey(self):
        self._unregister_focus_hotkey()
        try:
            ctypes.windll.user32.UnregisterHotKey(None, FOCUS_HOTKEY_ID)
        except (AttributeError, OSError):
            pass
        try:
            vk = int(self.cfg.get("focus_hotkey_vk", 0x79))
            if ctypes.windll.user32.RegisterHotKey(
                    None, FOCUS_HOTKEY_ID, MOD_NOREPEAT, vk):
                self._focus_hotkey_ok = True
                return
        except (AttributeError, OSError, ValueError):
            pass
        self._focus_hotkey_ok = False
        # sem panico: sem a tecla de foco o overlay segue usavel
        # (so o alt-tab manual); nao mexe na trava.

    def _unregister_focus_hotkey(self):
        if self._focus_hotkey_ok:
            try:
                ctypes.windll.user32.UnregisterHotKey(
                    None, FOCUS_HOTKEY_ID)
            except (AttributeError, OSError):
                pass
            self._focus_hotkey_ok = False

    def _start_hotkey_capture(self, which="lock"):
        if self.cfg.get("locked"):
            self.toggle_lock()  # precisa estar destravado p/ clicar
        self._capture_which = which if which == "focus" else "lock"
        self._capturing = True
        what = ("foco (chamar o overlay)"
                if self._capture_which == "focus" else "trava")
        self._set_hint("Pressione a nova tecla de %s (Esc cancela)..." % what)
        self.grabKeyboard()
        QTimer.singleShot(8000, self._cancel_capture)

    def _cancel_capture(self):
        if not self._capturing:
            return
        self._capturing = False
        try:
            self.releaseKeyboard()
        except Exception:
            pass
        self._set_hint()

    def keyPressEvent(self, e):
        if self._capturing:
            self._capturing = False
            try:
                self.releaseKeyboard()
            except Exception:
                pass
            if int(e.key()) != int(Qt.Key_Escape):
                mapped = qt_key_to_vk(e.key())
                if mapped:
                    vk, name = mapped
                    if self._capture_which == "focus":
                        self._unregister_focus_hotkey()
                        self.cfg["focus_hotkey_vk"] = vk
                        self.cfg["focus_hotkey_name"] = name
                        save_config(self.cfg)
                        self._register_focus_hotkey()
                        if self._focus_hotkey_ok:
                            self._set_hint("Tecla de foco agora é: %s" % name)
                        else:
                            self._set_hint(
                                "Tecla %s indisponivel p/ foco; "
                                "tente outra." % name)
                        return
                    self._unregister_hotkey()
                    self.cfg["hotkey_vk"] = vk
                    self.cfg["hotkey_name"] = name
                    save_config(self.cfg)
                    self._register_hotkey()
                    self._refresh_lock_ui()
                    if self._hotkey_ok:
                        self._set_hint("Tecla de trava agora é: %s" % name)
                    return
            self._refresh_lock_ui()
            self._set_hint()
            return
        if int(e.key()) == int(Qt.Key_Escape) and self.filter.text():
            self.filter.clear()
            return
        super().keyPressEvent(e)

    def _poll_hotkey(self):
        # Legado: mantido p/ compat, mas NAO e mais usado. O HotkeyFilter
        # recebe WM_HOTKEY pelo dispatcher do Qt; o polling com PeekMessage
        # disputava a mensagem com o proprio Qt e o F8 parecia morto.
        if not self._hotkey_ok:
            return
        try:
            msg = MSG()
            while ctypes.windll.user32.PeekMessageW(
                    ctypes.byref(msg), None, WM_HOTKEY, WM_HOTKEY, 1):
                if msg.wParam == HOTKEY_ID:
                    self.toggle_lock()
        except (AttributeError, OSError):
            pass

    @staticmethod
    def _global_pos(e):
        try:
            return e.globalPosition().toPoint()
        except Exception:
            return e.globalPos()

    def eventFilter(self, obj, e):
        # Arrastar pela barra: resolve AQUI, antes da entrega. So a barra
        # e seus textos entram; botoes nunca recebem este filtro.
        try:
            mine = (obj is self.titlebar or (
                isinstance(obj, QLabel) and obj.parent() is self.titlebar))
        except RuntimeError:
            return False
        if not mine:
            return super().eventFilter(obj, e)
        t = e.type()
        try:
            if t == QEvent.MouseButtonPress:
                if e.button() == Qt.LeftButton:
                    self._drag = (self._global_pos(e)
                                  - self.frameGeometry().topLeft())
                    return True
                return False
            if t == QEvent.MouseMove:
                if (self._drag is not None
                        and e.buttons() & Qt.LeftButton):
                    self.move(self._global_pos(e) - self._drag)
                    return True
                return False
            if t == QEvent.MouseButtonRelease:
                if (self._drag is not None
                        and e.button() == Qt.LeftButton):
                    self._drag = None
                    return True
                return False
        except (AttributeError, RuntimeError, TypeError):
            return False
        return super().eventFilter(obj, e)

    # arrastar pela barra de titulo (so funciona destravado, claro)
    def mousePressEvent(self, e):
        try:
            # mapFrom devolve coord. LOCAL da barra; comparar com rect(),
            # nao com geometry() (que e relativo ao pai e quase nunca casa).
            in_bar = self.titlebar.rect().contains(
                self.titlebar.mapFrom(self, e.pos()))
        except Exception:
            in_bar = False
        if e.button() == Qt.LeftButton and in_bar:
            self._drag = self._global_pos(e) - self.frameGeometry().topLeft()
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(self._global_pos(e) - self._drag)
            e.accept()
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag = None
        super().mouseReleaseEvent(e)

    def closeEvent(self, e):
        try:
            QApplication.instance().removeNativeEventFilter(
                self._native_filter)
        except Exception:
            pass
        self._unregister_hotkey()
        self._unregister_focus_hotkey()
        self.cfg["opacity"] = round(getattr(self, "_bg_alpha", 0.88), 2)
        self.cfg["width"] = self.width()
        self.cfg["height"] = self.height()
        self.cfg["x"] = self.x()
        self.cfg["y"] = self.y()
        _sec = getattr(self, "_sec_idx", None)
        self.cfg["view"] = {"home": _sec is None, "sec": _sec or 0}
        save_config(self.cfg)
        super().closeEvent(e)
        # Saida explicita: janela e Qt.Tool e o Qt limpa WA_QuitOnClose
        # em tool windows, entao fechar "a ultima janela" NAO encerra o
        # exec() sozinho e o pythonw ficava preso em segundo plano.
        try:
            inst = QApplication.instance()
            if inst is not None:
                inst.quit()
        except Exception:
            pass


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    ov = Overlay(load_config())
    ov.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
