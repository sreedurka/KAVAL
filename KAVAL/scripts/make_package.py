"""
KAVAL - build the portable package (a single zip) for another machine.

Includes what is needed to RUN the product and to re-run the pipeline: code, all data the
product serves, docs, the recorded demo, the supplied dataset, the CropSight feature export,
and the Windows scripts (setup.cmd, run.cmd, WINDOWS_SETUP.md).

Excludes anything machine-specific or rebuildable: .venv (Linux binaries, rebuilt by
setup.cmd), .cache (the 15 GB scene cache; re-downloaded only if the pipeline is re-run),
node_modules and dist (rebuilt by `npm ci`), Python caches, Playwright test artefacts.

Refuses to build if an API-key-shaped secret appears in any packaged text file: keys are
only ever passed as environment variables, and the package must never carry one.

Run:  .venv/bin/python KAVAL/scripts/make_package.py [--out ../KAVAL_Package.zip]
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOP = "KAVAL_Package"

INCLUDE = [
    "setup.cmd", "run.cmd", "WINDOWS_SETUP.md", "SESSION_HANDOFF.md", "CLAUDE.md",
    ".claude", "KAVAL", "Dataset", "documents",
    "CropSight/CropSight_Task3_UPGRADED/06_FEATURE_ACQUISITION",
]
EXCLUDE_DIRS = {"node_modules", "dist", "__pycache__", ".pytest_cache", "test-results",
                ".venv", ".cache", ".git", ".vite"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".tsbuildinfo"}
# Key shapes: Google (AIza..., AQ.), Anthropic (sk-ant-), OpenAI/Groq/OpenRouter (sk-, gsk_).
SECRET = re.compile(rb"(AIza[0-9A-Za-z_\-]{30,}|AQ\.[A-Za-z0-9_\-]{30,}|sk-ant-[A-Za-z0-9_\-]{20,}"
                    rb"|gsk_[A-Za-z0-9]{20,}|sk-or-[A-Za-z0-9_\-]{20,})")
TEXT = {".py", ".md", ".txt", ".json", ".ts", ".tsx", ".js", ".cmd", ".sh", ".css", ".html",
        ".toml", ".yaml", ".yml", ".csv"}


def files():
    for item in INCLUDE:
        p = ROOT / item
        if not p.exists():
            sys.exit(f"missing from the project: {item}")
        if p.is_file():
            yield p
            continue
        for f in sorted(p.rglob("*")):
            rel = f.relative_to(ROOT)
            if f.is_dir() or set(rel.parts) & EXCLUDE_DIRS or f.suffix in EXCLUDE_SUFFIX:
                continue
            yield f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT.parent / "KAVAL_Package.zip"))
    out = Path(ap.parse_args().out).resolve()

    todo = list(files())
    leaks = [str(f.relative_to(ROOT)) for f in todo
             if f.suffix in TEXT and f.stat().st_size < 50_000_000
             and SECRET.search(f.read_bytes())]
    if leaks:
        sys.exit(f"REFUSING: secret-shaped string found in {leaks}")

    for need in ("setup.cmd", "run.cmd"):
        if b"\r\n" not in (ROOT / need).read_bytes():
            sys.exit(f"{need} must have CRLF line endings for Windows")

    total = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in todo:
            z.write(f, f"{TOP}/{f.relative_to(ROOT).as_posix()}")
            total += f.stat().st_size
    print(f"{len(todo):,} files, {total / 1e6:,.0f} MB uncompressed -> {out} "
          f"({out.stat().st_size / 1e6:,.0f} MB)")


if __name__ == "__main__":
    main()
