"""Teste headless do overlay (nao abre janela visivel)."""
import os
import re
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nms_overlay  # noqa: E402
from nms_overlay import Overlay, qt_key_to_vk, section_progress  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

# nao sujar o config real do usuario durante o teste
nms_overlay.save_config = lambda cfg: None

# usa o checklist EMBUTIDO no projeto (checklist/); nunca o vault pessoal
CHECKLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "checklist", "nms-endgame-checklist.md")

tmp = tempfile.mkdtemp(prefix="nms_ov_test_")
md_copy = os.path.join(tmp, "check.md")
shutil.copyfile(CHECKLIST, md_copy)
# deterministico: zera qualquer progresso que a copia embutida tiver
with open(md_copy, encoding="utf-8") as f:
    _c = f.read()
assert "corveta" in _c.lower(), "checklist embutido sem o termo de busca"
with open(md_copy, "w", encoding="utf-8") as f:
    f.write(re.sub(r"(?m)^(\s*)- \[x\]", r"\1- [ ]", _c))


def fresh_cfg(**kw):
    cfg = {"md_path": md_copy, "opacity": 1.0, "width": 340,
           "height": 480, "locked": False,
           "hotkey_vk": 0x77, "hotkey_name": "F8", "x": None, "y": None}
    cfg.update(kw)
    return cfg


app = QApplication([])

# --- teste 1: posicao lembrada ---
ov_pos = Overlay(fresh_cfg(x=60, y=70))
assert (ov_pos.x(), ov_pos.y()) == (60, 70), (ov_pos.x(), ov_pos.y())
ov_pos.close()
print("OK posicao lembrada")



# --- teste 2: parse + toggle + save + backup ---
ov = Overlay(fresh_cfg())
# metricas dinamicas: os testes seguem valendo se o checklist mudar de tamanho
SECOES = len(ov.sections)
TOTAL = len(ov.checkboxes)
assert ov.views.count() == SECOES + 1, ov.views.count()  # secoes + overview
assert ov.views.widget(SECOES) is ov.home_page, "overview nao e a ultima"
assert TOTAL > 0, TOTAL
assert "F8" in ov.btn_lock.text() and "Livre" in ov.btn_lock.text()
assert ov.views.currentIndex() == SECOES, "tela inicial deve ser o overview"

cb, item, sec = ov.checkboxes[0]
assert not item["checked"]
cb.setChecked(True)
assert item["checked"]
assert os.path.isfile(md_copy + ".bak"), "backup nao criado"
with open(md_copy, encoding="utf-8") as f:
    assert "- [x]" in f.read(), "marcacao nao foi salva"
assert ("1 de %d" % TOTAL) in ov.lbl_total.text(), ov.lbl_total.text()
assert ov.lbl_pct.text().endswith("%"), ov.lbl_pct.text()
done0, total0 = section_progress(ov.sections[0])
assert done0 == 1, (done0, total0)
_h0 = [c for _t, c, _i in ov.detail_heads if _i == 0][0]
assert _h0.text() == "%d/%d" % (done0, total0), _h0.text()
print("OK toggle/save/backup/dashboard")

# --- arrastar pela barra de titulo move a janela ---
from PySide6.QtCore import QEvent, QPointF, QPoint
from PySide6.QtGui import QMouseEvent
ov.show()
app.processEvents()
def _me(tipo, local, button, buttons):
    # construtor moderno: global explicito (o deprecado zera globalPosition)
    g = QPointF(local + QPoint(500, 300))
    return QMouseEvent(tipo, QPointF(local), g, button, buttons,
                       Qt.NoModifier)


_pt = ov.titlebar.mapTo(ov, ov.titlebar.rect().center())
_x0, _y0 = ov.x(), ov.y()
ov.mousePressEvent(_me(QEvent.MouseButtonPress, _pt,
                       Qt.LeftButton, Qt.LeftButton))
