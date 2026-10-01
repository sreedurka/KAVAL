# Phase 2e — FTW match detail

Recomputed read-only through `p2_ftw_delineate.py`'s own functions.

Strict match rate 36.4%; at the 20 m snap tolerance 73.3%.

## Per crop, strict containment

| Crop | Points | Match | Unmatched | Ambiguous |
|---|---:|---:|---:|---:|
| Groundnut | 16 | 62.5% | 37.5% | 0.0% |
| Sorghum | 30 | 56.7% | 43.3% | 0.0% |
| Sugarcane | 432 | 56.5% | 43.5% | 0.0% |
| Fodder Sorghum | 2 | 50.0% | 50.0% | 0.0% |
| Diploid Cotton (Paruththi) | 19 | 47.4% | 52.6% | 0.0% |
| Rice (Paddy) | 9,201 | 41.4% | 58.6% | 0.0% |
| Mango | 6 | 33.3% | 66.7% | 0.0% |
| Cassava | 24 | 29.2% | 70.8% | 0.0% |
| Banana | 655 | 27.5% | 72.5% | 0.0% |
| Maize | 1,563 | 25.9% | 74.1% | 0.0% |
| Coconut | 2,627 | 23.6% | 76.4% | 0.0% |
| Marigold | 36 | 13.9% | 86.1% | 0.0% |

## Unmatched points: distance to the nearest field

9,296 points: median **15.2 m**, p90 62.7 m; 58.0% within 20 m, 0.9% beyond 200 m.

## Layers

| Layer | Polygons | Hectares |
|---|---:|---:|
| raw | 64,708 | 13,061.9 |
| post_processed | 64,530 | 12,246.7 |
