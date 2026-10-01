# KAVAL on Windows: setup and run

KAVAL is a satellite audit of the Digital Crop Survey: a FastAPI backend, a React + Leaflet
web interface, and an analyst that answers questions in plain English. This package contains
the code, all the data the product serves, the documentation and the recorded demo. Two
double-click scripts set it up and run it.

| Step | What you do | Time |
|---|---|---|
| 1 | Unzip the package | 1 min |
| 2 | Double-click **`setup.cmd`** (once per machine) | 5–10 min, needs internet |
| 3 | Double-click **`run.cmd`** (every time) | under 1 min |
| 4 | Use the app at **http://127.0.0.1:5173** | |

---

## 1. Before you start

- **Windows 10 or 11, 64-bit.** About 2 GB free disk for a normal setup, about 5 GB for `setup.cmd full`.
- **Internet**, during setup only. Running the app needs internet only for the map tiles and the Gemini analyst.
- **No administrator rights needed.** Python is installed into this folder by `uv`. Node.js comes from `winget`, which may show one Windows prompt.
- **Optional:** a free **Gemini API key** for the LLM analyst. Get one at
  https://aistudio.google.com (sign in, then "Get API key"). Without it, the analyst still
  answers using its offline planner, and every answer says which mode produced it.

## 2. Unzip

Unzip `KAVAL_Package.zip` to a short local path, for example **`C:\KAVAL`**. Avoid:
- **OneDrive or Dropbox folders.** Syncing locks files during setup.
- **Very long paths.** Some Node packages hit Windows' 260-character path limit.
- **Running from inside the zip.** Extract it first ("Extract all…").

You should see:

```
C:\KAVAL\
  setup.cmd            one-time setup
  run.cmd              start KAVAL
  WINDOWS_SETUP.md     this file
  KAVAL\               code, data, docs (start with KAVAL\README.md)
  Dataset\             the data FarmwiseAI supplied
  documents\           the challenge brief
  CropSight\           prior feature export (needed only to re-run Phase 3)
  SESSION_HANDOFF.md   project state, for anyone continuing development
```

## 3. Setup: `setup.cmd`

Double-click `setup.cmd`. If Windows shows **"Windows protected your PC"**, click **More
info → Run anyway**. These are plain text scripts you can open in Notepad to read first.

The script runs five steps and prints each one:

