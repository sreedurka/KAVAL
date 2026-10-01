@echo off
rem ======================================================================
rem  KAVAL - start the product on Windows
rem
rem    run.cmd            API on http://127.0.0.1:8077, web UI on http://127.0.0.1:5173
rem
rem  The analyst uses a free Gemini key if you paste one (it is kept only in
rem  these windows' memory, never written to disk); press Enter to skip and
rem  the analyst answers with its offline planner instead.
rem  Close the two "KAVAL" windows to stop.
rem ======================================================================
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"

if not exist ".venv\Scripts\python.exe" (
  echo KAVAL is not set up yet. Run setup.cmd first.
  pause
  exit /b 1
)
if not exist "KAVAL\frontend\node_modules" (
  echo The web interface is not installed. Run setup.cmd first.
  pause
  exit /b 1
)

netstat -ano | findstr /r /c:":8077 .*LISTENING" >nul && (
  echo Port 8077 is already in use - KAVAL may already be running. Close it first.
  pause
  exit /b 1
)

if not defined GEMINI_API_KEY (
  echo.
  echo Optional: paste a Gemini API key for the LLM analyst ^(free at https://aistudio.google.com^).
  set /p "GEMINI_API_KEY=Key (or just press Enter to use the offline planner): "
)
if defined GEMINI_API_KEY (
  rem Gemini first; if it is busy or over quota, fall straight to the fast offline planner.
  set "KAVAL_LLM_PROVIDER=gemini"
  echo Analyst: Gemini ^(free tier^), offline planner as fallback.
) else (
  echo Analyst: offline planner ^(no key given^).
)

echo Starting the API ...
start "KAVAL API (port 8077)" cmd /k ".venv\Scripts\python.exe -m uvicorn KAVAL.api.main:app --host 127.0.0.1 --port 8077"

echo Waiting for the API to answer ...
powershell -NoProfile -Command "$t=0; while($t -lt 90){ try { $r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8077/health -TimeoutSec 2; if($r.StatusCode -eq 200){exit 0} } catch {}; Start-Sleep 1; $t++ }; exit 1"
if errorlevel 1 (
  echo The API did not start within 90 s. Look at the "KAVAL API" window for the error.
  pause
  exit /b 1
)

rem The UI proxies /api to the API. 127.0.0.1, not "localhost": on Windows
rem localhost can resolve to IPv6 (::1) where the API is not listening.
set "KAVAL_API=http://127.0.0.1:8077"
echo Starting the web interface ...
start "KAVAL UI (port 5173)" cmd /k "cd /d KAVAL\frontend && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort"

powershell -NoProfile -Command "$t=0; while($t -lt 60){ try { $r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173/ -TimeoutSec 2; if($r.StatusCode -eq 200){exit 0} } catch {}; Start-Sleep 1; $t++ }; exit 1"
start "" "http://127.0.0.1:5173/#validation"
echo.
echo KAVAL is running:   web UI  http://127.0.0.1:5173
echo                     API     http://127.0.0.1:8077/docs
echo Close the two KAVAL windows to stop it.
echo.
pause
