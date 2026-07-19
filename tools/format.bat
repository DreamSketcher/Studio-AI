@echo off
rem Форматирование/проверка стиля проекта (Black + Ruff, line-length 100).
rem   format.bat         -- авто-правка
rem   format.bat --check -- только проверка (для CI)
cd /d "%~dp0\.."
python tools\format_code.py %*
