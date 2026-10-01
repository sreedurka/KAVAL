"""
KAVAL / Phase 1 - Tamil Nadu crop-area registry acquisition (no GEE needed).

Sources, in order of granularity:

  1. VILLAGE  TN Dept. of Agriculture - Agrisnet, Digital Crop Survey (DCS) report,
              village-wise, Tenkasi / Sivagiri taluk. Seasons published: Rabi 2024,
              Summer 2025, Kharif 2025.
              https://www.tnagrisnet.tn.gov.in/ARS/dcs/reportVillageWise/<season>/Tenkasi/Sivagiri
  2. TALUK    same portal, taluk-wise (Agriculture + Horticultural), all Tenkasi taluks.
  3. DISTRICT same portal, district-wise (Tenkasi row).
  4. DISTRICT TN Dept. of Economics & Statistics, Statistical Hand Book of Tamil Nadu
              2022-23, table 4.4 (annual, all seasons; Paddy, Maize, Sugarcane only).

INDEPENDENCE CAVEAT (carried into the CSV and the evidence JSON): sources 1-3 are the
aggregated OUTPUT of the same Digital Crop Survey whose parcel-level sample FarmwiseAI
supplied as ground truth. They are the official declared area, not an independent
measurement. A satellite-vs-registry delta is therefore an audit of the DCS against
satellite, which is the KAVAL thesis, but it is NOT validation against a second survey.
Source 4 is a different programme (DES revenue-record area statistics) but district-level
and a different year.

Terms: neither portal publishes a licence or terms-of-use page that we could retrieve
(tnagrisnet /home/terms -> 404, des.tn.gov.in returned HTTP 500 on every attempt, no
robots.txt on tnagrisnet). Recorded as "no licence stated; public government statistics".
Data is used for internal analysis only; do not redistribute the raw snapshots without
confirming terms.

Run:  .venv/bin/python KAVAL/scripts/p1_acquire_registry.py [--offline]
      --offline re-parses the cached snapshots in data/raw/tn_registry_src/ (no network).
"""

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval import provenance  # noqa: E402
from kaval.config import EVIDENCE, RAW  # noqa: E402

SRC_DIR = RAW / "tn_registry_src"
OUT_CSV = RAW / "tn_crop_registry.csv"
EVID = EVIDENCE / "p1_registry_acquisition.json"
BASE = "https://www.tnagrisnet.tn.gov.in/ARS/dcs"
DES_PDF_URL = "https://www.des.tn.gov.in/sites/default/files/2025-07/4.%20AGRICULTURE.pdf"
DISTRICT, TALUK = "Tenkasi", "Sivagiri"
UA = "Mozilla/5.0 (KAVAL data-acquisition; research use)"
TIMEOUT = 90
RETRIES = 3

# The five evaluable classes (leakage-protocol MIN_EVENTS_PER_CLASS). Only exact,
# unambiguous matches map. "Fodder Maize", "Sweet corn" etc. deliberately do NOT.
CROP_MAP = {"Rice (Paddy)": "Rice (Paddy)", "Paddy": "Rice (Paddy)", "Coconut": "Coconut",
            "Maize": "Maize", "Banana": "Banana", "Sugarcane": "Sugarcane"}
EVALUABLE = {"Rice (Paddy)", "Coconut", "Maize", "Banana", "Sugarcane"}

FIELDS = ["level", "district", "taluk", "village", "crop", "crop_source_name",
          "evaluable_class", "crop_type", "season", "year", "area_ha", "source_dataset",
          "source_url", "retrieved_on"]


# ------------------------------------------------------------------ fetch ------
def fetch(url, dest: Path, offline=False):
    if offline:
        return dest.read_bytes()
    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = r.read()
            if dest.suffix == ".html" and b"<table" not in body:
                raise ValueError("HTTP 200 but no <table> in body (HTML where data promised)")
            if dest.suffix == ".pdf" and not body.startswith(b"%PDF"):
                raise ValueError("not a PDF")
            dest.write_bytes(body)
            return body
        except Exception as exc:                                   # noqa: BLE001
            last = exc
            time.sleep(2 * attempt)
    raise RuntimeError(f"{url}: {last}")


# ------------------------------------------------------------------ parse ------
class TableParser(HTMLParser):
    """Stdlib table + h2 extractor (no bs4 dependency)."""

    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell = [], None, None
        self.h2, self._in_h2 = "", False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "h2":
            self._in_h2 = True

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
        elif tag == "h2":
            self._in_h2 = False

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        if self._in_h2:
            self.h2 += data


def parse_html(body: bytes):
    p = TableParser()
    p.feed(body.decode("utf-8", "replace"))
    m = re.search(r"(Rabi|Kharif|Summer)\s+(\d{4})", p.h2)
    if not m:   # e.g. Kharif taluk pages ship an empty <h2>; caller resolves from the URL id
        return p.rows, None, None
    return p.rows, m.group(1), int(m.group(2))


def num(s):
    s = s.replace(",", "").strip()
    return float(s) if s not in ("", "-") else 0.0


