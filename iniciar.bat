@echo off
rem Inicia o overlay NMS sem janela de console (roda ao lado do projeto).
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0nms_overlay.py"
