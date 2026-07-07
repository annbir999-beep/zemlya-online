@echo off
rem SubBot — тихий фоновый запуск (без окна консоли).
rem Используется для автозапуска. Для отладки с логом — run-debug.bat.
start "" pythonw "%~dp0subbot.py"