assert ov._drag is not None, "press na barra nao iniciou o arrasto"
_mv = _pt + QPoint(40, 30)
ov.mouseMoveEvent(_me(QEvent.MouseMove, _mv, Qt.NoButton, Qt.LeftButton))
assert (ov.x(), ov.y()) != (_x0, _y0), "janela nao se moveu"
ov.mouseReleaseEvent(_me(QEvent.MouseButtonRelease, _mv,
                         Qt.LeftButton, Qt.NoButton))
assert ov._drag is None, "arrasto nao soltou"
ov.mousePressEvent(_me(QEvent.MouseButtonPress,
                       QPoint(10, ov.height() - 10),
                       Qt.LeftButton, Qt.LeftButton))
assert ov._drag is None, "arrasto comecou fora da barra"
print("OK arrastar pela barra")

# --- drag via eventFilter (caminho real: barra e textos; botoes intactos)
_bx0, _by0 = ov.x(), ov.y()
_ft = ov.titlebar.mapTo(ov, ov.titlebar.rect().center())
assert ov.eventFilter(
    ov.titlebar,
    _me(QEvent.MouseButtonPress, _ft, Qt.LeftButton, Qt.LeftButton)) is True
assert ov._drag is not None, "filtro nao iniciou o arrasto"
_mv2 = _ft + QPoint(25, 15)
assert ov.eventFilter(
    ov.titlebar,
    _me(QEvent.MouseMove, _mv2, Qt.NoButton, Qt.LeftButton)) is True
assert (ov.x(), ov.y()) != (_bx0, _by0), "filtro nao moveu a janela"
assert ov.eventFilter(
    ov.titlebar,
    _me(QEvent.MouseButtonRelease, _mv2, Qt.LeftButton, Qt.NoButton)) is True
assert ov._drag is None, "filtro nao soltou"
_lt = ov.lbl_title.mapTo(ov, ov.lbl_title.rect().center())
assert ov.eventFilter(
    ov.lbl_title,
    _me(QEvent.MouseButtonPress, _lt, Qt.LeftButton, Qt.LeftButton)) is True
assert ov._drag is not None, "texto da barra nao arrasta"
ov.eventFilter(ov.lbl_title,
               _me(QEvent.MouseButtonRelease, _lt,
                   Qt.LeftButton, Qt.NoButton))
assert ov.eventFilter(
    ov.btn_lock,
    _me(QEvent.MouseButtonPress, QPoint(5, 5),
        Qt.LeftButton, Qt.LeftButton)) is False, "filtro engoliu botao"
print("OK drag via eventFilter")

# --- teste 3: merge quando o Obsidian muda por fora ---
# edicao externa: marca outro item direto no arquivo
with open(md_copy, encoding="utf-8") as f:
    content = f.read()
content2, n = re.subn(r"- \[ \]", "- [x]", content, count=1)
# garante que a edicao externa pegou um item AINDA desmarcado no overlay:
# (o item 0 do overlay ja esta [x] no disco; pega o proximo [ ])
assert n == 1
with open(md_copy, "w", encoding="utf-8") as f:
    f.write(content2)

cb2, item2, sec2 = ov.checkboxes[1]
assert not item2["checked"]
cb2.setChecked(True)  # agenda o merge via singleShot
app.processEvents()   # dispara _do_external_reload
with open(md_copy, encoding="utf-8") as f:
    final = f.read()
assert final.count("- [x]") >= 3, final.count("- [x]")  # ext + item0 + item1
assert "mesclado" in ov.hint.text(), ov.hint.text()
print("OK merge externo preservado")

# --- teste 4: filtro global + pulo de secao ---
ov.show_home()
ov.filter.setText("corveta")
assert "resultados" in ov.hint.text(), ov.hint.text()
ov._jump_to_match()
cur = ov.views.currentIndex()
assert cur < SECOES, cur
QtWidgets = __import__("PySide6.QtWidgets", fromlist=["QCheckBox", "QLabel"])
texts = [(cb.toolTip() or cb.text() or cb.accessibleName())
         for cb in ov.views.currentWidget().findChildren(QtWidgets.QCheckBox)]
