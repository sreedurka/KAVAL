"""
KAVAL / Phase 8 — colour-vision check of the agreement-status palette.

The status colours are the product's vocabulary on the map, so whether a colour-
blind reviewer can tell DISPUTED from CONFIRMED is a claim we publish. It used to
be quoted from an earlier run of the dataviz skill's validator with no raw output
kept. This script re-runs it and writes the result into docs/evidence/, like
every other number.

Colours are read from frontend/src/styles.css, not typed in here, so the
evidence describes the palette that actually ships. The light tokens come from
the first :root block, the dark tokens from :root[data-theme='dark'], and the
prefers-color-scheme block is checked to match the latter.

Three palettes are validated, all with --pairs all (a choropleth lets any two
statuses share a border, so every pair must separate, not just legend neighbours):

  filled    DISPUTED, UNCERTAIN, UNVERIFIABLE, CONFIRMED — the four statuses drawn
            with a fill. This is the palette the published CVD figures refer to.
  with_unseen  the same plus UNSEEN. UNSEEN is achromatic and drawn outline-only
            with no fill, so it fails the chroma floor by design; recorded so the
            exclusion above is visible rather than silent.
  retired   the green/red palette replaced in Phase 8, kept for correction record.

The validator is not part of this repository; it ships with Claude Code's
bundled dataviz skill. Point at it with --validator or KAVAL_PALETTE_VALIDATOR.

Run:  .venv/bin/python KAVAL/scripts/p8_validate_palette.py --validator <path/to/validate_palette.js>
Out:  docs/evidence/p8_palette.{json,md}
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval.config import EVIDENCE  # noqa: E402

CSS = Path(__file__).resolve().parents[1] / "frontend" / "src" / "styles.css"
FILLED = ["disputed", "uncertain", "unverifiable", "confirmed"]
RETIRED = {"light": "#0ca30c,#fab219,#d03b3b,#4a3aa7,#898781"}


def block(css, selector_regex):
    m = re.search(selector_regex + r"\s*\{(.*?)\n\s*\}", css, re.S)
    if not m:
        sys.exit(f"could not find CSS block {selector_regex!r} in {CSS}")
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", m.group(1)))


def run(validator, hexes, mode, surface):
    cmd = ["node", str(validator), ",".join(hexes), "--mode", mode,
           "--surface", surface, "--pairs", "all"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    raw = (p.stdout + p.stderr).strip()
    checks = {}
    for tag, name, detail in re.findall(r"\[(PASS|WARN|FAIL)\]\s+(.+?)\s{2,}(.*)", raw):
        checks[name.strip()] = {"verdict": tag, "detail": detail.strip()}
    cvd = re.search(r"CVD separation.*?ΔE ([\d.]+) \((\w+)\)", raw)
    nv = re.search(r"Normal-vision floor.*?ΔE ([\d.]+) \(normal\)", raw)
    return {"palette": hexes, "mode": mode, "surface": surface, "command": " ".join(cmd[1:]),
            "checks": checks,
            "worst_cvd_delta_e": float(cvd.group(1)) if cvd else None,
            "worst_cvd_type": cvd.group(2) if cvd else None,
            "normal_vision_floor_delta_e": float(nv.group(1)) if nv else None,
            "passed": "FAILED" not in raw, "raw": raw}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validator", default=os.environ.get("KAVAL_PALETTE_VALIDATOR"))
    a = ap.parse_args()
    if not a.validator or not Path(a.validator).exists():
        sys.exit("validate_palette.js not found. Pass --validator or set "
                 "KAVAL_PALETTE_VALIDATOR (it ships with the dataviz skill).")

    css = CSS.read_text()
    light = block(css, r"(?m)^:root")
    dark = block(css, r":root\[data-theme='dark'\]")
    media = block(css, r":root:where\(:not\(\[data-theme='light'\]\)\)")
    mismatch = {k: (dark.get(k), v) for k, v in media.items()
                if k.startswith("st-") and dark.get(k) != v}
    if mismatch:
        sys.exit(f"dark tokens differ between the media query and data-theme blocks: {mismatch}")

    ev = {"source_css": "KAVAL/frontend/src/styles.css", "validator": Path(a.validator).name,
          "pairs": "all", "results": {}}
    for mode, tok in (("light", light), ("dark", dark)):
        surface = tok["surface-1"]
        filled = [tok[f"st-{s}"] for s in FILLED]
        ev["results"][f"filled_{mode}"] = run(a.validator, filled, mode, surface)
        ev["results"][f"with_unseen_{mode}"] = run(
            a.validator, filled + [tok["st-unseen"]], mode, surface)
    ev["results"]["retired_light"] = run(
        a.validator, RETIRED["light"].split(","), "light", light["surface-1"])
    ev["status_order"] = FILLED

    (EVIDENCE / "p8_palette.json").write_text(json.dumps(ev, indent=2, ensure_ascii=False))
    L = ["# Phase 8 — Agreement-status palette, colour-vision check\n",
         f"Colours read from `{ev['source_css']}`. Validator `{ev['validator']}` "
         "(dataviz skill), `--pairs all`.\n",
         "| Palette | Mode | Worst CVD ΔE | Normal-vision floor ΔE | Result |",
         "|---|---|---:|---:|---|"]
    for key, r in ev["results"].items():
        warn = [n for n, c in r["checks"].items() if c["verdict"] == "WARN"]
        fail = [n for n, c in r["checks"].items() if c["verdict"] == "FAIL"]
        res = ("FAIL: " + ", ".join(fail)) if fail else (
            "pass" + (f" (warn: {', '.join(warn)})" if warn else ""))
        L.append(f"| {key} | {r['mode']} | {r['worst_cvd_delta_e']} ({r['worst_cvd_type']}) "
                 f"| {r['normal_vision_floor_delta_e']} | {res} |")
    L += ["", "`with_unseen` fails the chroma floor by design: UNSEEN is achromatic and "
              "drawn as an outline with no fill. `retired` is the green/red palette that "
              "Phase 8 replaced.", "", "## Raw validator output\n"]
    for key, r in ev["results"].items():
        L += [f"### {key}\n", "```", r["command"], r["raw"], "```", ""]
    (EVIDENCE / "p8_palette.md").write_text("\n".join(L))
    for key, r in ev["results"].items():
        print(f"{key:20} cvd={r['worst_cvd_delta_e']} ({r['worst_cvd_type']}) "
              f"nv={r['normal_vision_floor_delta_e']} passed={r['passed']}")


if __name__ == "__main__":
    main()
