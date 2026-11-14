# Reduced Flood Model Variable Tree

The 12 inputs and 2 controls of the narrowed impact model, grouped by category. One variable per physical mechanism, and the same set feeds both the GLM hurdle and the LightGBM hurdle. The dropped inputs and the panel columns no model uses are listed below the tree.

Hazard (W) · Long-run rain climate (C) · Exposure and susceptibility (X) · Adaptation (A) · Controls

Interactive version: [flood_model_variable_tree.html](flood_model_variable_tree.html) · Printable version: [flood_model_variable_tree.pdf](flood_model_variable_tree.pdf)

## Tree

- **Y: county-month property loss** (`has_damage` for part 1, `log_PropertyDmgADJ` given damage for part 2; SHELDUS, 2024 $)
  - **Hazard (W)**: 6 inputs, nClimGrid-Daily and ERA5-Land
    - *Same month*
      - `p_month`: monthly rain total (log)
      - `rx5_rl_ratio`: wettest 5 days ÷ county 10-year 5-day level
      - `snowmelt_mm`: snowmelt in the month (log)
      - `frost_days`: days with Tmin < 0 °C (frozen ground)
    - *Known in advance (day 1 of the month)*
      - `sm_root_pct`: root-zone soil wetness percentile
      - `swe_mm`: snowpack water equivalent (log)
  - **Rain climate (C)**: 1 input, nClimGrid-Daily 1951–1999
    - `c_rx5_rl10_mm`: 10-year 5-day rain level (the confounder)
  - **Exposure and susceptibility (X)**: 4 inputs, NHGIS, Annual NLCD, MERIT Hydro, Census TIGER
    - `log_housing_units`: homes exposed
    - `impervious_mean`: paved share (runoff), year − 1
    - `hand_lt5_share`: share of land < 5 m above the nearest drainage
    - `log_land_km2`: county land area (scale)
  - **Adaptation (A)**: 1 input, Annual NLCD
    - `wetland_share`: natural water storage, year − 1
  - **Controls**: 2 fixed effects
    - `state`: reporting differences between states
    - calendar month: seasonality

## Dropped from the models

These columns stay in `model_panel.csv` but are no longer model inputs. Each repeats a kept variable, shown in parentheses.

### W: rain duplicates
- `rx1`, `rx3`, `rx5` (`rx5_rl_ratio`)
- `n_gt_p95`, `n_gt_p99` (`p_month`)
- `rx5_gt_rl10` (`rx5_rl_ratio`)
- `rain_x_wetsoil` (interaction of `rx5_rl_ratio` × `sm_root_pct`)

### W: soil and snow duplicates
- `sm_surface`, `sm_root`, `sm_root_anom` (`sm_root_pct`)
- `spi1_prev`, `spi2_prev` (`sm_root_pct`)
- `snowmelt_prev_mm` (`swe_mm`)
- `frost_days_prev` (`frost_days`)

### C: other thresholds
- `c_wetday_p95_mm`, `c_wetday_p99_mm`, `c_rx5_rl2_mm`, `c_rx5_rl25_mm` (`c_rx5_rl10_mm`)

### X: land cover and terrain
- `urban_share`, `developed_share` (`impervious_mean`)
- `water_share`, `water_km2` (`hand_lt5_share`)
- `elev_mean`, `slope_mean`, `flat_share`, `hand_mean` (`hand_lt5_share`)

### A: wetlands
- `wetland_change_since_1999` (`wetland_share`)

## Census and ACS (in the panel, unused)

- housing_units (X)
- population (X)
- median_value (X)
- median_income (A candidate)
- poverty_rate (A candidate)
- mobile_home_share (A candidate)
- built_pre1980_share (A candidate)

## Planned, not built yet

- policies_in_force (A)
- buyouts_cum (A)
- elevations_cum (A)
- soil_cd_share (X)

The outcome (`PropertyDmgADJ`, `log_PropertyDmgADJ`, `has_damage`) and the keys (`GEOID`, `year`, `split`) are left out of the tree. Labels follow `HANDOFF.md`: C is rain climate, and terrain is susceptibility, so it sits in X.