texts += [lb.text() for lb in ov.views.currentWidget().findChildren(
    QtWidgets.QLabel)]
assert any("corveta" in t.lower() for t in texts), "secao sem o termo"
# word-wrap ligado: textos longos quebram em vez de cortar
assert any(lb.wordWrap() for lb in ov.views.currentWidget().findChildren(
    QtWidgets.QLabel)), "labels sem word-wrap"
# sem fundo branco: paginas/scroll no tema escuro
assert "QScrollArea" in nms_overlay.QSS, "QSS sem regra do QScrollArea"
assert 'objectName="inner"' in open(
    "nms_overlay.py", encoding="utf-8").read(), "inner sem objectName"
# redimensionavel via grip
assert hasattr(ov, "grip"), "sem QSizeGrip p/ redimensionar"
assert ov.minimumWidth() >= 200, ov.minimumWidth()
# opacidade: janela sempre opaca, alfa so no fundo (texto nao apaga)
assert ov.windowOpacity() == 1.0, ov.windowOpacity()
assert "rgba(" in ov.styleSheet(), "fundo sem rgba"
ov.slider.setValue(30)
assert ov.windowOpacity() == 1.0, "texto apagaria junto"
assert "rgba(" in ov.styleSheet(), "fundo sem rgba apos slider"
assert abs(ov.cfg["opacity"] - 0.30) < 0.01, ov.cfg["opacity"]
assert "rgba(" in nms_overlay.build_qss(0.5), "build_qss sem rgba"
assert "rgba(" in nms_overlay.build_qss("lixo"), "build_qss sem fallback"
ov.slider.setValue(100)
ov._apply_pending_alpha()  # drena debounce pendente do assert acima
# arrasto do slider nao pode repolir a janela a cada tick (~0,7s cada)
calls = []
ov.setStyleSheet = lambda ss: calls.append(ss)
for v in range(30, 90):
    ov.slider.setValue(v)
assert len(calls) == 0, "stylesheet aplicado durante o arrasto: %d" % len(calls)
ov._apply_pending_alpha()
assert len(calls) == 1, "debounce devia aplicar 1x: %d" % len(calls)
ov._apply_pending_alpha()
assert len(calls) == 1, "apply idempotente quebrou"
print("OK slider sem travar")
# rolagem estavel: barra vertical sempre visivel => largura constante,
# sem flip aparecer/sumir que requebra as labels e move a posicao sozinha
from PySide6.QtCore import Qt as _Qt
for _i in range(ov.views.count()):
    _sa = ov.views.widget(_i).findChild(QtWidgets.QScrollArea)
    assert _sa.verticalScrollBarPolicy() == _Qt.ScrollBarAlwaysOn, _i
    assert _sa.horizontalScrollBarPolicy() == _Qt.ScrollBarAlwaysOff, _i
_sa0 = ov.views.widget(0).findChild(QtWidgets.QScrollArea)
_sb0 = _sa0.verticalScrollBar()
if _sb0.maximum() > 0:
    _sb0.setValue(_sb0.maximum())
    app.processEvents()
    _w = _sa0.viewport().width()
    for _ in range(5):
        app.processEvents()
        assert _sa0.viewport().width() == _w, "largura oscilou"
        assert _sb0.value() == _sb0.maximum(), "posicao voltou sozinha"
print("OK rolagem estavel")
# trava com hotkey falho nao prende (anti-deadlock)
import ctypes as _ct
try:
    _u32 = _ct.windll.user32
    _real_reg = _u32.RegisterHotKey
    _u32.RegisterHotKey = lambda *a: 0  # forca falha (ex.: em uso)
    ov._hotkey_ok = False
    ov.cfg["locked"] = False
    ov.toggle_lock()
    assert ov.cfg["locked"] is False, "travou sem hotkey -> deadlock"
    _u32.RegisterHotKey = _real_reg
    ov._register_hotkey()
except AttributeError:
    # sem user32 (CI linux): testa so o guarda do _apply_lock
    ov._hotkey_ok = False
    ov.cfg["locked"] = True
    ov._apply_lock()
    assert ov.cfg["locked"] is False, "travou sem hotkey -> deadlock"
