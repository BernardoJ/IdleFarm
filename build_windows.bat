@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Instale Python 3.12 de 64 bits para recompilar o jogo.
  exit /b 1
)
if not exist .venv\Scripts\python.exe py -3.12 -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install --requirement requirements-dev.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pytest -q
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m ruff check .
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m ruff format --check .
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe tools\validate.py --output qa-output\visual
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe tools\validate_experience.py --output qa-output\experience
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe tools\benchmark.py --output qa-output\performance.json
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean IdleFarm.spec
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe tools\smoke_exe.py dist\IdleFarm.exe --output qa-output\packaged
if errorlevel 1 exit /b 1
echo Build e smoke test concluidos: dist\IdleFarm.exe
endlocal
