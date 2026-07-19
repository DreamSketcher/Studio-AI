@echo off
setlocal EnableDelayedExpansion

set i=0
for %%F in (*.py) do (
    set /a i+=1
    set file[!i!]=%%F
    echo !i!^) %%F
)

if %i%==0 (
    echo В текущей папке нет Python-файлов.
    pause
    exit /b
)

echo.
set /p num=Выберите номер файла: 

if not defined file[%num%] (
    echo Неверный номер.
    pause
    exit /b
)

echo.
echo Запуск !file[%num%]!
echo.

python "!file[%num%]!"

pause