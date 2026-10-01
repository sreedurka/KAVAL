import argparse
from pathlib import Path

import pandas as pd


parser = argparse.ArgumentParser()
parser.add_argument("--seasonal", required=True)
parser.add_argument("--gse", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args()

seasonal_path = Path(args.seasonal)
gse_path = Path(args.gse)
out_path = Path(args.out)

print("Loading seasonal features...")
seasonal = pd.read_csv(seasonal_path)

print("Loading Google Satellite Embeddings...")
gse = pd.read_csv(gse_path)

KEY = "observation_id"

if KEY not in seasonal.columns:
    raise ValueError("Seasonal file does not contain observation_id")

if KEY not in gse.columns:
    raise ValueError("GSE file does not contain observation_id")

# Seasonal satellite features only.
seasonal_features = [
    "S1_NDVI", "S1_VH", "S1_VV",
    "S2_NDVI", "S2_VH", "S2_VV",
    "S3_NDVI", "S3_VH", "S3_VV",
    "S4_NDVI", "S4_VH", "S4_VV",
]

missing_features = [
    c for c in seasonal_features
    if c not in seasonal.columns
]

if missing_features:
    raise ValueError(
        f"Missing seasonal features: {missing_features}"
    )

# Check duplicate observation IDs before merging.
if seasonal[KEY].duplicated().any():
    raise ValueError("Seasonal file contains duplicate observation_id values")

if gse[KEY].duplicated().any():
    raise ValueError("GSE file contains duplicate observation_id values")

print(f"Seasonal rows: {len(seasonal):,}")
print(f"GSE rows: {len(gse):,}")

# Keep only the key and the 12 newly acquired features.
seasonal_small = seasonal[
    [KEY] + seasonal_features
].copy()

# One-to-one merge.
merged = gse.merge(
    seasonal_small,
    on=KEY,
    how="left",
    validate="one_to_one",
)

# Validate row count.
if len(merged) != len(gse):
    raise ValueError(
        f"Row count changed after merge: "
        f"{len(gse):,} -> {len(merged):,}"
    )

# Validate seasonal feature completeness.
missing_fraction = (
    merged[seasonal_features]
    .isna()
    .mean()
    .sort_values(ascending=False)
)

print("\nMissing fraction by seasonal feature:")
print(missing_fraction.to_string())

if missing_fraction.max() > 0:
    raise ValueError(
        "Seasonal features contain missing values."
    )

# Validate finite numeric values.
for feature in seasonal_features:
    if not pd.api.types.is_numeric_dtype(merged[feature]):
        raise ValueError(
            f"{feature} is not numeric"
        )

    if not merged[feature].map(
        lambda x: pd.notna(x) and pd.api.types.is_number(x)
    ).all():
        raise ValueError(
            f"{feature} contains non-numeric values"
        )

# Save.
out_path.parent.mkdir(parents=True, exist_ok=True)
merged.to_csv(out_path, index=False)

print("\n" + "=" * 60)
print("MERGE SUCCESSFUL")
print("=" * 60)

print(f"Output: {out_path}")
print(f"Rows: {len(merged):,}")
print(f"Columns: {len(merged.columns):,}")
print(f"GSE dimensions: 64")
print(f"Seasonal dimensions: {len(seasonal_features)}")
print(f"Combined model features: {64 + len(seasonal_features)}")
print("Duplicate observation IDs: 0")
print("Missing seasonal values: 0")
print("=" * 60)