@echo off
chcp 65001 >nul
title Git Connect Push

echo ===============================
echo      Git Connect ^& Push
echo ===============================
echo.

:: Проверка Git
git --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Git не установлен
    pause
    exit /b
)

:: Инициализация
if not exist ".git" (
    echo 📁 Создание Git репозитория...
    git init
)

:: Проверяем origin
git remote get-url origin >nul 2>&1

if errorlevel 1 (
    echo.
    echo 🔗 Репозиторий не подключен.
    echo.

    set /p REPO="URL GitHub репозитория: "

    if "%REPO%"=="" (
        echo ❌ URL пустой
        pause
        exit /b
    )

    git remote add origin %REPO%
    git branch -M main

    echo ✅ Репозиторий подключен
) else (
    echo.
    echo 🔗 Уже подключен:
    git remote get-url origin
)

echo.
echo 📦 Добавление изменений...
git add .

echo.
set /p MSG="Комментарий коммита (Enter = Update): "

if "%MSG%"=="" (
    set MSG=Update
)

git commit -m "%MSG%"

echo.
echo 🚀 Push...
git push -u origin main

echo.
echo ===============================
echo ✅ Завершено
echo ===============================

pause