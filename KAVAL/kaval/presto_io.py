"""
KAVAL - Presto loader and input builder.  Contract documented in docs/PRESTO_NOTES.md.

Why this module exists
  * `pip install presto` (nasaharvest/presto @ 11e207a, MIT) drags in earthengine-api,
    openmapflow, cropharvest, webdataset ... at `import presto` time, all pinned to
    2023 versions that would downgrade numpy/torch in the shared venv. We install the
    package with `--no-deps` and satisfy those import-time-only names with inert stubs.
    They are used for Presto's own GEE download pipelines, which KAVAL never calls.
    The stub finder sits LAST on sys.meta_path, so a real installed module always wins.
  * `Presto.load_pretrained()` looks for `<site-packages>/../data/default_model.pt`,
    which does not exist for a non-editable install. We load the checkpoint from
    KAVAL/models/presto/default_model.pt explicitly instead.
  * Do NOT use upstream `single_file_presto.py`: its mask_tokens asserts that every row
    of a batch has the same number of masked tokens, which real cloud-gapped pixels never do.
"""

import importlib.abc
import importlib.machinery
import sys
from unittest.mock import MagicMock

import numpy as np

from .config import MODELS

CHECKPOINT = MODELS / "presto" / "default_model.pt"
_STUB_ROOTS = ("ee", "openmapflow", "rioxarray", "xarray", "google", "hurry", "webdataset",
               "cropharvest", "wandb", "h5py", "matplotlib")

# Band order Presto's encoder consumes (NORMED_BANDS in upstream s1_s2_era5_srtm.py).
PRESTO_BANDS = ["VV", "VH", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12",
                "temperature_2m", "total_precipitation", "elevation", "slope", "NDVI"]
N_BANDS = len(PRESTO_BANDS)          # 17
DW_MISSING = 9                        # Dynamic World "no data" token
EMBED_DIM = 128
DAYS_PER_TIMESTEP = 30                # pretraining cadence (openmapflow.bands)


class _Stub(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in _STUB_ROOTS:
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
        return None

    def create_module(self, spec):
        m = MagicMock()
        m.__path__, m.__name__, m.__spec__ = [], spec.name, spec
        return m

    def exec_module(self, module):
        pass


def _import_presto():
    if not any(isinstance(f, _Stub) for f in sys.meta_path):
        sys.meta_path.append(_Stub())       # LAST: real modules take precedence
    import presto
    return presto


def load_presto(checkpoint=CHECKPOINT):
    """Return the pretrained encoder-decoder in eval mode (CPU). Use `.encoder` to embed."""
    import torch
    presto = _import_presto()
    model = presto.Presto.construct()       # defaults == config/default.json == checkpoint
    sd = torch.load(checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(sd)               # strict: raises on any key mismatch
    return model.eval()


def build_inputs(s1_db=None, s2_dn=None, era5_temp_k=None, era5_precip_m=None,
                 srtm_elev_m=None, srtm_slope_deg=None):
    """Assemble (x, mask, dynamic_world) tensors from raw-unit arrays.

    Every array is [N, T, ...]. Units are the RAW ones, normalisation is applied here:
      s1_db          [N,T,2]  VV, VH backscatter in dB
      s2_dn          [N,T,10] B2 B3 B4 B5 B6 B7 B8 B8A B11 B12 as reflectance x 10000
      era5_temp_k    [N,T]    2 m air temperature, kelvin
      era5_precip_m  [N,T]    total precipitation over the 30-day step, metres
      srtm_elev_m / srtm_slope_deg [N] or [N,T]  static, metres / degrees
    NaN entries are converted to masked (mask == 1) tokens.
    """
    import torch
    presto = _import_presto()
    n, t = next(a for a in (s1_db, s2_dn, era5_temp_k, era5_precip_m) if a is not None).shape[:2]
    kw = {}

    def add(prefix, arr, bands):
        if arr is None:
            return
        kw[prefix], kw[f"{prefix}_bands"] = torch.as_tensor(arr, dtype=torch.float32), bands

    add("s1", s1_db, ["VV", "VH"])
    add("s2", s2_dn, ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"])
    if era5_temp_k is not None or era5_precip_m is not None:
        cols, bands = [], []
        if era5_temp_k is not None:
            cols.append(np.asarray(era5_temp_k)); bands.append("temperature_2m")
        if era5_precip_m is not None:
            cols.append(np.asarray(era5_precip_m)); bands.append("total_precipitation")
        add("era5", np.stack(cols, -1), bands)
    if srtm_elev_m is not None or srtm_slope_deg is not None:
        def tile(a):
            a = np.asarray(a, dtype=np.float32)
            return np.repeat(a[:, None], t, 1) if a.ndim == 1 else a
        cols, bands = [], []
        if srtm_elev_m is not None:
            cols.append(tile(srtm_elev_m)); bands.append("elevation")
        if srtm_slope_deg is not None:
            cols.append(tile(srtm_slope_deg)); bands.append("slope")
        add("srtm", np.stack(cols, -1), bands)

    # NaN -> masked. Upstream builder masks by band GROUP only, so handle NaN ourselves.
    nan_any = {k: torch.isnan(v) for k, v in kw.items() if not k.endswith("_bands")}
    for k in nan_any:
        kw[k] = torch.nan_to_num(kw[k], nan=0.0)
    x, mask, dw = presto.construct_batch_presto_input(**kw)
    # Per-band mask for NaNs, mapped onto the 17-band layout.
    m_map = {"s1": ["VV", "VH"], "s2": ["B2", "B3", "B4", "B5", "B6", "B7", "B8", "B8A", "B11", "B12"],
             "era5": ["temperature_2m", "total_precipitation"], "srtm": ["elevation", "slope"]}
    for k, nanm in nan_any.items():
        for j, b in enumerate(kw[f"{k}_bands"]):
            if b in PRESTO_BANDS:
                mask[:, :, PRESTO_BANDS.index(b)] = torch.maximum(
                    mask[:, :, PRESTO_BANDS.index(b)], nanm[:, :, j].float())
    if "B8" in kw.get("s2_bands", []) and "B4" in kw.get("s2_bands", []):
        both = torch.maximum(mask[:, :, PRESTO_BANDS.index("B8")], mask[:, :, PRESTO_BANDS.index("B4")])
        mask[:, :, PRESTO_BANDS.index("NDVI")] = both
    # upstream returns dynamic_world as FLOAT when none is given; nn.Embedding needs long.
    return x, mask, dw.long()


def embed(model, x, mask, dw, latlons, start_month, batch_size=4096):
    """Mean-pooled 128-d encoder embedding per row -> float32 ndarray [N,128].

    latlons  [N,2] (lat, lon) degrees.   start_month  int 0..11, 0 == January, calendar
    month of timestep 0 (November -> 10).
    """
    import torch
    out = []
    with torch.no_grad():
        for i in range(0, len(x), batch_size):
            sl = slice(i, i + batch_size)
            out.append(model.encoder(x[sl], dw[sl], torch.as_tensor(latlons[sl], dtype=torch.float32),
                                     mask[sl], month=int(start_month), eval_task=True))
    return torch.cat(out).numpy()
