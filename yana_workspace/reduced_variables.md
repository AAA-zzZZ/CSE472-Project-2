# Reduced Variable Set for the Flood Impact Model

This note narrows the impact model's inputs from 39 columns to **12 inputs plus 2 controls**, one per physical mechanism. Each input has a clear link to the output. Both the GLM hurdle and the LightGBM hurdle should be refit on this one set, which also fixes the open benchmark issue in `HANDOFF.md`: the GLM currently uses 17 inputs and the trees 39.

## 1. The equation

The course slides define the impact model as

$$
Y_{it} = \tau\left(W_{it};\; X_{i},\, C_{i}\right)
$$

Here $Y_{it}$ is the property loss of county $i$ in month $t$, $W$ is the hazard (how hard the flood hit), $X$ is exposure and susceptibility (what is in the way, and how easily it floods), and $C$ is the county's long-run rain climate.

**Causal target.** We want the effect of the hazard, not just its association with loss:

$$
\tau(w; x, c) = E\left[\,Y \mid do(W = w),\, X = x,\, C = c\,\right]
\quad\text{not}\quad E\left[\,Y \mid W, X\,\right]
$$

The backdoor path is $W \leftarrow C \rightarrow A \rightarrow Y$: counties with a wet climate get stronger storms *and* adapt more (wetlands, buyouts, insurance). So adaptation $A$ and climate $C$ are inputs even though they are not the hazard.

**How it is fitted: a hurdle model.** Most county-months (about 97%) have zero loss, so the model splits the expected loss into the chance of any damage and the size of the damage when there is some:

$$
E[Y_{it}] = \underbrace{\Pr(D_{it} = 1)}_{\text{part 1: any damage}} \times \underbrace{E[Y_{it} \mid D_{it} = 1]}_{\text{part 2: how much}}
$$

In the GLM version both parts share the same linear index of inputs:

$$
\text{Part 1:}\quad \operatorname{logit}\Pr(D_{it}=1) = \alpha_{s(i)} + \gamma_{m(t)} + \beta_W^{\top} W_{it} + \beta_C\, C_i + \beta_X^{\top} X_{i,y-1} + \beta_A\, A_{i,y-1}
$$

$$
\text{Part 2:}\quad E\left[\log_{10} Y_{it} \mid D_{it}=1\right] = \alpha'_{s(i)} + \gamma'_{m(t)} + \beta_W'^{\top} W_{it} + \beta'_C\, C_i + \beta_X'^{\top} X_{i,y-1} + \beta'_A\, A_{i,y-1}
$$

- $D_{it}$ = `has_damage`; $\log_{10} Y_{it}$ = `log_PropertyDmgADJ`
- $\alpha_{s(i)}$ = state effect, $\gamma_{m(t)}$ = calendar-month effect
- $y-1$ = the year before: yearly tables (land cover, census) use the previous year so every input is known before the month
- LightGBM keeps the same two parts and the same inputs, but replaces each linear index with a learned function $f(W, C, X, A, s, m)$, with monotone constraints on the hazard inputs.

## 2. The reduced variables

| Block | Variable | Meaning | Mechanism | Source | Timing |
|---|---|---|---|---|---|
| **W**, same month | `p_month` (log) | Monthly rain total | Sustained rain fills rivers (Davenport et al. 2021) | NOAA nClimGrid-Daily | Same month (perfect forecast) |
| | `rx5_rl_ratio` | Wettest 5 days ÷ county 10-year 5-day level | Short, intense bursts cause flash and urban flooding | nClimGrid-Daily | Same month |
| | `snowmelt_mm` (log) | Snowmelt in the month | Melt runoff (Berghuijs et al. 2016) | ERA5-Land | Same month |
| | `frost_days` | Days with Tmin < 0 °C | Frozen ground cannot absorb water | nClimGrid-Daily | Same month |
| **W**, known in advance | `sm_root_pct` | Root-zone soil wetness percentile vs 1950–1999 | Wet soil turns rain into runoff | ERA5-Land | Day 1 of the month |
| | `swe_mm` (log) | Snowpack water equivalent | Snow waiting to melt | ERA5-Land | Day 1 of the month |
| **C** | `c_rx5_rl10_mm` | 10-year 5-day rain level, 1951–1999 | Long-run rain climate: the confounder on W ← C → A → Y | nClimGrid-Daily | Static, before the study years |
| **X** | `log_housing_units` | Housing units (natural log) | Amount of property exposed | IPUMS NHGIS | Census year |
| | `impervious_mean` | Mean impervious (paved) % | Paved land sends rain straight to runoff | Annual NLCD | Year − 1 |
| | `hand_lt5_share` | Share of land < 5 m above nearest drainage | Floodplain: how much land sits low next to water | MERIT Hydro | Static |
| | `log_land_km2` | County land area (log) | Scale: bigger counties catch more storms | Census TIGER | Static |
| **A** | `wetland_share` | Wetland share of county | Natural storage that absorbs floodwater | Annual NLCD | Year − 1 |
| Controls | state | State indicator | Reporting differs by state (Iowa 7.9% vs Minnesota 2.2% damage months) | | |
| | calendar month | Month indicator | Seasonality | | |

