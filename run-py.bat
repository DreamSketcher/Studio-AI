@echo off
setlocal EnableDelayedExpansion

set i=0
for %%F in (*.py) do (
    set /a i+=1
    set file[!i!]=%%F
    echo !i!^) %%F
)

if %i%==0 (
    echo V tekushchey papke net Python-faylov.
    pause
    exit /b
)

echo.
set /p num=Vyberite nomer fayla: 

if not defined file[%num%] (
    echo Nevernyy nomer.
    pause
    exit /b
)

echo.
echo Zapusk !file[%num%]!
echo.

rem PYTHONFAULTHANDLER: pechataet Python-treys dazhe pri nativnom krakhe
rem (access violation / segfault) vmesto polnostyu tikhoy smerti processa.
set PYTHONFAULTHANDLER=1
rem PYTHONUNBUFFERED: vyvod pishetsya srazu, bez bufferizatsii.
set PYTHONUNBUFFERED=1

set LOGFILE=run_log_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%.txt
set LOGFILE=%LOGFILE: =0%

echo Polnyy vyvod pishetsya v log-fayl: %LOGFILE%
echo.

powershell -NoProfile -Command "python -u \"!file[%num%]!\" 2>&1 | Tee-Object -FilePath '%LOGFILE%'"

echo.
echo ============================================
echo Kod zaversheniya: %ERRORLEVEL%
if not "%ERRORLEVEL%"=="0" (
    echo [!] Protsess zavershilsya s oshibkoy. Log: %LOGFILE%
) else (
    echo [OK] Protsess zavershilsya bez oshibok.
)
echo ============================================

pause