# _apply_lock tambem forca destravado se o config veio locked:true sem hotkey
ov._hotkey_ok = False
ov.cfg["locked"] = True
ov._apply_lock(initial=True)
assert ov.cfg["locked"] is False, "inicio travado sem hotkey -> deadlock"
assert hasattr(ov, "_native_filter"), "sem filtro nativo de hotkey"
ov.filter.setText("")
print("OK filtro global (-> aba %d)" % cur)

# --- overview: cards clicaveis + titulo completo + nav + legenda ---
assert ov.views.widget(SECOES) is ov.home_page, "overview nao e a ultima"
assert len(ov.home_rows) == SECOES, len(ov.home_rows)
_d0, _t0 = section_progress(ov.sections[0])
assert ov.home_rows[0].count.text().startswith(
    "%d de %d" % (_d0, _t0)), ov.home_rows[0].count.text()
assert ov.home_rows[0].name.text() == ov.sections[0]["titulo"]
ov.show_home()
app.processEvents()
from PySide6.QtTest import QTest
QTest.mouseClick(ov.home_rows[3], Qt.LeftButton)
app.processEvents()
assert ov.views.currentIndex() == 3, ov.views.currentIndex()
_t0labels = [lb.text() for lb in ov.views.widget(0).findChildren(
    QtWidgets.QLabel) if lb.objectName() == "secTitleBig"]
assert _t0labels and _t0labels[0] == ov.sections[0]["titulo"], _t0labels
ov.show_section(0)
assert ov.views.currentIndex() == 0, ov.views.currentIndex()
_back = [b for b in ov.views.widget(3).findChildren(
    QtWidgets.QPushButton) if b.objectName() == "ghost"]
assert _back, "sem botao voltar"
_back[0].click()
assert ov.views.currentIndex() == SECOES, ov.views.currentIndex()
assert ov.cfg["view"] == {"home": True, "sec": 0}, ov.cfg["view"]
ov.show_section(5)
assert ov.cfg["view"] == {"home": False, "sec": 5}, ov.cfg["view"]
assert ov.lbl_alpha.text().endswith("%"), ov.lbl_alpha.text()
assert ov.btn_reload.toolTip() == "Recarregar do Obsidian"
assert ov.btn_reload.objectName() == "tool"
assert "Esc limpa" in ov._hint_base(), ov._hint_base()
assert [t for t, _s in ov._menu_actions()] == [
    "Recarregar do Obsidian", "Trocar tecla de trava (atual: F8)",
    "Trocar tecla de foco (atual: F9)",
    "Redefinir posi\u00e7\u00e3o e tamanho", "Abrir pasta do checklist"]
ov.filter.setText("corveta")
QTest.keyClick(ov.filter, Qt.Key_Escape)
assert ov.filter.text() == "", repr(ov.filter.text())
print("OK overview/nav/legenda")

# --- teste 5: trava + mapeamento de teclas ---
ov._hotkey_ok = True  # simula hotkey global funcionando (instancia unica)
ov.cfg["locked"] = False
ov._refresh_lock_ui()
assert "Livre" in ov.btn_lock.text() and "F8" in ov.btn_lock.text()
ov.toggle_lock()
assert ov.cfg["locked"] is True
assert "Travado" in ov.btn_lock.text() and "F8" in ov.btn_lock.text()
ov.toggle_lock()
assert ov.cfg["locked"] is False
assert "Livre" in ov.btn_lock.text()
assert qt_key_to_vk(Qt.Key_F9) == (0x78, "F9")
assert qt_key_to_vk(Qt.Key_G) == (0x47, "G")
assert qt_key_to_vk(Qt.Key_5) == (0x35, "5")
assert qt_key_to_vk(Qt.Key_Escape) is None
print("OK trava + mapa de teclas")

