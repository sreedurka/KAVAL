# Seasonal feature upgrade
The current CropSight package has only one annual 64-D Google Satellite Embedding. This folder adds a reproducible feature-acquisition experiment using official Earth Engine Sentinel-2 surface reflectance and Sentinel-1 GRD collections.

Sentinel-2 source: COPERNICUS/S2_SR_HARMONIZED. Sentinel-1 source: COPERNICUS/S1_GRD.

The script creates four seasonal NDVI features and four seasonal VV/VH composites, sampled over a fixed 30 m buffer around each ground-truth point. It does not replace the existing GSE model until the new features are validated with the same spatial blocks.