"(log)" means the GLM uses log(x + 1), as `hurdle_model.py` already does. Trees use the raw column.

## 3. Dropped variables and why

Nothing is deleted from `model_panel.csv`. These columns are just no longer model inputs. The rule: when several columns measure the same mechanism, keep the one that is most direct and best supported in the literature. Near-duplicates make coefficients unstable in the GLM and split importance across copies in the trees, so neither model gives a clean input-to-output mapping.

### W: rain duplicates (7 dropped)

| Dropped | Kept instead | Why |
|---|---|---|
| `rx1`, `rx3`, `rx5` | `rx5_rl_ratio` | Wettest 1/3/5 days are near copies (Spearman 0.92–0.96 with `rx5_rl_ratio`). The ratio also scales the burst to what is extreme *for that county* |
| `n_gt_p95`, `n_gt_p99` | `p_month` | Counts of very wet days follow the monthly total |
| `rx5_gt_rl10` | `rx5_rl_ratio` | A yes/no flag of the same ratio passing 1; the continuous ratio keeps more information |
| `rain_x_wetsoil` | `rx5_rl_ratio`, `sm_root_pct` | It is their product. Trees learn interactions on their own; add it back to the GLM only as an explicit interaction term |

### W: soil and snow duplicates (7 dropped)

| Dropped | Kept instead | Why |
|---|---|---|
| `sm_surface`, `sm_root`, `sm_root_anom` | `sm_root_pct` | Same soil moisture in other forms. The percentile is comparable across counties with different soils |
| `spi1_prev`, `spi2_prev` | `sm_root_pct` | Rain in the previous 1–2 months shows up in the soil moisture at the start of the month |
| `snowmelt_prev_mm` | `swe_mm` | Last month's melt matters only through what is left on the ground |
| `frost_days_prev` | `frost_days` | Same frozen-ground signal, one month earlier |

### C: other climate thresholds (4 dropped)

| Dropped | Kept instead | Why |
|---|---|---|
| `c_wetday_p95_mm`, `c_wetday_p99_mm`, `c_rx5_rl2_mm`, `c_rx5_rl25_mm` | `c_rx5_rl10_mm` | All describe the same rain climate at different return periods. The 10-year level matches the hazard ratio's denominator |

### X: land cover and terrain (8 dropped)

| Dropped | Kept instead | Why |
|---|---|---|
| `urban_share`, `developed_share` | `impervious_mean` | Both track how built-up the county is. Impervious % is the part that changes runoff |
| `water_share`, `water_km2` | `hand_lt5_share` | Open water marks where flooding can happen. Land within 5 m of drainage measures it more directly |
| `elev_mean`, `slope_mean`, `flat_share`, `hand_mean` | `hand_lt5_share` | Elevation and slope describe the terrain broadly. Height above drainage is the standard floodplain measure |

### A: wetlands (1 dropped)

| Dropped | Kept instead | Why |
|---|---|---|
| `wetland_change_since_1999` | `wetland_share` | The level is what stores water; the change since 1999 is a second view of the same quantity |

**Total:** 27 dropped + 12 kept = 39, the full tree-model input list in `model_comparison.py`.

## 4. Points to raise with the team

1. **`rx5_rl_ratio` already contains C.** It is `rx5 / c_rx5_rl10_mm`, so W and C are linked by construction. That is fine for prediction. For the causal step (fixed effects with W × C, DML), use raw `rx5` as W and keep C separate.
2. **Same-month W assumes a perfect rain forecast.** Most of the skill comes from it: in `HANDOFF.md`, LightGBM's AUC is 0.886 with all inputs vs 0.769 using only inputs known in advance. Report both versions.
3. **A is thin.** `wetland_share` is the only adaptation input until the NFIP policies and HMA buyout tables are built. The census columns (`median_income`, `poverty_rate`, `mobile_home_share`, `built_pre1980_share`) are already in the panel and are the quickest way to give A real content.
4. **Next step:** refit `hurdle_model.py` and the LightGBM hurdle on exactly this list and compare against the 39-input results to show how much (if anything) the reduction costs.

## 5. Variable tree

Full page: [flood_model_variable_tree.html](flood_model_variable_tree.html) · PDF: [flood_model_variable_tree.pdf](flood_model_variable_tree.pdf) · Text version: [flood_model_variable_tree.md](flood_model_variable_tree.md)