# --- click-through: sequencia Get->OR->Set correta (HWND real so em prod) ---
from nms_overlay import GWL_EXSTYLE, WS_EX_TRANSPARENT, WS_EX_LAYERED


class _FakeU32(object):
    def __init__(self):
        self.ex = 0
        self.calls = []

    def GetWindowLongW(self, hwnd, idx):
        self.calls.append(("get", hwnd, idx))
        return self.ex

    def SetWindowLongW(self, hwnd, idx, val):
        self.calls.append(("set", hwnd, idx, val))
        self.ex = val & 0xFFFFFFFF
        return val


class _FakeWindll(object):
    def __init__(self):
        self.user32 = _FakeU32()


_real_windll = _ct.windll
_ct.windll = _FakeWindll()
try:
    ov._set_click_through(True)
    _ex = _ct.windll.user32.ex
    assert _ex & WS_EX_TRANSPARENT, "TRANSPARENT nao aplicado: 0x%08x" % _ex
    assert _ex & WS_EX_LAYERED, "LAYERED perdido: 0x%08x" % _ex
    assert _ct.windll.user32.calls[0][0] == "get", "sem leitura antes"
    ov._set_click_through(False)
    _ex = _ct.windll.user32.ex
    assert not (_ex & WS_EX_TRANSPARENT), "TRANSPARENT nao removido"
    assert _ex & WS_EX_LAYERED, "LAYERED removido ao destravar"
finally:
    _ct.windll = _real_windll
print("OK click-through (sequencia)")

# --- watchdog: travado sem hotkey nunca prende ---
ov.cfg["locked"] = True
ov._hotkey_ok = False
ov._watch_hotkey()
assert ov.cfg["locked"] is False, "watchdog nao destravou"
ov._hotkey_ok = True
ov.toggle_lock()
assert ov.cfg["locked"] is True
ov._watch_hotkey()
assert ov.cfg["locked"] is True, "watchdog mexeu sem precisar"
ov.toggle_lock()
assert ov.cfg["locked"] is False
print("OK watchdog anti-trava")

# --- X fecha o processo de verdade (quit explicito; Qt.Tool nao sai sozinho)
_quit_calls = []
_orig_QApplication = nms_overlay.QApplication


class _FakeApp:
    @staticmethod
    def instance():
        return _FakeApp()

    def removeNativeEventFilter(self, *a):
        pass

    def quit(self):
        _quit_calls.append(1)


nms_overlay.QApplication = _FakeApp
try:
    ov2 = Overlay(fresh_cfg(x=10, y=10))
    ov2.close()
finally:
    nms_overlay.QApplication = _orig_QApplication
assert _quit_calls, "close() nao pediu quit: processo ficaria em 2o plano"
print("OK fechar sai do processo")

# --- modo foco: estrela, cartao amarelo compacto, persistencia ---
assert getattr(ov, "focus", None) is None
assert len(ov.focus_btns) == len(ov.checkboxes) == TOTAL
_sec0 = ov.sections[0]["titulo"]
_txt0 = next(b[1]["text"] for b in ov.sections[0]["blocos"]
             if b[0] == "item" and not b[1]["checked"])
_h_full = ov.height()
ov.toggle_focus(_sec0, _txt0)
app.processEvents()
assert ov.focus == {"sec": _sec0, "text": _txt0}, ov.focus
assert ov.cfg["focus"] == {"sec": _sec0, "text": _txt0}
assert not ov.focus_card.isHidden(), "cartao nao apareceu"
assert ov.views.isHidden(), "lista devia sumir"
assert ov.height() < _h_full, (ov.height(), _h_full)
assert ov.focus_lbl.text() == _txt0, ov.focus_lbl.text()
assert "nesta se\u00e7\u00e3o" in ov.focus_ctx.text(), ov.focus_ctx.text()
assert _sec0 in ov.focus_sec.text(), ov.focus_sec.text()
ov.toggle_focus(_sec0, _txt0)  # de novo = sai do foco
app.processEvents()
assert ov.focus is None
assert ov.focus_card.isHidden()
assert not ov.views.isHidden()
assert ov.height() == _h_full, (ov.height(), _h_full)
# estrela clica e foca
_sec1 = ov.sections[1]["titulo"]
_txt1 = next(b[1]["text"] for b in ov.sections[1]["blocos"]
             if b[0] == "item" and not b[1]["checked"])
