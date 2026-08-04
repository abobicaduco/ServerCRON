@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM Interprete: SERVERCRON_PYTHON (passado pelo server.py) ou "python" do PATH
if defined SERVERCRON_PYTHON (
  set "PYEXE=%SERVERCRON_PYTHON%"
) else (
  set "PYEXE=python"
)

echo.
echo [BOOT] ========================================
echo [BOOT] ServerCRON - instalar dependencias
echo [BOOT] Python: %PYEXE%
echo [BOOT] ========================================
echo.

"%PYEXE%" -m pip install --upgrade pip
if errorlevel 1 (
  echo [BOOT] Falha ao atualizar pip.
  exit /b 1
)

"%PYEXE%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
  echo [BOOT] Falha ao instalar requirements.txt
  exit /b 1
)

echo.
echo [BOOT] Dependencias instaladas com sucesso.
exit /b 0
