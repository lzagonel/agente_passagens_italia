@echo off
setlocal

cd /d "%~dp0"

echo Iniciando o Agente de Passagens da Italia...
echo.

set "CODEX_PYTHON=C:\Users\leooz\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if exist "%CODEX_PYTHON%" (
    "%CODEX_PYTHON%" agente_passagens_italia.py --abrir
    goto fim
)

where python >nul 2>nul
if %errorlevel%==0 (
    python agente_passagens_italia.py --abrir
    goto fim
)

where py >nul 2>nul
if %errorlevel%==0 (
    py agente_passagens_italia.py --abrir
    goto fim
)

echo Nao encontrei um Python funcional neste Windows.
echo Instale o Python em https://www.python.org/downloads/ ou ajuste o caminho no arquivo .bat.

:fim
echo.
pause
