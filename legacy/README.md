# Legacy: county-year pipeline

These scripts belong to the first design (one row per county per year, inputs
partly built from SHELDUS). They are kept so the results in the earlier
write-ups can be reproduced. The current design is county × month with SHELDUS
used only for the outcome; see `HANDOFF.md`.

Run from the repository root (the scripts read and write files there):

| # | Script | Writes |
|---|---|---|
| 1 | `python legacy/data_clean.py` | `loss_cleaned.csv` |
| 2 | `python legacy/build_features_DU.py` | `model_data_DU.csv` |
| 3 | `python hazard_features.py` | `model_data_hazard.csv`, `hazard_by_division.csv` |
| 4 | `python exposure_features.py` | `model_data_combined.csv`, `exposure_by_county_year.csv` |
| 5 | `python climatology_features.py` | `model_data_climatology.csv` |
| 6 | `python build_panel.py` | `model_data_panel.csv` |
| 7 | `python legacy/impact_model.py` | printed results (flooded county-years) |
| 8 | `python hurdle_model.py` | printed results (county-year panel) |

Steps 3–6 and 8 still live in the root folder until they are rebuilt for the
county-month design; their county-year versions will move here at that point.

`crop_dmg_regression.py` and `property_dmg_regression.py` are side
explorations that use `Records` and duration, which are only known after the
flood, so they are not forecasts.
