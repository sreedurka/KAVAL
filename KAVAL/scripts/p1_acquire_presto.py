"""
KAVAL / Phase 1 - Presto pretrained checkpoint (nasaharvest/presto, MIT).

Downloads default_model.pt and LICENSE from a PINNED commit, checks the checkpoint
loads (strict state-dict match) and runs a smoke forward pass, records provenance.

Install of the code itself (done once, NOT part of this script):
    uv pip install --python .venv/bin/python einops
    uv pip install --python .venv/bin/python --no-deps git+https://github.com/nasaharvest/presto@<COMMIT>
(--no-deps: upstream pins numpy==1.23.5, torch==2.0, earthengine-api etc. See kaval/presto_io.py.)

Run:  .venv/bin/python KAVAL/scripts/p1_acquire_presto.py
"""

import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaval import provenance  # noqa: E402
from kaval.config import EVIDENCE, MODELS  # noqa: E402
from kaval import presto_io  # noqa: E402

COMMIT = "11e207a668a34336ced1d8e492a1bd5849b96c4a"
RAW_URL = f"https://raw.githubusercontent.com/nasaharvest/presto/{COMMIT}"
DEST = MODELS / "presto"
LICENCE_NOTE = ("MIT License, Copyright (c) 2024 Presto Authors (repo LICENSE at the pinned commit). "
                "The repo states no separate licence for the weights; they are distributed inside "
                "the MIT-licensed repository. Preserve the LICENSE file when redistributing. "
                "Cite Tseng et al., 'Lightweight, Pre-trained Transformers for Remote Sensing "
                "Timeseries' (arXiv:2304.14065).")


def get(name, dest):
    req = urllib.request.Request(f"{RAW_URL}/{name}", headers={"User-Agent": "kaval"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
    if name.endswith(".pt") and not body.startswith(b"PK"):
        raise RuntimeError("checkpoint is not a torch zip (Git LFS pointer or HTML?)")
    dest.write_bytes(body)


def main():
    import torch
    DEST.mkdir(parents=True, exist_ok=True)
    get("data/default_model.pt", DEST / "default_model.pt")
    get("LICENSE", DEST / "LICENSE")

    model = presto_io.load_presto()
    n_params = sum(p.numel() for p in model.parameters())
    n_enc = sum(p.numel() for p in model.encoder.parameters())
    torch.manual_seed(0)
    x = torch.randn(3, 12, presto_io.N_BANDS) * 0.3
    dw = torch.full((3, 12), presto_io.DW_MISSING)
    mask = torch.zeros(3, 12, presto_io.N_BANDS)
    z = presto_io.embed(model, x, mask, dw, [[8.9, 77.4]] * 3, start_month=10)
    ok = z.shape == (3, presto_io.EMBED_DIM) and bool(torch.isfinite(torch.as_tensor(z)).all())

    for f, kind in (("default_model.pt", "ACQUIRED"), ("LICENSE", "ACQUIRED")):
        provenance.record(
            DEST / f, classification=kind, agent="data-acquisition",
            source=f"{RAW_URL}/{'data/' if f.endswith('.pt') else ''}{f} "
                   f"(github.com/nasaharvest/presto @ {COMMIT})",
            licence=LICENCE_NOTE, produced_by="KAVAL/scripts/p1_acquire_presto.py",
            spatial_extent="global (pretrained on 2020-2021 global samples)",
            temporal_extent="pretraining 2020-2021", crs="n/a",
            notes=("Pretrained encoder-decoder state dict, 128-d, 2-layer encoder. Loaded and "
                   "smoke-tested; input contract in KAVAL/docs/PRESTO_NOTES.md.") if f.endswith(".pt") else "")

    ev = {"date": date.today().isoformat(), "commit": COMMIT, "checkpoint_loads": True,
          "params_total": n_params, "params_encoder": n_enc, "embedding_shape": list(z.shape),
          "smoke_forward_finite": ok,
          "note": "Presto NOT yet run over parcels; awaits Sentinel time series."}
    (EVIDENCE / "p1_presto_checkpoint.json").write_text(json.dumps(ev, indent=2))
    print(json.dumps(ev, indent=2))
    if not ok:
        sys.exit("smoke test failed")


if __name__ == "__main__":
    main()