<table>
  <thead>
    <tr>
      <th colspan="5" align="center">Y: county-month property loss<br><sub><code>has_damage</code> (part 1) × <code>log_PropertyDmgADJ</code> given damage (part 2) · SHELDUS, 2024 $</sub></th>
    </tr>
    <tr>
      <th>🟦 Hazard (W)<br><sub>6 inputs</sub></th>
      <th>🟪 Rain climate (C)<br><sub>1 input</sub></th>
      <th>🟧 Exposure &amp; susceptibility (X)<br><sub>4 inputs</sub></th>
      <th>🟩 Adaptation (A)<br><sub>1 input</sub></th>
      <th>⬜ Controls<br><sub>2 fixed effects</sub></th>
    </tr>
  </thead>
  <tbody>
    <tr valign="top">
      <td>
        <b>Same month</b><br>
        ├─ <code>p_month</code><br><sub>&nbsp;&nbsp;&nbsp;&nbsp;monthly rain (log)</sub><br>
        ├─ <code>rx5_rl_ratio</code><br><sub>&nbsp;&nbsp;&nbsp;&nbsp;5-day max ÷ 10-yr level</sub><br>
        ├─ <code>snowmelt_mm</code><br><sub>&nbsp;&nbsp;&nbsp;&nbsp;snowmelt (log)</sub><br>
        └─ <code>frost_days</code><br><sub>&nbsp;&nbsp;&nbsp;&nbsp;frozen ground</sub><br>
        <b>Known in advance</b><br>
        ├─ <code>sm_root_pct</code><br><sub>&nbsp;&nbsp;&nbsp;&nbsp;soil wetness pct.</sub><br>
        └─ <code>swe_mm</code><br><sub>&nbsp;&nbsp;&nbsp;&nbsp;snowpack (log)</sub>
      </td>
      <td>
        └─ <code>c_rx5_rl10_mm</code><br><sub>&nbsp;&nbsp;&nbsp;&nbsp;10-yr 5-day rain, 1951–1999</sub>
      </td>
      <td>
        ├─ <code>log_housing_units</code><br><sub>&nbsp;&nbsp;&nbsp;&nbsp;homes exposed</sub><br>
        ├─ <code>impervious_mean</code><br><sub>&nbsp;&nbsp;&nbsp;&nbsp;paved %, year − 1</sub><br>
        ├─ <code>hand_lt5_share</code><br><sub>&nbsp;&nbsp;&nbsp;&nbsp;land &lt; 5 m above drainage</sub><br>
        └─ <code>log_land_km2</code><br><sub>&nbsp;&nbsp;&nbsp;&nbsp;county size</sub>
      </td>
      <td>
        └─ <code>wetland_share</code><br><sub>&nbsp;&nbsp;&nbsp;&nbsp;water storage, year − 1</sub>
      </td>
      <td>
        ├─ <code>state</code><br><sub>&nbsp;&nbsp;&nbsp;&nbsp;reporting differences</sub><br>
        └─ calendar month<br><sub>&nbsp;&nbsp;&nbsp;&nbsp;seasonality</sub>
      </td>
    </tr>
    <tr valign="top">
      <td colspan="5"><b>Dropped:</b> <sub>W: <code>rx1</code> <code>rx3</code> <code>rx5</code> <code>n_gt_p95</code> <code>n_gt_p99</code> <code>rx5_gt_rl10</code> <code>rain_x_wetsoil</code> <code>sm_surface</code> <code>sm_root</code> <code>sm_root_anom</code> <code>spi1_prev</code> <code>spi2_prev</code> <code>snowmelt_prev_mm</code> <code>frost_days_prev</code> · C: <code>c_wetday_p95_mm</code> <code>c_wetday_p99_mm</code> <code>c_rx5_rl2_mm</code> <code>c_rx5_rl25_mm</code> · X: <code>urban_share</code> <code>developed_share</code> <code>water_share</code> <code>water_km2</code> <code>elev_mean</code> <code>slope_mean</code> <code>flat_share</code> <code>hand_mean</code> · A: <code>wetland_change_since_1999</code></sub></td>
    </tr>
    <tr valign="top">
      <td colspan="5"><b>Not used yet:</b> <sub>census/ACS <code>housing_units</code> <code>population</code> <code>median_value</code> (X), <code>median_income</code> <code>poverty_rate</code> <code>mobile_home_share</code> <code>built_pre1980_share</code> (A) · planned <code>policies_in_force</code> <code>buyouts_cum</code> <code>elevations_cum</code> (A), <code>soil_cd_share</code> (X)</sub></td>
    </tr>
  </tbody>
</table>
