@echo off
setlocal

cd /d "%~dp0"

set "CODEX_PYTHON=C:\Users\leooz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if exist "%CODEX_PYTHON%" (
    "%CODEX_PYTHON%" monitor_diario.py --salvar
    goto fim
)

where python >nul 2>nul
if %errorlevel%==0 (
    python monitor_diario.py --salvar
    goto fim
)

where py >nul 2>nul
if %errorlevel%==0 (
    py monitor_diario.py --salvar
    goto fim
)

echo Nao encontrei um Python funcional neste Windows.

:fim
echo.
pause