def row(level, dist, taluk, village, crop_src, ctype, season, year, area, ds, url, today):
    crop = CROP_MAP.get(crop_src, crop_src)
    return dict(level=level, district=dist, taluk=taluk, village=village, crop=crop,
                crop_source_name=crop_src, evaluable_class=crop in EVALUABLE,
                crop_type=ctype, season=season, year=year, area_ha=round(area, 3),
                source_dataset=ds, source_url=url, retrieved_on=today)


SEASON_BY_ID = {}   # url season id -> (season, year); learned from pages that DO print it


def resolve_season(url, season, year):
    sid = int(re.search(r"/(?:reportVillageWise|reportTalukWise|reportDistrictWise)/(\d)/", url).group(1))
    if season:
        prev = SEASON_BY_ID.setdefault(sid, (season, year))
        if prev != (season, year):
            raise ValueError(f"season id {sid} maps to both {prev} and {(season, year)}")
        return season, year
    if sid not in SEASON_BY_ID:
        raise ValueError(f"season id {sid} never printed by any page; cannot label")
    return SEASON_BY_ID[sid]


def parse_village(body, url, today, checks):
    rows, season, year = parse_html(body)
    season, year = resolve_season(url, season, year)
    out, totals, seen = [], {}, {}
    for r in rows:
        if len(r) == 4 and r[0] != "Village":
            out.append(row("village", DISTRICT, TALUK, r[0], r[2], r[1], f"{season} {year}",
                           year, num(r[3]), "TN Agrisnet DCS village-wise", url, today))
            seen[r[0]] = seen.get(r[0], 0) + num(r[3])
        else:
            m = re.match(r"Total for (.+?):\s*([\d,\.]+)", " ".join(r))
            if m:
                totals[m.group(1)] = num(m.group(2))
    bad = {v: (round(seen.get(v, 0), 1), t) for v, t in totals.items()
           if abs(seen.get(v, 0) - t) > 0.15}
    checks[f"village_sum_vs_source_total_{season}_{year}"] = {
        "villages_with_source_total": len(totals), "mismatches": bad}
    return out


def parse_wide(body, level, url, today, ctype, checks, key):
    """Taluk / district pages: one row per taluk (district), one column per crop."""
    rows, season, year = parse_html(body)
    season, year = resolve_season(url, season, year)
    header = next(r for r in rows if r and r[0] in ("Taluk", "District"))
    out = []
    for r in rows:
        if r is header or len(r) != len(header) or r[0] in ("Taluk", "District"):
            continue
        name = r[0]
        if re.match(r"(?i)total", name):
            continue
        if level == "district" and name != DISTRICT:
            continue
        for crop_src, cell in zip(header[1:], r[1:]):
            a = num(cell)
            if a > 0 and not re.match(r"(?i)total", crop_src):
                out.append(row(level, DISTRICT, name if level == "taluk" else "", "",
                               crop_src, ctype, f"{season} {year}", year, a,
                               f"TN Agrisnet DCS {level}-wise", url, today))
    checks[key] = {"rows": len(out)}
    return out, season, year


def parse_des(pdf_path: Path, today, checks):
    """Statistical Hand Book of TN 2022-23, table 4.4: Tenkasi row of Paddy/Maize/Sugarcane."""
    if not shutil.which("pdftotext"):
        checks["des_handbook"] = "SKIPPED: pdftotext not installed"
        return []
    txt = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True,
                         text=True, check=True).stdout
    start = txt.index("4.4 AREA UNDER PRINCIPAL CROPS BY DISTRICTS")
    end = txt.index("4.5 AREA UNDER PRINCIPAL CROPS AS PERCENTAGES")
    sect = txt[start:end]
    want = {"Rice (Paddy)": (r"Paddy\s+Wheat\s+Cholam", "Paddy"),
            "Maize": (r"Maize\s+.*Red gram|Maize\s+Other", "Maize"),
            "Sugarcane": (r"Sugar-", "Sugarcane")}
    out, found = [], {}
    for block in sect.split("Statistical Hand Book"):
        for label, (pat, src_name) in want.items():
            if label in found or not re.search(pat, block, re.S):
                continue
            if label == "Maize" and "Red gram" not in block:
                continue
            m = re.search(r"\n\s*35\.?\s+Tenkasi\s+(\d+)", block)
            if m:
                found[label] = int(m.group(1))
                out.append(row("district", DISTRICT, "", "", src_name, "Agriculture",
                               "Annual (all seasons)", 2022, found[label],
                               "DES Statistical Hand Book of Tamil Nadu 2022-23, table 4.4",
                               DES_PDF_URL, today))
                out[-1]["crop"] = CROP_MAP.get(src_name, src_name)
    checks["des_handbook"] = {"tenkasi_values_ha": found,
                              "note": "FY 2022-23, annual, not season-matched to Rabi 2024"}
    if set(found) != set(want):
        checks["des_handbook"]["warning"] = f"missing {set(want) - set(found)}"
    return out


