"""Gera capturas do overlay para o README, sem abrir o jogo.

As capturas precisam do loop de eventos REAL do Qt (app.exec + timers):
sem ele o Qt não entrega paintEvent ao conteúdo rolável e as imagens
saem sem os cards. A janela nativa aparece na tela por ~3 s e fecha
sozinha no fim — o jogo não é aberto e nada é gravado.

Uso: venv\\Scripts\\python.exe tools\\gerar_prints.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nms_overlay
from nms_overlay import Overlay
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "docs", "imgs")

# Nao sujar o config real durante as capturas
nms_overlay.save_config = lambda cfg: None


def salvar(widget, nome):
    destino = os.path.join(SAIDA, nome)
    widget.grab().save(destino)
    print("%-16s %4d KB" % (nome, os.path.getsize(destino) // 1024))


app = QApplication([])
os.makedirs(SAIDA, exist_ok=True)
ov = Overlay({"md_path": nms_overlay.DEFAULT_MD, "x": 90, "y": 90})
ov.show()

secao = next(i for i, s in enumerate(ov.sections) if "Fauna" in s["titulo"])
txt0 = next(b[1]["text"] for b in ov.sections[secao]["blocos"] if b[0] == "item")
tit0 = ov.sections[secao]["titulo"]


def passo1():
    salvar(ov, "01-overview.png")   # dashboard + cards


def passo2():
    ov.show_section(secao)


def passo3():
    salvar(ov, "02-secao.png")      # itens da seção
    ov.show_home()
    ov.filter.setFocus()
    ov.filter.setText("corveta")


def passo4():
    salvar(ov, "03-busca.png")      # busca com resultados
    ov.toggle_focus(tit0, txt0)


def passo5():
    salvar(ov, "04-foco.png")       # cartão compacto do objetivo
    ov.close()
    print("Capturas salvas em docs/imgs/")
    app.quit()


# Agenda unica: cada passo roda uma vez; o intervalo de ~400 ms da
# tempo de o loop de eventos real pintar o estado antes da captura.
QTimer.singleShot(600, passo1)    # 01: overview (home)
QTimer.singleShot(1000, passo2)   # 02: abre a seção
QTimer.singleShot(1400, passo3)   # captura 02; volta pra home + busca
QTimer.singleShot(1800, passo4)   # captura 03; entra no modo foco
QTimer.singleShot(2200, passo5)   # captura 04; fecha
app.exec()
