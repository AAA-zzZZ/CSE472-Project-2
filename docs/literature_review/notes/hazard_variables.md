# Hazard (W) variables for predicting county x month property flood loss (Midwest, 2000-2023)

> Method note: In this session WebFetch was blocked for almost every host (pmc.ncbi.nlm.nih.gov, pnas.org, arxiv.org, core.ac.uk, developers.google.com all failed DNS resolution through the sandbox proxy). All findings below come from search-engine result pages and snippets that cite the listed URLs; I did NOT open the full texts. The report writer should treat effect sizes as "as reported in abstract/summary" and should verify Earth Engine end dates on the live catalog. To fetch these sites, the user has to allow those domains in the session's network settings.

## Q1. Which hazard variables do empirical flood-loss studies find most predictive (US, county/state level; SHELDUS, NFIP, Storm Events)?

### Takeaway
The strongest US evidence that links hazard variables to economic flood damages is Davenport, Burke and Diffenbaugh (2021, PNAS). In a state x month panel with fixed effects, both monthly precipitation and 5-day maximum precipitation had significant positive effects on damages. Most of the damage came from the extremely wet upper quantiles. NFIP-claims machine-learning studies also find that adding rainfall improves prediction. The best of them (iClaim) also uses flood extent, river stage and water levels. I found no SHELDUS county study that ranks hazard variables directly: the SHELDUS county studies treat precipitation as a control.