# ------------------------------------------------------------------ main -------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="re-parse cached snapshots")
    args = ap.parse_args()
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    checks, failures, files, all_rows = {}, [], [], []

    jobs = []   # (url, dest, kind, extra)
    for s in (2, 1, 3):
        jobs.append((f"{BASE}/reportVillageWise/{s}/{DISTRICT}/{TALUK}",
                     SRC_DIR / f"village_s{s}_{DISTRICT}_{TALUK}.html", "village", None))
        for t in ("Agriculture", "Horticultural"):
            jobs.append((f"{BASE}/reportTalukWise/{s}/{DISTRICT}/{t}",
                         SRC_DIR / f"taluk_s{s}_{DISTRICT}_{t}.html", "taluk", t))
            jobs.append((f"{BASE}/reportDistrictWise/{s}/{t}",
                         SRC_DIR / f"district_s{s}_{t}.html", "district", t))
    jobs.append((DES_PDF_URL, SRC_DIR / "des_handbook_2022_23_agriculture.pdf", "des", None))

    for url, dest, kind, extra in jobs:
        try:
            body = fetch(url, dest, args.offline)
            files.append((dest, url))
            if kind == "village":
                all_rows += parse_village(body, url, today, checks)
            elif kind in ("taluk", "district"):
                rws, se, yr = parse_wide(body, kind, url, today, extra, checks,
                                         f"{kind}_{se_key(dest)}")
                all_rows += rws
            else:
                all_rows += parse_des(dest, today, checks)
            print(f"ok   {kind:8s} {url}")
        except Exception as exc:                                   # noqa: BLE001
            failures.append({"url": url, "error": str(exc)})
            print(f"FAIL {kind:8s} {url}: {exc}")

    if not all_rows:
        sys.exit("nothing acquired; see failures above")

    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(all_rows)

    # ---- provenance: every file written under data/ ----
    terms = ("No licence or terms-of-use statement found (tnagrisnet /home/terms is 404, no "
             "robots.txt; des.tn.gov.in returned HTTP 500 for its terms pages). Public "
             "Government of Tamil Nadu statistics. Treated as: attribute the source, internal "
             "analysis only, confirm terms before redistributing the raw snapshots.")
    for dest, url in files:
        provenance.record(
            dest, classification="ACQUIRED", source=url, licence=terms,
            produced_by="KAVAL/scripts/p1_acquire_registry.py",
            temporal_extent="Rabi 2024 / Summer 2025 / Kharif 2025 (DCS)"
            if "tnagrisnet" in url else "FY 2022-23 (DES Hand Book)",
            transform="none (raw snapshot as served)", agent="data-acquisition",
            notes="Raw snapshot kept so the CSV can be re-derived offline.")
    provenance.record(
        OUT_CSV, classification="DERIVED", agent="data-acquisition",
        source="Parsed from the snapshots in KAVAL/data/raw/tn_registry_src/ "
               "(TN Agrisnet DCS village/taluk/district reports; DES Statistical Hand Book 2022-23)",
        licence=terms, produced_by="KAVAL/scripts/p1_acquire_registry.py",
        inputs=[str(d.relative_to(RAW.parents[1])) for d, _ in files],
        temporal_extent="Rabi 2024 (aligned with the Nov-2024 survey), plus Summer/Kharif 2025",
        transform="HTML tables tidied to long format; crop names mapped to the five evaluable "
                  "classes ONLY on exact match, original wording kept in crop_source_name; "
                  "zero-area cells dropped; 'Total' rows dropped.",
        notes="Village level = 23 DCS village units for Sivagiri incl. 'Part-1/Part-2' splits "
              "that match Sivagiri_Villages.geojson vill_name exactly. NOT independent of the "
              "DCS ground truth: it is that survey's aggregate. See evidence JSON.")

    # ---- evidence ----
    import collections
    lv = collections.Counter(r["level"] for r in all_rows)
    rabi_v = [r for r in all_rows if r["level"] == "village" and r["season"] == "Rabi 2024"]
    ev = {
        "acquired_on": today, "output": str(OUT_CSV), "rows": len(all_rows),
        "rows_by_level": dict(lv), "failures": failures, "checks": checks,
        "village_rabi2024": {
            "villages": len({r["village"] for r in rabi_v}),
            "evaluable_area_ha": {c: round(sum(r["area_ha"] for r in rabi_v if r["crop"] == c), 1)
                                  for c in sorted(EVALUABLE)},
            "total_area_ha": round(sum(r["area_ha"] for r in rabi_v), 1)},
        "independence_caveat": "DCS aggregate; same programme as the supplied ground truth.",
        "licence": terms,
    }
    EVID.write_text(json.dumps(ev, indent=2))
    provenance.record(EVID, classification="DERIVED", agent="data-acquisition",
                      source="Evidence summary of the registry acquisition run",
                      licence="Project-internal", produced_by="KAVAL/scripts/p1_acquire_registry.py",
                      inputs=[str(OUT_CSV.relative_to(RAW.parents[1]))],
                      transform="counts and integrity checks")
    print(json.dumps({k: ev[k] for k in ("rows", "rows_by_level", "failures")}, indent=2))


def se_key(dest: Path):
    return dest.stem


if __name__ == "__main__":
    main()