1. **uv.** Installs uv, a fast Python manager, if it is missing. No admin rights needed.
2. **Python 3.12.** Downloads it and creates a private environment in `.venv\`. Your system
   Python is not touched.
3. **Python packages.** Installs the pinned versions in `KAVAL\requirements-app.txt`, the
   exact set verified on 2026-10-01.
4. **Node.js LTS.** Installs it with `winget` if it is missing.
5. **Web interface packages.** Runs `npm ci` in `KAVAL\frontend`, exactly as locked in
   `package-lock.json`.

It ends by loading the API once to prove the install works. A good finish looks like:

```
API loads: 20 routes
=== Setup complete. Start KAVAL with:  run.cmd ===
```

**`setup.cmd full`** (run it from a Command Prompt in the folder) also installs the
science-pipeline packages (`KAVAL\requirements-pipeline.txt`: LightGBM, PyTorch, rasterio,
STAC, Fields of The World, Presto) and the Chromium browser for the UI tests. You only need
this to **re-run the analysis** or the Playwright tests. The product itself never needs it,
because every derived file it serves is already in `KAVAL\data`.

Running `setup.cmd` again is safe. It skips anything already done.

## 4. Run: `run.cmd`

Double-click `run.cmd`.

1. It asks for an optional Gemini key. **Paste it and press Enter**, or just press Enter to
   use the offline planner. The key lives only in the memory of the windows `run.cmd` opens.
   It is never written to disk, and it is gone when you close them.
2. It opens two windows, **"KAVAL API (port 8077)"** and **"KAVAL UI (port 5173)"**. Leave
   them open.
3. It waits for both to answer, then opens your browser at the Leakage Ladder:
   **http://127.0.0.1:5173/#validation**.

**To stop KAVAL:** close the two KAVAL windows.

| Address | What it is |
|---|---|
| http://127.0.0.1:5173 | The web interface (six tabs) |
| http://127.0.0.1:8077/docs | The API, with interactive documentation of every endpoint |

To skip the key prompt, set the key for your Windows user once:
`setx GEMINI_API_KEY "your-key"`, then open a new window. Note that this **does** store it in
your user environment. If you would rather not, keep pasting it at the prompt.

## 5. Using it

Start with these, all under `KAVAL\docs\`:

| File | Use it for |
|---|---|
| `team\presentation\presentation-script.md` | The 15-minute talk, timed, with speaker roles |
| `team\presentation\app-demo-script.md` | What to say on each page of the website |
| `team\website\page-guide.md` | What every element on every page means and where its data comes from |
| `team\website\demo-test-inputs.md` | **46 analyst questions verified to give good answers**, plus exact click paths |
| `team\website\glossary.md` | Every term: DISPUTED, Rabi, Registry share, the Leakage Ladder… |
| `demo\kaval_walkthrough.webm` | A 2-minute recorded walkthrough (open it in a browser) |

**The analyst.** Every answer carries a chip naming what answered it:
- `LLM · gemini:…`: Gemini planned the answer.
- `offline planner — not LLM`: no key was given, or Gemini was busy or over its free quota.
  The answer is routed by keywords to the same tools and is still accurate.

The free tier allows roughly 10 questions a minute. Don't rehearse on the quota you need for
a live demo.

## 6. Checking it works (optional)

From a Command Prompt in the package folder:

```bat
set PYTHONUTF8=1
.venv\Scripts\python.exe -m pytest KAVAL\tests -q
```

Expected result: **41 passed**. These are behavioural tests of every API route against the
evidence files.

UI tests (after `setup.cmd full`, with `run.cmd` running):

```bat
cd KAVAL\frontend
npx playwright test
```

Expected result: **23 passed**, with screenshots in `KAVAL\docs\e2e\`.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| "Windows protected your PC" | More info, then Run anyway. |
| `uv could not be installed` | PowerShell may be blocked by policy. Install uv by hand from https://docs.astral.sh/uv/, open a new window, run `setup.cmd` again. |
| `Node.js not found` after setup | `winget` is missing on older Windows. Install the LTS from https://nodejs.org, open a new window, run `setup.cmd` again. |
| `npm ci` fails with path errors | The folder path is too long. Move the package to `C:\KAVAL`. |
| Setup fails behind a company proxy | Set `HTTPS_PROXY=http://proxy:port` in the window, then run `setup.cmd` from it. |
| `Port 8077 is already in use` | KAVAL (or something else) is already running. Close the old KAVAL windows. |
| The API window shows an error and closes the browser wait | Read the message in the "KAVAL API" window. `Phase 6 has not run` means `KAVAL\data` is incomplete: re-extract the zip. |
| The map has no background | The map tiles come from OpenStreetMap and need internet. The parcels still draw. |
| The analyst always says "offline planner" | No key was given, or Gemini refused (quota or overload). The answer's note says which. Wait a minute, or continue offline. |
| Garbled characters (`â€”`) in the API window | The scripts set `PYTHONUTF8=1`. If you run Python by hand, set it first. |
| Antivirus quarantines `uv.exe` or `node.exe` | Allow them. They are the official installers from astral.sh and nodejs.org. |

## 8. Notes for developers

- **Running by hand:** `set PYTHONUTF8=1`, then
  `.venv\Scripts\python.exe -m uvicorn KAVAL.api.main:app --port 8077`. In a second window:
  `set KAVAL_API=http://127.0.0.1:8077` then `cd KAVAL\frontend && npm run dev`.
- **Use `127.0.0.1`, not `localhost`.** On Windows, `localhost` may resolve to IPv6 (`::1`),
  where the API is not listening.
- **The analyst's model chain** is configured by environment variables, documented in
  `KAVAL\api\llm.py` and `KAVAL\docs\team\10_API_ANALYST.md`. `ANTHROPIC_API_KEY`,
  `GROQ_API_KEY` and `OPENROUTER_API_KEY` also work. The local open-weight model
  (`serve_local_llm.sh`) is Linux-only in this package.
- **Re-running the pipeline** (after `setup.cmd full`): see `KAVAL\README.md`. Phase 1 to 3
  scripts download satellite data, about 15 GB and hours of work. Phase 4 takes about 25 min.
  Google Earth Engine features cannot be regenerated without GEE credentials. That is a
  documented exception.
- **Project state and rules** for anyone continuing development: `SESSION_HANDOFF.md`,
  `KAVAL\plan.md` (authoritative), `KAVAL\progress.md`.