### Cited Findings
- **Davenport, Burke and Diffenbaugh (2021), "Contribution of historical precipitation change to US flood damages," PNAS 118(4) e2017524118, doi:10.1073/pnas.2017524118.**
  - They link precipitation to damage using more than 6,600 state-level flood-damage reports. Both monthly and 5-day state-level precipitation had significant positive effects on state flood damage.
  - Historical precipitation change accounts for about 36% (95% CI 20–46%) of cumulative US flood damages over 1988–2017, or $73B (95% CI $39–91B). Total damages over the period were about $199B.
  - Anthropogenic forcing has raised the probability of exceeding the "extremely wet quantiles that are responsible for most flood damages."
  - Attribution is more uncertain at finer spatial scales because climate variability has more influence there.
  - Sources: [PMC full text (search-indexed)](https://pmc.ncbi.nlm.nih.gov/articles/7848586/); [Stanford News](https://news.stanford.edu/stories/2021/01/climate-change-caused-one-third-historical-flood-damages); [CA Water Library abstract](https://cawaterlibrary.net/document/contribution-of-historical-precipitation-change-to-us-flood-damages/)
  - The damage source is believed to be NCEI Storm Events, aggregated to state, but I could not open the text to confirm it.
- **Earlier AGU abstract by the same group (Davenport et al., 2019).** Panel fixed-effects regressions of monthly precipitation on flood damages across US states, 1960–2017, found a significant log-linear relationship whose strength varies by region. It attributes the damage increase to changes in the upper tail of the precipitation distribution, with a median of about $80B (95% range $30–100B) due to increased precipitation. — [ADS abstract 2019AGUFMGC23A..02D](https://ui.adsabs.harvard.edu/abs/2019AGUFMGC23A..02D)
- **Salas, Saha and Ravela (2022), "Learning Inter-Annual Flood Loss Risk Models From Historical Flood Insurance Claims and Extreme Rainfall Data," arXiv:2212.08660, doi:10.48550/arXiv.2212.08660.**
  - Uses NFIP claim amounts and compares neural-network, gradient-boosting (XGBoost was best) and Gaussian-process regressors.
  - Adding Daymet rainfall as a predictor improved performance across 11 counties, with R² = 0.807 reported for coastal counties.
  - Source: [arXiv](https://doi.org/10.48550/arXiv.2212.08660); [MIT Climate Extremes page](https://www.climate-extremes.mit.edu/publicationslist/publications1-dxd6x)
- **iClaim (Yang et al., BAMS 2022, "Predicting Flood Property Insurance Claims over CONUS, Fusing Big Earth Observation Data").**
  - A random forest on NFIP records. Inputs are building location, topography, basin morphometry and land cover, plus hydrometeorological inputs: flood extent, precipitation, river stage and water levels.
  - Reported R² is above 0.5 at the grid/event level and above 0.9 at the county/event level.
  - Source: [NOAA repository](https://repository.library.noaa.gov/view/noaa/64559); [CU Experts](https://experts.colorado.edu/display/pubid_318327)
- **Random-forest study of riverine NFIP claims ("Predicting flood insurance claims with hydrologic and socioeconomic demographics via machine learning").** Mostly static hydrologic features best predicted claims: distance to the nearest stream and topographic wetness index. These are exposure/susceptibility features rather than time-varying hazard. — [ResearchGate](https://www.researchgate.net/publication/342973658_Predicting_flood_insurance_claims_with_hydrologic_and_socioeconomic_demographics_via_machine_learning_Exploring_the_roles_of_topography_minority_populations_and_political_dissimilarity)
- **County-level SHELDUS flood-damage study (PMC8492007).** The dependent variable is log three-year property damage per capita from SHELDUS. Mean annual PRISM precipitation enters only as a control, not as an extreme-rainfall predictor. — [PMC table](https://pmc.ncbi.nlm.nih.gov/articles/PMC8492007/table/T1)
- **Spekkers et al. (2013), HESS 17:913, Dutch insurance claims.** The strongest correlation was between rainfall intensity and the number of damage claims, which was stronger than for damage amounts. — [HESS metrics page](https://www.hydrol-earth-syst-sci.net/17/913/2013/hess-17-913-2013-metrics.html); summarized in [search result](https://typeset.io/pdf/a-statistical-analysis-of-insurance-damage-claims-related-to-5aplcasf6n.pdf)
- **Pluvial share of US claims.** Pluvial flooding caused 74% of tropical-cyclone (TC) and 60% of non-TC flood-insurance claims in the US (2022 study, as summarized in search results). The original paper was not identified. — [search summary via CAS catalog, "Evaluating the Risk and Complexity of Pluvial Flood Damage in the U.S."](https://katalog.lib.cas.cz/KNAV/EdsRecord/edsair,edsair.doi...........4401c008941e0332c6a7e0609cebdf3d)
- **Collinearity.** A claims-estimation pipeline reported a correlation of 0.71 between precipitation and soil moisture and built orthogonal moisture indices with PCA. — [PMC13312540](https://pmc.ncbi.nlm.nih.gov/articles/PMC13312540/)
- **Rözer et al. (2019), Earth's Future 7:384–394, doi:10.1029/2018EF001074.** A probabilistic (beta) loss model for Hurricane Harvey pluvial losses cut the 90% prediction interval by $3.8B (78%). The paper is about uncertainty in loss models, not a ranking of hazard variables. — [DDB record](https://www.deutsche-digitale-bibliothek.de/item/MMVXZ7LYVK2Z27PVQXK6AP6YR2RYEJYE?lang=en)
- **Highfield and Brody (CRS studies).** These are about mitigation and exposure, not hazard.
  - Community Rating System (CRS) communities had about 50% lower insured losses per year.
  - Freeboard and open-space protection were the most effective activities (community-level study, 1999–2009).
  - Source: [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S2212420916303983)
- **Climate Central summary of US inland-flood drivers:** multi-day precipitation, intense short-duration rainfall, rapid snowmelt, river debris, and dam/levee failure. It cites about $230B in inland flood damage from 1988 to 2021, with 37% attributable to precipitation change. — [Climate Central](https://www.climatecentral.org/climate-matters/climate-change-and-inland-flooding)
- **Muriqi et al. (2025), ERL review, doi:10.1088/1748-9326/add35e.** "Inland flooding in the United States: a review of research related to risk management, economic behavior, and data resources." It calls for datasets that combine economic, flood and policy variables. I saw only an abstract. — [IOP PDF (search-indexed)](https://iopscience.iop.org/article/10.1088/1748-9326/add35e/pdf)

### Inferences
- For a county x month SHELDUS model, the best-supported hazard core is:
  - monthly total precipitation;
  - maximum 1-day, 3-day and 5-day precipitation within the month, or exceedance of a high local percentile (e.g. above the county's 95th or 99th percentile of 5-day totals);
  - antecedent wetness (see Q3);
  - river stage or streamflow exceedance where available.
- Davenport et al. found a log-linear damage–precipitation relationship. This suggests modelling log(1+loss) against precipitation, or against precipitation percentiles/anomalies relative to each county's own climatology, with county and month fixed effects.
- Static susceptibility (distance to stream, TWI, floodplain share) is strongly predictive in NFIP work. It belongs with exposure/vulnerability, not hazard, but should be included alongside W.

### Gaps
- I found no study using SHELDUS county x month losses that ranks hazard variables (precipitation vs soil moisture vs streamflow) by importance. This appears to be a genuine gap in the literature, or at least not findable via search snippets.
- I could not open Davenport et al. to extract coefficient magnitudes (e.g. % damage change per SD of precipitation) or Midwest-specific coefficients.
- No Brody/Highfield paper surfaced that uses precipitation-days variables in a county panel.
- No Gourley/FLASH or NCEI Storm Events study with effect sizes was retrieved.

## Q2. Monthly totals vs daily maxima (Rx1day/Rx3day/Rx5day) vs return-period exceedance — what does evidence favour?

### Takeaway
The US damage evidence supports including both a monthly total and a multi-day maximum (5-day), because each had an independent, significant effect (Davenport et al. 2021). Damage concentrates in the extreme upper quantiles, which favours percentile or return-period exceedance terms over raw linear amounts. Hydrological evidence from the Midwest shows that flood frequency responds to more frequent heavy rain, and that precipitation shortly before an event matters together with basin wetness.

### Cited Findings
- Monthly and 5-day state-level precipitation both had significant positive effects on state flood damages. The extremely wet quantiles are "responsible for most flood damages." — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/7848586/); [CA Water Library](https://cawaterlibrary.net/?p=29571)
- The increase in damage is attributed to changes in the upper tail of the precipitation distribution (monthly state panel, 1960–2017). — [ADS](https://ui.adsabs.harvard.edu/abs/2019AGUFMGC23A..02D)
- **Mallakpour and Villarini (2015), Nature Climate Change 5:250–254, "The changing nature of flooding across the central United States."**
  - 774 streamgages, 1962–2011, show significant increases in flood frequency but little evidence of larger flood peaks.
  - The authors preliminarily relate this to more frequent extreme rainfall events.
  - Source: [Nature](https://www.nature.com/articles/nclimate2516); [ResearchGate](https://www.researchgate.net/publication/272388509_The_changing_nature_of_flooding_across_the_central_United_States)
- Rainfall intensity correlated most strongly with the number of claims, more than with damage amount (Netherlands). — [Spekkers et al. 2013 HESS](https://www.hydrol-earth-syst-sci.net/17/913/2013/hess-17-913-2013-metrics.html)
- Berghuijs et al. (2016, GRL; 420 US catchments) found that rainfall characteristics alone explain flood timing and year-to-year magnitude poorly. Soil-moisture-dependent precipitation excess, snowmelt and rain-on-snow are much better predictors. — [Typeset PDF](https://typeset.io/pdf/dominant-flood-generating-mechanisms-across-the-united-10tztxaz7l.pdf); [EGU2016 abstract](https://meetingorganizer.copernicus.org/EGU2016/EGU2016-1874-1.pdf?pdf)

### Inferences
- A recommended feature set per county-month:
  - total precipitation (P_month);
  - Rx1day, Rx3day and Rx5day;
  - number of days above the county's 95th/99th daily percentile;
  - a binary or graded exceedance of a local return-period threshold, computed from a pre-2000 or training-period-only baseline to avoid leakage;
  - "precipitation excess" = P minus available soil storage, following Berghuijs.
- Tree-based models can absorb non-linear thresholds. A log-linear or fixed-effects model should use percentile and anomaly forms.
- Return-period thresholds from NOAA Atlas 14 are an option (Atlas 14 itself was not researched here). A simpler leakage-free alternative is percentiles from PRISM 1981–1999 daily data, or from 1895–1999 monthly data.

### Gaps
- No US damage study was found that directly compares Rx1day vs Rx3day vs Rx5day vs return-period exceedance in a head-to-head test.

## Q3. Role of antecedent conditions (soil moisture, previous-month rain, snowmelt) for Midwest floods

### Takeaway
Antecedent wetness and snowmelt are first-order drivers in the Midwest and arguably dominate peak rainfall. Across the US, soil-moisture excess and snowmelt/rain-on-snow predict annual floods better than rainfall alone. In the Midwest and Northeast, snowmelt or rain-on-snow on saturated soil was the leading generator. The March 2019 Missouri River flood is a canonical example: wet autumn, then deep frozen saturated soils, then the bomb cyclone's rain on snowpack.

### Cited Findings
- **Berghuijs, Woods, Hutton and Sivapalan (2016), GRL, "Dominant flood generating mechanisms across the United States" (420 catchments).** Soil-moisture-dependent precipitation excess, snowmelt and rain-on-snow are much better predictors of the seasonality and magnitude of annual maximum floods than rainfall characteristics. — [Typeset](https://typeset.io/pdf/dominant-flood-generating-mechanisms-across-the-united-10tztxaz7l.pdf); [EGU2016](https://meetingorganizer.copernicus.org/EGU2016/EGU2016-1874-1.pdf?pdf)
  - DOI from memory, not verified this session: 10.1002/2016GL068070.
- A CONUS machine-learning (circular-statistics) study found snowmelt or rain-on-snow on saturated soil to be the greatest contributor to local flood generation in the Midwest and northeastern CONUS. Globally, soil-moisture excess ranked as the most influential driver, ahead of extreme precipitation and snowmelt. — [Hydrology Research 54(10):1181](https://iwaponline.com/hr/article/54/10/1181/97601/Unveiling-flood-generating-mechanisms-using)
- **Slater and Villarini (2016), GRL, "Recent trends in U.S. flood risk," doi:10.1002/2016GL071199.**
  - Uses roughly 30 years of stage height above NWS flood thresholds.
  - Both the precipitation preceding events and overall basin wetness are critical drivers of flood frequency.
  - Cox regression on individual events modelled occurrence as a function of immediate precipitation plus annual wetness.
  - Source: [Wiley](https://agupubs.onlinelibrary.wiley.com/doi/10.1002/2016GL071199); [ResearchGate](https://www.researchgate.net/publication/310300165_Recent_trends_in_US_flood_risk)
- Neri et al. (2019, Adv. Water Resour.) cite a consensus that antecedent wetness is an important predictor of streamflow magnitude in the Midwest flood-frequency context. — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0309170818304391)
- Berghuijs et al. (2019, Europe): most annual floods are caused by sub-extreme precipitation falling on high antecedent soil moisture, not by annual peak rainfall. This is a European result. — summarized in [search results](https://pmc.ncbi.nlm.nih.gov/articles/PMC9832955)
- **2019 Missouri basin flood.**
  - Fall 2018 rainfall was above average, leaving soils saturated. Extreme winter cold then froze those near-saturated soils deeply. — [ASDSO](https://damsafety.org/reference/2019-missouri-river-basin-historic-flood-event)
  - October–December 2018 was the 12th wettest in 125 years. — [NCEI](https://www.ncei.noaa.gov/node/699)
  - Rain and above-freezing temperatures on snowpack and frozen soil caused rapid runoff. — [Iowa DNR](https://iowadnr.gov/About-DNR/DNR-News-Releases/ArticleID/2384/Water-Summary-Update-Rapid-runoff-led-to-historic-flooding-in-March)
  - Ice jams backed up water. — [NASA Earth Observatory](https://earthobservatory.nasa.gov/images/144729/the-mississippi-and-missouri-are-badly-swollen)
  - The Missouri River Basin had 50 record river-level events in 2019. — [NCEI](https://www.ncei.noaa.gov/node/699)
  - A reported ~$62B national 2019 flood damage figure appears only in an ENR headline URL and is unverified. — [ENR](https://enr.com/articles/48586-noaa-says-2019-floods-caused-62b-in-damage-expects-more)
- Spring floods have a persistent impact on crop loss in the US Midwest (title only, no details). — [ScienceDirect](https://sciencedirect.com/science/article/pii/S2212094721000815)

### Inferences
- Recommended antecedent features for county x month:
  - previous-month and previous-2-month precipitation (or its SPI-style anomaly);
  - root-zone soil moisture at the start of the month or as a monthly mean (ERA5-Land swvl1–swvl3, NLDAS/GLDAS Noah);
  - snow water equivalent at the end of the previous month and the change in SWE during the month as a snowmelt proxy (ERA5-Land `snow_depth_water_equivalent`, `snowmelt_sum`);
  - frozen-ground or temperature indicators (count of days with Tmin below 0 in the prior month);
  - an interaction of heavy-rain extreme × wet antecedent soil.
- Month-of-year fixed effects (seasonality: March–June snowmelt and convective peak) will capture part of this signal but not its year-to-year variation.
- The Midwest includes large mainstem rivers (Missouri, Mississippi, Red River of the North), where losses in a county can be driven by upstream basin conditions. Upstream-basin precipitation and soil moisture, or downstream gauge stage, may therefore matter as much as local county rainfall.

### Gaps
- I found no damage-based (as opposed to streamflow-based) quantification of the soil-moisture effect for US counties.
- The Berghuijs 2016 effect magnitudes and regional maps could not be read.

## Q4. Datasets 2000–2023 at monthly or finer resolution aggregable to counties (coverage, resolution, GEE ID, limitations)

### Takeaway
PRISM (daily and monthly, 4 km) is the best CONUS precipitation source. In Earth Engine the AN81d and AN81m collections are marked deprecated in favour of `OREGONSTATE/PRISM/ANd` and `OREGONSTATE/PRISM/ANm`. ERA5-Land provides daily soil moisture, snow and runoff back to 1950. NLDAS-2 provides hourly 1/8° forcing from 1979. GLDAS-2.1 runs from 2000. SMAP L4 starts only in 2015, which is unusable for a 2000–2016 training period. The Global Flood Database (MODIS) covers only 2000–2018, with sparse event coverage. USGS NWIS gives daily and peak streamflow plus NWS flood stages. The Dartmouth Flood Observatory gives event polygons from 1985 onward.

### Cited Findings
- **PRISM daily.**
  - `OREGONSTATE/PRISM/AN81d` is marked deprecated. One catalog page gives availability 1981-01-01 to 2020-12-30, and a mirror says 2021-09-29.
  - The replacement `OREGONSTATE/PRISM/ANd` covers 1981-01-01 to 2026-03-17 and holds both AN81 and AN91 data, flagged by the `dataset_type` property.
  - Bands: ppt, tmean, tmin, tmax, tdmean, vpdmin, vpdmax. Pixel size is about 4,638 m.
  - Sources: [GEE AN81d](https://developers.google.cn/earth-engine/datasets/catalog/OREGONSTATE_PRISM_AN81d?authuser=0); [GEE ANd](https://developers.google.com/earth-engine/datasets/catalog/OREGONSTATE_PRISM_ANd?authuser=0)
- **PRISM monthly.**
  - `OREGONSTATE/PRISM/AN81m` starts 1895-01-01 and is marked deprecated. Listed end dates conflict across snapshots (2020-12, 2021-08, 2025-07, 2025-09).
  - The successor is `OREGONSTATE/PRISM/ANm`. Version identifiers M1, M2 and M3 apply to monthly products.
  - Sources: [GEE AN81m](https://developers.google.com/earth-engine/datasets/catalog/OREGONSTATE_PRISM_AN81m?hl=zh-tw); [GEE ANm](https://developers.google.com/earth-engine/datasets/catalog/OREGONSTATE_PRISM_ANm?hl=zh-tw)
- **GPM IMERG.**
  - Monthly V07 is `NASA/GPM_L3/IMERG_MONTHLY_V07`, covering 1998-01-01 to 2025-09-01 at 0.1°. — [GEE IMERG monthly V07](https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_MONTHLY_V07?hl=fr)
  - The daily Final product is GPM_3IMERGDF_07 (0.1°) at GES DISC; its GEE daily ID was not confirmed. — [NASA PMM data services](https://ntrs.nasa.gov/api/citations/20240001387/downloads/PMM%20precip%20data%20services_12042023.pdf); [NCAR RDA d734000](https://oidc.rda.ucar.edu/datasets/d734000)
  - The half-hourly product is `NASA/GPM_L3/IMERG_V07` (from memory, unverified).
- **CHIRPS.**
  - `UCSB-CHC/CHIRPS/V3/DAILY_SAT` covers 1981 to near-present. It splits pentadal CHIRPS-v3 totals into daily amounts using IMERG Late V07. — [GEE CHIRPS v3 daily](https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHC_CHIRPS_V3_DAILY_SAT)
  - Limitation (general knowledge, unverified here): CHIRPS covers land only between 50°S and 50°N. That excludes most of North Dakota and Minnesota and northern Michigan and Wisconsin, so it is unsuitable for this 12-state domain.
- **NLDAS-2 forcing.** `NASA/NLDAS/FORA0125_H002` is hourly at 1/8°, from 1979-01-01 to the present. — [GEE NLDAS-2](https://developers.google.com/earth-engine/datasets/catalog/NASA_NLDAS_FORA0125_H002)
  - The NLDAS-2 Noah/VIC/Mosaic land-surface model outputs (soil moisture, runoff, SWE) are distributed by NASA LDAS/GES DISC, e.g. NLDAS_NOAH0125_H. I found no GEE asset. — [NASA LDAS NLDAS-2 model data](https://ldas.gsfc.nasa.gov/nldas/nldas-2-model-data)
- **GLDAS-2.1.**
  - `NASA/GLDAS/V021/NOAH/G025/T3H` is 3-hourly at 0.25°, from 2000-01-01 (end date listed as 2025-02-18 in the snapshot). — [GEE GLDAS-2.1](https://developers.google.com/earth-engine/datasets/catalog/NASA_GLDAS_V021_NOAH_G025_T3H)
  - GLDAS-2.0 (Princeton forcing) extends back to 1948. The NOAH and Catchment models run at 0.25°. — [GLDAS-2 README](https://data.mint.isi.edu/files/raw-data/GLDAS_NOAH025_M.2.0/doc/README_GLDAS2.pdf)
- **SMAP L4.**
  - `NASA/SMAP/SPL4SMGP/008` covers 2015-03-31 to 2026-10-15, 3-hourly at 9 km. It gives surface (0–5 cm) and root-zone (0–100 cm) soil moisture.
  - Limitation: it starts in 2015, so there is no training-period coverage.
  - Sources: [GEE SPL4SMGP.008](https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008); [NASA Earthdata](https://www.earthdata.nasa.gov/data/catalog/nsidc-cprd-spl4smgp-008)
- **ERA5-Land.**
  - A reanalysis of land variables at higher resolution than ERA5. The daily-statistics product runs from 1950. — [CDS ERA5-Land daily statistics](https://cds.climate.copernicus.eu/datasets/derived-era5-land-daily-statistics?tab=overview); [Muñoz-Sabater et al. 2021 ESSD](https://essd.copernicus.org/articles/13/4349/2021/essd-13-4349-2021.pdf)
  - GEE hourly: [ECMWF/ERA5_LAND/HOURLY](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY). Daily aggregated: [catalog slug ECMWF_ERA5_LAND_DAILY_AGGR](https://climateengine.org/datasets/climatehydrology/era5land_daily_11100/), i.e. `ECMWF/ERA5_LAND/DAILY_AGGR`.
  - The GEE daily ID and start date were not verified directly.
  - Resolution is 0.1° (about 9 km; general knowledge).
  - Useful bands (general knowledge, unverified here): volumetric soil water layers 1–4, snow water equivalent, snowmelt, surface and sub-surface runoff, total precipitation.
- **Global Flood Database v1.**
  - `GLOBAL_FLOOD_DB/MODIS_EVENTS/V1` covers 2000-02-17 to 2018-12-10. It maps 913 DFO events using 12,719 Terra/Aqua MODIS scenes and includes a JRC permanent-water band.
  - Event attributes come from DFO: severity, displaced, dead, GLIDE number.
  - Citation: Tellman et al. (2021), Nature, doi:10.1038/s41586-021-03695-w.
  - Source: [GEE Global Flood DB](https://developers.google.com/earth-engine/datasets/catalog/GLOBAL_FLOOD_DB_MODIS_EVENTS_V1)
  - Limitations:
    - It stops in 2018, so it covers only 2 of the 7 test years.
    - Only large DFO-listed events are mapped.
    - MODIS is 250 m and cloud-obscured (general knowledge).
- **Dartmouth Flood Observatory Global Active Archive.**
  - Covers 1985 to the present, with weekly updates. Provides Excel/XML event tables and GIS "area affected" outlines. Licence is CC BY 3.0. Most events are not mapped or measured.
  - A GEE community-catalog snapshot covers only 1985–2016.
  - Sources: [DFO Archives](https://floodobservatory.colorado.edu/Archives/index.html); [DFO FAQ](https://floodobservatory.colorado.edu/FAQ.html); [GEE community catalog](https://gee-community-catalog.org/projects/flood/)
  - Limitation: polygons are coarse, large-event only, and drawn from news sources. That makes DFO weak as a county-month hazard feature and risks overlap with impact reporting.
- **USGS NWIS.**
  - Provides historical and real-time streamflow, plus annual peak streamflow downloadable in WATSTORE format. NWS flood stage can be overlaid on gauge records.
  - Peak-flow data underpin flood-frequency estimates.
  - Sources: [USGS peak flow chart](https://www.usgs.gov/media/images/current-and-historical-peak-flow-chart); [USGS data catalog](https://data.usgs.gov/datacatalog/data/USGS:5aabf73de4b081f61aaf0388)
  - NWS thresholds are action, flood, moderate and major. That definition comes from a non-authoritative page and should be checked against NWS. — [ai-analytics.org](https://ai-analytics.org/writing/usgs-water-resources/)
  - Slater and Villarini (2016) used stage above NWS flood thresholds as the flood-occurrence measure. — [Wiley](https://agupubs.onlinelibrary.wiley.com/doi/10.1002/2016GL071199)
- **Daymet.** Used as the rainfall predictor in the NFIP claims ML study. — [arXiv 2212.08660](https://doi.org/10.48550/arXiv.2212.08660)
  - Daymet is 1 km daily over North America from 1980, with GEE ID `NASA/ORNL/DAYMET_V4` (general knowledge, unverified here).

### Inferences
- Practical stack for this project:
  - **Precipitation:** PRISM daily (ANd) for monthly totals, Rx1/3/5day and percentile exceedances. Area-weight to county polygons, e.g. with TIGER counties `TIGER/2018/Counties` via `reduceRegions`. Use PRISM monthly (ANm) for the long baseline.
  - **Antecedent moisture and snow:** ERA5-Land daily (soil water L1–L3, SWE, snowmelt, runoff), consistent 1950–2023.
  - **Cross-check:** NLDAS-2 forcing.
  - **Streamflow:** USGS NWIS daily values for gauges in or near each county. Compute the monthly maximum of discharge divided by the gauge's 2-year flood (or stage minus NWS flood stage), mapped to counties by gauge location or HUC.
  - **Avoid or treat as optional:** SMAP (starts 2015), CHIRPS (50°N cut-off; unverified here), GFD (ends 2018).
- **Leakage caution.** DFO and GFD events are compiled partly from impact reports. Using them as inputs may proxy the outcome, and they are also unavailable for most of the test period.
- **Distribution shift caution.** PRISM's dataset_type (AN81 vs AN91) and its station network change over time. Use one consistent product across train and test.

### Gaps
- The exact current Earth Engine IDs and end dates for ERA5-Land daily, IMERG daily V07 and Daymet could not be verified because catalog pages could not be opened.
- Whether `OREGONSTATE/PRISM/ANm` fully covers 1895–2023 as a single consistent version was not confirmed.
- No retrieved source documented a pre-processed county-level USGS gauge-to-county crosswalk.

## Q5. Does any data allow a long pre-2000 baseline (anomalies or a rainfall-based flood climatology)?

### Takeaway
Yes. Several sources reach well before 2000:
- PRISM monthly runs from 1895 and PRISM daily from 1981.
- ERA5-Land runs from 1950.
- NLDAS-2 runs from 1979, and GLDAS-2.0 from 1948.
- CHIRPS runs from 1981 but has latitude limits.
- USGS peak-flow records are often decades long.

These allow county-specific percentile and return-period thresholds and anomalies (e.g. 1981–1999 or 1895–1999 climatologies) computed without touching the 2000–2023 outcome period.

### Cited Findings
- PRISM AN81m/ANm monthly starts 1895-01-01. — [GEE AN81m](https://developers.google.com/earth-engine/datasets/catalog/OREGONSTATE_PRISM_AN81m?hl=zh-tw)
- PRISM AN81d/ANd daily starts 1981-01-01. — [GEE ANd](https://developers.google.com/earth-engine/datasets/catalog/OREGONSTATE_PRISM_ANd?authuser=0)
- ERA5-Land daily statistics run from 1950 to the present. — [CDS](https://cds.climate.copernicus.eu/datasets/derived-era5-land-daily-statistics?tab=overview)
- NLDAS-2 forcing runs from 1979-01-01. — [GEE NLDAS-2](https://developers.google.com/earth-engine/datasets/catalog/NASA_NLDAS_FORA0125_H002)
- GLDAS-2 documentation (version 2.0 is the long Princeton-forced run). — [GLDAS-2 README](https://data.mint.isi.edu/files/raw-data/GLDAS_NOAH025_M.2.0/doc/README_GLDAS2.pdf)
- CHIRPS v3 daily runs from 1981. — [GEE CHIRPS v3](https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHC_CHIRPS_V3_DAILY_SAT)
- USGS peak-flow data drive flood-frequency estimates. — [USGS](https://www.usgs.gov/media/images/current-and-historical-peak-flow-chart)
- Davenport et al. built a monthly state panel back to 1960, and Mallakpour and Villarini used gauge records from 1962–2011. Both show that long baselines are standard in this literature. — [ADS](https://ui.adsabs.harvard.edu/abs/2019AGUFMGC23A..02D); [Nature](https://www.nature.com/articles/nclimate2516)

### Inferences
- Suggested baseline:
  - Compute county-level daily-precipitation percentiles (95th/99th), and Rx1day/Rx5day annual-maximum distributions (GEV fit for 2-, 10- and 25-year return levels), from PRISM daily 1981–1999.
  - Compute monthly z-scores or SPI from PRISM monthly 1895–1999 (or 1981–2010).
  - Compute soil-moisture percentiles from ERA5-Land 1950–1999.
- Using only pre-2000 data, or only training-period data, for thresholds keeps the test set (2017–2023) clean.

### Gaps
- Nonstationarity (e.g. Mallakpour and Villarini's increasing flood frequency) means a 1895–1999 baseline may understate current exceedance frequency. I found no source that quantifies the impact of baseline choice on loss-model skill.
