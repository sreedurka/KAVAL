@echo off
rem ======================================================================
rem  KAVAL - one-time setup on Windows 10/11 (x64)
rem
rem    setup.cmd          install what is needed to RUN the product
rem    setup.cmd full     also install the science pipeline + UI test browser
rem
rem  Installs into this folder only (.venv, KAVAL\frontend\node_modules).
rem  Needs an internet connection. Safe to run again: it skips what is done.
rem ======================================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "MODE=%~1"
echo.
echo === KAVAL setup (%CD%) ===
echo.

rem ---- 1. uv: fetches Python 3.12 and installs packages (no admin rights) --
where uv >nul 2>nul
if errorlevel 1 (
  echo [1/5] Installing uv ...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
where uv >nul 2>nul
if errorlevel 1 (
  echo ERROR: uv could not be installed. See WINDOWS_SETUP.md, "Troubleshooting".
  goto :fail
)
echo [1/5] uv ready.

rem ---- 2. Python 3.12 + virtual environment -------------------------------
echo [2/5] Python 3.12 and .venv ...
uv python install 3.12
if errorlevel 1 goto :fail
if not exist ".venv\Scripts\python.exe" (
  uv venv .venv --python 3.12
  if errorlevel 1 goto :fail
)

rem ---- 3. Python packages -------------------------------------------------
echo [3/5] Python packages (product) ...
uv pip install --python .venv\Scripts\python.exe -r KAVAL\requirements-app.txt
if errorlevel 1 goto :fail
if /i "%MODE%"=="full" (
  echo [3/5] Python packages (science pipeline^) ...
  uv pip install --python .venv\Scripts\python.exe -r KAVAL\requirements-pipeline.txt
  if errorlevel 1 goto :fail
  uv pip install --python .venv\Scripts\python.exe --prerelease=allow "ftw-tools>=2.0.0b5"
  if errorlevel 1 goto :fail
  uv pip install --python .venv\Scripts\python.exe --no-deps "git+https://github.com/nasaharvest/presto@11e207a668a34336ced1d8e492a1bd5849b96c4a"
  if errorlevel 1 echo WARNING: Presto needs Git installed ^(winget install Git.Git^); only Phase 3b uses it.
)

rem ---- 4. Node.js (for the web interface) ---------------------------------
where node >nul 2>nul
if errorlevel 1 (
  echo [4/5] Installing Node.js LTS with winget ...
  winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements
  set "PATH=%ProgramFiles%\nodejs;%PATH%"
)
where node >nul 2>nul
if errorlevel 1 (
  echo ERROR: Node.js not found. Install the LTS from https://nodejs.org and run setup.cmd again.
  goto :fail
)
for /f "delims=" %%v in ('node -v') do set "NODEV=%%v"
echo [4/5] Node.js !NODEV! ready.

rem ---- 5. Web interface packages ------------------------------------------
echo [5/5] Web interface packages ...
pushd KAVAL\frontend
call npm ci --no-audit --no-fund
if errorlevel 1 ( popd & goto :fail )
if /i "%MODE%"=="full" (
  call npx playwright install chromium
)
popd

rem ---- check --------------------------------------------------------------
echo.
echo Checking the installation ...
.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'KAVAL'); import KAVAL.api.main as m; print('API loads:', len(m.app.routes), 'routes')"
if errorlevel 1 goto :fail
echo.
echo === Setup complete. Start KAVAL with:  run.cmd ===
echo.
pause
exit /b 0

:fail
echo.
echo === Setup did NOT finish. Read the message above, then see WINDOWS_SETUP.md. ===
pause
exit /b 1