_star = next(b for b, p, s in ov.focus_btns
             if p["text"] == _txt1 and s["titulo"] == _sec1)
_star.click()
app.processEvents()
assert ov.focus == {"sec": _sec1, "text": _txt1}, ov.focus
assert not ov.focus_card.isHidden()
# marcar pelo cartao salva no .md
ov.focus_cb.setChecked(True)
app.processEvents()
assert ov.focus_cb.isChecked()
with open(md_copy, encoding="utf-8") as f:
    assert "- [x]" in f.read()
# foco inexistente nao entra
ov.toggle_focus("secao fantasma", "missao fantasma")
assert ov.focus is None
assert not ov.views.isHidden()
# persistencia: nova instancia restaura o foco
ov.toggle_focus(_sec0, _txt0)
cfg2 = fresh_cfg(x=10, y=10)
cfg2["focus"] = dict(ov.cfg["focus"])
ov3 = Overlay(cfg2)
assert ov3.focus == {"sec": _sec0, "text": _txt0}, ov3.focus
assert not ov3.focus_card.isHidden()
ov3.close()
ov.unfocus()
print("OK modo foco")

# --- visao persistida entre aberturas ---
cfg_v = fresh_cfg(x=10, y=10)
cfg_v["view"] = {"home": False, "sec": 5}
ov4 = Overlay(cfg_v)
assert ov4.views.currentIndex() == 5, ov4.views.currentIndex()
ov4.close()
cfg_w = fresh_cfg(x=10, y=10)
ov5 = Overlay(cfg_w)
assert ov5.views.currentIndex() == SECOES, ov5.views.currentIndex()
ov5.close()
print("OK visao persistida")

# --- tecla de foco: chama o overlay p/ frente sem alt-tab ---
assert hasattr(ov, "toggle_overlay_focus"), "sem toggle_overlay_focus"


class _FakeU32F(object):
    def __init__(self):
        self.ex = 0
        self.fg = 424242  # "jogo" em 1o plano
        self.calls = []

    def GetWindowLongW(self, hwnd, idx):
        return self.ex

    def SetWindowLongW(self, hwnd, idx, val):
        self.ex = val & 0xFFFFFFFF
        return val

    def GetForegroundWindow(self):
        return self.fg

    def SetForegroundWindow(self, hwnd):
        self.calls.append(("fg", hwnd))
        self.fg = hwnd
        return 1

    def IsIconic(self, hwnd):
        return 0

    def ShowWindow(self, hwnd, cmd):
        self.calls.append(("show", hwnd, cmd))
        return 1

    def RegisterHotKey(self, *a):
        return 1

    def UnregisterHotKey(self, *a):
        return 1


class _FakeWindllF(object):
    def __init__(self):
        self.user32 = _FakeU32F()


_real_windll_f = _ct.windll
_ct.windll = _FakeWindllF()
try:
    ov.cfg["locked"] = True
    ov._hotkey_ok = True
    ov._apply_lock()
    assert "Travado" in ov.btn_lock.text()
    ov.toggle_overlay_focus()  # chama: salva jogo, destrava, foca overlay
    assert ov.cfg["locked"] is False, "chamar devia destravar p/ clicar"
    assert _ct.windll.user32.fg == ov._hwnd(), "overlay devia estar em 1o plano"
    ov.toggle_overlay_focus()  # dispensa: retrava, devolve foco ao jogo
    assert ov.cfg["locked"] is True, "dispensar devia retravar"
    assert _ct.windll.user32.fg == 424242, "foco devia voltar ao jogo"
finally:
    _ct.windll = _real_windll_f
print("OK tecla de foco chama/devolve")

ov.close()
shutil.rmtree(tmp, ignore_errors=True)
print("TEST-OK geral.")
