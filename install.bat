@echo off
title Python Requirements Installer

echo ===============================
echo Installing Python requirements
echo ===============================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден в PATH.
    pause
    exit /b 1
)

if not exist requirements-core.txt (
    echo [ERROR] Файл requirements-core.txt не найден.
    pause
    exit /b 1
)

echo Обновление pip...
python -m pip install --upgrade pip

echo.
echo Установка зависимостей...
python -m pip install -r requirements-core.txt

if errorlevel 1 (
    echo.
    echo [ERROR] Во время установки произошла ошибка.
) else (
    echo.
    echo [OK] Все зависимости успешно установлены.
)

echo.
pause