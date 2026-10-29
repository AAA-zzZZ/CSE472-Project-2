# Modelling methods for zero-heavy, skewed county flood loss data (incl. Bayesian spatial models)

> **Read this first: source access.** This session's network sandbox blocked direct page fetches to almost every academic host (paulamoraga.com, doi.org, link.springer.com, iopscience.iop.org, onlinelibrary.wiley.com, arxiv.org, PMC, MDPI, copernicus.org, r-inla.org, scikit-learn.org all failed with DNS errors or proxy rejections). Only two sources below were **opened in full**:
> (1) the R-INLA zero-inflated likelihood documentation, via a GitHub mirror (raw.githubusercontent.com/grantbrown/inla), and (2) the PyMC BYM example notebook (raw.githubusercontent.com/pymc-devs/pymc-examples).
> Every other claim comes from **search-engine snippets or summaries** of the cited URL, not the full text. Each of those is marked **[snippet]**. Before anything goes into a final report, the writer should treat [snippet] numbers as unverified and re-check them against the paper. **The Moraga chapter could not be opened.** Its summary below is pieced together from snippets plus standard knowledge of BYM/INLA, and the two are labelled separately.

## Q1. Studies modelling SHELDUS / NCEI Storm Events county losses: models used and reported skill

### Takeaway
No study found pairs SHELDUS county-month flood loss with a hurdle, Tweedie or ML model and reports AUC or ranking skill. The direct precedents are:
- Tobit models of annual county SHELDUS flood damage (Indiana).
- A 2025 SHELDUS crop-loss study that uses a classify-then-regress design with RF/SVM against a GLMM and a county-month climatology baseline.
- Two-part mixed-effects models for flash-flood damage at community scale.
- Tree ensembles (RF, GBM/LightGBM) for county or event flood-damage regression.

The project's two-part hurdle is therefore well-motivated, but published benchmark numbers that are directly comparable are essentially absent.

### Cited Findings
- **Tobit on SHELDUS (Indiana).** Liu et al. (Climatic Change) model county-level *annual* SHELDUS flood property damage (1995–2012 in the OSTI version) with a Tobit. They justify it because "not every county suffered damage every year", treating zeros as a corner solution (citing Wooldridge 2010), and they include county indicators (fixed effects). They then use the fitted model to project future damage. [snippet] — [Liu et al., Climatic Change (mygeohub PDF)](https://mygeohub.org/resources/1200/download/Liu-et_al-Climatic_Change.pdf); [OSTI version](https://www.osti.gov/pages/servlets/purl/1265732)
- **SHELDUS + ML with an explicit zero-inflation design (crop losses, Delmarva, 2025).** SHELDUS county loss records are paired with daily PRISM weather for 1980–2018. Because losses are zero-heavy and heavy-tailed, the authors compare "multi-step" formulations: stratified sampling, then a damage/no-damage classification, then loss estimation. Random forests and SVMs are compared against a generalized linear mixed model (GLMM) and a simple **county-and-month average baseline**. Numeric results were not available in the snippet. [snippet] — [Stochastic Environmental Research and Risk Assessment, 2025, doi:10.1007/s00477-025-03157-z](https://link.springer.com/article/10.1007/s00477-025-03157-z)
- **Two-part (hurdle-type) mixed-effects model for flash-flood damage.** Damage occurrence was found to be zero-inflated, so the authors fit part 1 for the probability of damage and part 2 for the dollar amount given damage, with mixed (random) effects. The application is Harris County, TX at census-tract scale (not SHELDUS). [snippet] — ["Predicting Flash Flood Economic Damage at the Community Scale: Empirical Zero-Inflated Model with Semicontinuous Data", Natural Hazards Review (ASCE), doi:10.1061/NHREFO.NHENG-1729](https://doi.org/10.1061/nhrefo.nheng-1729)
- **ML for flash-flood damage, Southeast US.** Uses machine learning to predict flash-flood damage, with county-level social vulnerability indices and NN-imputed Zillow home values. Specific model metrics were not retrieved. [snippet] — [Environmental Research Letters, doi:10.1088/1748-9326/ab6edd](https://iopscience.iop.org/article/10.1088/1748-9326/ab6edd)
- **CONUS ML flood-damage cost models from NOAA flood events.** Random forest was the top regressor, and the authors describe RF as "a practical, scalable backbone for flood modeling". Gradient Boosting Regressor was evaluated as a comparison. The 38 candidate predictors were reduced to 18, which "yield[ed] more stable and consistent results". [snippet] — [Hydrology 13(1):31 (2026), doi:10.3390/hydrology13010031](https://doi.org/10.3390/hydrology13010031)
- **County-level direct economic loss, tropical cyclones (Guangdong).** Compares RF, XGBoost, LightGBM and CatBoost on 896 samples, and **LightGBM performed best**. [snippet] — [Int. J. Disaster Risk Reduction (ScienceDirect S2212420924007179)](https://www.sciencedirect.com/science/article/abs/pii/S2212420924007179)
- **Urban flood severity (Norfolk, VA).** Random forest beat Poisson regression at predicting the number of flood reports and had a lower false-negative rate. [snippet] — [NSF PAR, "Modeling Urban Coastal Flood Severity from Crowd-Sourced…"](https://par.nsf.gov/servlets/purl/10065971)
- **District-level flood-risk classification (Indonesia, 2026).** XGBoost had the highest ROC-AUC (0.675), while RF had higher recall. This shows that event-occurrence AUCs in hazard data can be modest. [snippet] — [Journal of Information Systems and Informatics, Vol 8 No 1 (2026)](https://journal-isi.org/index.php/isi/article/download/1461/734)
- **Zero-inflated spatial point process for grouped storm insurance losses (2026 preprint).** A zero-inflated mixed Poisson model. Storm extent and the number of affected properties raise the chance of any claim, and precipitation and wind speed raise claim intensity. [snippet] — [arXiv:2607.03852](https://arxiv.org/pdf/2607.03852)
- **Data-quality caveat.** A review of inland-flood research notes that SHELDUS is derived from NOAA Storm Events and that both "have been criticized for the inaccurate reporting of damages and fatalities". [snippet] — [Environmental Research Letters review, doi:10.1088/1748-9326/add35e](https://iopscience.iop.org/article/10.1088/1748-9326/add35e)
- **Coastal compound-flood study.** Uses SHELDUS losses for 203 coastal counties, 1980–2018, linking losses to compound drivers (≥2 drivers above the 95th percentile). The analysis is descriptive, not a predictive model. [snippet] — [npj Natural Hazards (Nature portfolio), s44304-025-00076-5](https://www.nature.com/articles/s44304-025-00076-5)
- **Tweedie (compound Poisson–gamma) as a one-part alternative to hurdles.** For power parameter 1<p<2, Tweedie is a Poisson number of gamma-sized losses. It has an exact point mass at zero and a continuous positive part, so one log-link GLM covers zeros and amounts together. It is standard in insurance pure-premium modelling (Smyth & Jørgensen; gradient-boosted Tweedie by Yang, Qian & Zou). It is implemented as a scikit-learn example (`TweedieRegressor`, `HistGradientBoostingRegressor(loss="poisson")`), and LightGBM/XGBoost offer a `tweedie` objective. No flood-specific county Tweedie application was found. [snippet] — [Smyth & Jørgensen, ASTIN/ResearchGate](https://www.researchgate.net/publication/43485139_Fitting_Tweedie's_Compound_Poisson_Model_to_Insurance_Claims_Data_Dispersion_Modelling); [Yang, Qian & Zou, arXiv:1508.06378](https://arxiv.org/pdf/1508.06378); [scikit-learn Tweedie example](https://scikit-learn.org/stable/auto_examples/linear_model/plot_tweedie_regression_insurance_claims.html)

### Inferences
- The project's **logistic + log-linear hurdle** has direct precedent: the two-part model in the Natural Hazards Review paper and the classify-then-regress design in the Delmarva SHELDUS paper. A **Tobit** is the main econometric alternative in the SHELDUS literature, but it assumes a single latent process governs both occurrence and size. A hurdle relaxes that assumption, and with ~97% zeros a hurdle is more defensible.
- The **county × calendar-month climatology** (the mean or occurrence rate for each county and month over the training years) used as a baseline in the Delmarva paper is a cheap, strong benchmark. The project should report it next to the hurdle and OLS models.
- With 3% positives, **gradient boosting (LightGBM/XGBoost) with a binary objective for occurrence plus a Tweedie or log-normal objective for severity** is the ML family most often reported as best in county/event loss tasks. RF is the most common "robust baseline".
- **Retransformation bias.** Any OLS on log(damage) needs a smearing correction (Duan) before predictions are converted back to dollars. Without it, expected dollars are biased low. This is standard econometrics and was not sourced in this session.

### Gaps
- No study was found reporting AUC, Brier, Spearman or top-k for SHELDUS **county-month** flood property loss. The full texts of the Delmarva and NHR papers (blocked) may contain metrics.
- Numeric performance of the Delmarva models and of the CONUS Hydrology paper could not be extracted.
- Studies such as Davenport/Burke/Diffenbaugh (2021, PNAS) on precipitation-driven US flood damages using county data were not retrieved in this session.

## Q2. Bayesian spatial / spatio-temporal models (BYM, BYM2, Leroux, INLA, SPDE) for disaster losses or counts; zeros; tooling; spatial confounding

### Takeaway
Areal CAR-family models (ICAR/Besag, BYM, BYM2, Leroux) fitted with R-INLA are the standard way to borrow strength across neighbouring counties. They have recently been applied to flood insurance claims, to climate-related claim counts, and to hurdle models for wildfire. Zeros can be handled three ways in INLA:
- built-in zero-inflated likelihoods (type 0 = hurdle-like, type 1 = mixture);
- a joint two-likelihood hurdle (binomial + positive part) that shares spatial effects;
- separately fitted occurrence and severity models.

BYM2 with PC priors is the recommended parameterisation. Spatial random effects can bias or inflate the variance of covariate coefficients (spatial confounding), which matters for interpretation but much less for pure prediction.

### Cited Findings
**Applications to hazards / losses**
- **Residential flood insurance claims (France, 2026 preprint).** Compares a GLM benchmark with **iCAR, BYM and SPDE** Gaussian random-field models, all in INLA. The SPDE captures sub-municipal risk gradients that areal models miss. [snippet] — [arXiv:2607.07609, "Bayesian spatial modelling framework for assessing residential flood risk in property insurance"](https://arxiv.org/abs/2607.07609)
- **Climate-related property claim counts (Greece, 2025).** Mixed-Poisson spatio-temporal and temporal **Besag negative-binomial** regression fitted in INLA. The Besag effect smooths across neighbouring regions to absorb unmeasured factors such as flood protection. [snippet] — [European Actuarial Journal, doi:10.1007/s13385-025-00443-6](https://link.springer.com/article/10.1007/s13385-025-00443-6)
- **Hurdle + BYM2 + ML hybrid (wildfires, Portugal, 2026).** "XGBoost Meets INLA" is a two-stage spatio-temporal forecast with a **hurdle** structure (zeros and positives modelled separately) and **reparameterised BYM2** spatial effects in R-INLA, with council-level and district-level graphs. This is the closest methodological template to a "hurdle + Bayesian spatial" flood model. [snippet] — [Hu et al., Environmetrics 2026, doi:10.1002/env.70089](https://onlinelibrary.wiley.com/doi/10.1002/env.70089)
- **Wildfire counts across Italian municipalities.** ICAR/BYM priors in R-INLA. [snippet] — [Environmental and Ecological Statistics 2026, doi:10.1007/s10651-026-00723-8](https://link.springer.com/article/10.1007/s10651-026-00723-8)
- **Semi-parametric spatial model for dispersed counts in INLA**, with climate-risk applications. [snippet] — [SERRA 2025, doi:10.1007/s00477-025-03165-z](https://link.springer.com/article/10.1007/s00477-025-03165-z)
- **Zero-inflated spatio-temporal data with INLA/SPDE** (child mortality, South Africa). [snippet] — [Musenge et al., Int. J. Applied Earth Observation & Geoinformation, ScienceDirect S0303243412000645](https://www.sciencedirect.com/science/article/pii/S0303243412000645)
- **Joint hurdle/zero-inflated spatial model in R-INLA** (Bernoulli for occurrence + zero-truncated Poisson for counts, shared spatial effects), with a simulation study. [snippet] — [Bayesian Spatial Joint Model for Disease Mapping of Zero-Inflated Data with R-INLA (PMC6888013)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6888013/)
- **Hurdle and zero-inflated joint models in R-INLA**, with BYM as an alternative to SPDE. INLA keeps these cheap relative to MCMC. [snippet] — [Sadykova et al., Ecology and Evolution 2017, doi:10.1002/ece3.3081](https://onlinelibrary.wiley.com/doi/full/10.1002/ece3.3081)

**How INLA handles zeros (documentation opened)**
- R-INLA supports two zero-inflation types for Poisson, binomial, negative binomial and beta-binomial:
  - **Type 0:** Prob(y) = p·1[y=0] + (1−p)·Poisson(y | y>0). This is a hurdle-style truncated positive part. Family names: `zeroinflatedpoisson0`, `zeroinflatednbinomial0`, …
  - **Type 1:** Prob(y) = p·1[y=0] + (1−p)·Poisson(y). This is a mixture with structural plus sampling zeros. Family names: `zeroinflatedpoisson1`, `zeroinflatednbinomial1`, …
  - p = exp(θ)/(1+exp(θ)) is a **hyperparameter**. The prior and initial value are set on θ.
  - **(Opened)** — [R-INLA likelihood doc "zeroinflated.tex" (GitHub mirror grantbrown/inla)](https://raw.githubusercontent.com/grantbrown/inla/master/r-inla.org/doc/likelihood/zeroinflated.tex)
- Because p is a scalar hyperparameter, these built-in families give an **intercept-only zero-inflation part**. To get covariates and spatial effects in the occurrence part, users fit a **multi-likelihood joint model**, e.g. `family = c("binomial", <positive family>)`, with separate linear predictors and optionally a shared (`copy=`) spatial effect. These are R-INLA mailing-list answers and may be outdated. [snippet] — [r-inla discussion: "Likelihoods for a hurdle model"](https://groups.google.com/g/r-inla-discussion-group/c/DPvHIGcbd0E); [r-inla discussion: zero-truncated/hurdle](https://groups.google.com/g/r-inla-discussion-group/c/ZOAACtyIkrA)
- No built-in "hurdle-gamma" / zero-inflated continuous family was found for **dollar** losses. The practical route is to fit the occurrence part (binomial) and the positive part (Gaussian on log loss, or gamma/lognormal on loss) as two models or as a joint two-likelihood model. [snippet / inference from search] — same threads as above

**BYM, BYM2, Leroux: definitions and recommendations**
- **BYM (opened, PyMC docs).** BYM uses an ICAR prior (neighbours covary; sum-to-zero constraint) plus an iid random effect. The BYM2 parameterisation (Riebler et al. 2016) writes the effect as β + σ(√(1−ρ)·θ + √(ρ/s)·φ). Here φ is the ICAR term, θ is iid N(0,1), ρ∈[0,1] is the share of variance that is spatially structured, and s is a **scaling factor computed from the adjacency graph** so that φ has unit variance. The notebook says this makes the model "interpretable and identifiable while previous parameterizations… are often not". It also says BYM's computational cost grows nearly linearly with the number of areas, and that it "only works for fully connected graphs" (islands need special handling). It gives PyMC code (`pm.ICAR`, `rho = pm.Beta(...)`) and a NumPy/SciPy sparse function for the scaling factor. **(Opened)** — [PyMC example "The Besag-York-Mollie Model for Spatial Data" (nyc_bym)](https://raw.githubusercontent.com/pymc-devs/pymc-examples/main/examples/spatial/nyc_bym.myst.md)
- The PyMC notebook also argues that spatial smoothing helps **forecasting/targeting**: a low-loss area surrounded by high-loss neighbours "probably just had good luck in the past" and will likely resemble its neighbours. This is the core intuition for using BYM in an allocation/ranking task. **(Opened)** — same source
- **R-INLA syntax.** `f(ID, model="bym", graph=adj)`; separate `besag` + `iid` terms need duplicated index variables; `bym2` is "the BYM-model with the PC priors". [snippet] — [Blangiardo, Cameletti, Baio & Rue tutorial (UCL Discovery)](https://discovery.ucl.ac.uk/1415919/1/Baio_BlaCamBaiRue.pdf); [R4DS bookclub notes on Moraga's book](https://r4ds.github.io/bookclub-spacestats/bayesian-spatial-models-in-inla-8.html)
- **Riebler et al. (2016) recommend BYM2 over Leroux.** BYM2's PC priors (Simpson et al. 2017) shrink first toward no spatial variation, then toward unstructured-only variation. [snippet] — [Spatial modelling with R-INLA: a review, arXiv:1802.06350](https://arxiv.org/pdf/1802.06350); [Simpson et al., Statistical Science 32(1), doi:10.1214/16-STS576](https://projecteuclid.org/journals/statistical-science/volume-32/issue-1/Penalising-Model-Component-Complexity--A-Principled-Practical-Approach-to/10.1214/16-STS576.pdf)
- **Leroux (Leroux, Lei & Breslow 2000)** puts a single mixing parameter inside one CAR precision matrix. In an applied 2026 comparison, Leroux and BYM2 were within ~0.2 DIC of each other, so the choice often barely matters for fit. [snippet] — [arXiv:1802.06350](https://arxiv.org/pdf/1802.06350); [Springer supplementary Table S1 (Clin. Transl. Oncol. 2026)](https://media.springernature.com/original/springer-static/esm/art%3A10.1007%2Fs12094-026-04408-3/MediaObjects/12094_2026_4408_MOESM1_ESM.docx)
- **Large-area tooling.** The `bigDM` R package fits spatial and spatio-temporal CAR models (iCAR, BYM2, Leroux, with Knorr-Held space-time interactions) on large numbers of small areas with INLA, using divide-and-conquer. [snippet] — [bigDM vignette](https://emi-sstcdapp.unavarra.es/bigDM/bigDM-1-fitting-spatial-models.html)
- **Model choice in spatial models.** Joint leave-group-out CV for Bayesian spatial models: in one analysis, CV favoured a simpler SAR model over BYM/BYM2. [snippet] — [arXiv:2504.15586](https://arxiv.org/pdf/2504.15586)

**Spatial confounding**
- **Hodges & Reich (2010, The American Statistician, "Adding spatially-correlated errors can mess up the fixed effect you love").** Adding a spatial random effect can change, bias or variance-inflate fixed-effect estimates when the covariate is itself spatially smooth. Their remedy, **restricted spatial regression (RSR)**, constrains the spatial effect to be orthogonal to the covariates. [snippet] — [Restricted Spatial Regression Methods: Implications for Inference (Khan & Calder), arXiv:1905.09371 / PMC9540349](https://pmc.ncbi.nlm.nih.gov/articles/PMC9540349/)
- **RSR's critics.** Hanks et al. (2015, Environmetrics, "Restricted spatial regression in practice: geostatistical models, confounding, and robustness under model misspecification") and Khan & Calder (JASA 2022) show that RSR yields overconfident (too narrow) intervals for the fixed effects. The current consensus is that RSR is not a fix for inference. [snippet; Hanks findings only partly confirmed] — [Khan & Calder, PMC9540349](https://pmc.ncbi.nlm.nih.gov/articles/PMC9540349/); [Spatial confounding review, arXiv:2602.17792](https://arxiv.org/pdf/2602.17792)
- **Concrete example from Moraga's own case study.** Under the BYM model, the smoking effect on Pennsylvania lung-cancer risk is attenuated and its interval may include zero. [snippet] — [Spatial Confounding: a review of concepts, challenges, and current approaches, arXiv:2602.17792](https://arxiv.org/pdf/2602.17792)
- **Recent alternatives:** spline-based mitigation (Biometrics 2025) and multivariate areal confounding (Biometrics 2026). [snippet] — [Regularized principal spline functions, Biometrics 81(2) ujaf076](https://academic.oup.com/biometrics/article/81/2/ujaf076/8174611); [Spatial confounding in multivariate areal data analysis, arXiv:2505.07232](https://arxiv.org/pdf/2505.07232)

**Tooling summary**
- **R-INLA:** `bym`, `bym2`, `besag`, `besagproper`, `generic1` (Leroux via custom precision), `ar1`/`rw1`/`rw2` for time, and space-time interaction via `group=`. Zero-inflated families are as above. Fast for ~1,000 areas × ~200 months. [opened doc for likelihoods; others snippet] — [arXiv:1802.06350](https://arxiv.org/pdf/1802.06350)
- **PyMC:** `pm.ICAR` + BYM2 mixing (opened notebook). Hurdle likelihoods (`pm.HurdleGamma`, `pm.HurdleLogNormal`, `pm.HurdlePoisson`) exist in PyMC ≥5 (my knowledge, not verified in this session). MCMC on 1,055 counties × 288 months (~300k rows) is slow, so aggregating to county level or county × season for the spatial component is advisable. **(Opened for ICAR/BYM2)** — [PyMC nyc_bym example](https://raw.githubusercontent.com/pymc-devs/pymc-examples/main/examples/spatial/nyc_bym.myst.md)
- **brms (Stan):** supports `car(M, type="icar"|"bym2"|"esicar")` terms and `hurdle_lognormal`, `hurdle_gamma` and `zero_inflated_*` families, so a spatial hurdle-lognormal is one formula (`bf(y ~ x + car(W, gr=county), hu ~ x + car(W, gr=county))`). This is from general knowledge; it was not opened in this session.

### Inferences
- **Recommended Bayesian spatial design for this project** (a direct analogue of the Portugal wildfire hurdle + BYM2):
  - Occurrence: `any_damage_it ~ Bernoulli(π_it)`, with `logit π_it = X_itβ + BYM2_county + month-of-year effect (rw1 cyclic or fixed) + year effect (rw1/iid)`.
  - Severity: `log(loss_it) | loss>0 ~ Normal(μ_it, σ²)`, with its own BYM2 term. Optionally share the spatial field via `copy` in INLA so that counties with more frequent damage also tend to have larger losses.
  - Fit with R-INLA (fast). In Python, PyMC + `pm.ICAR` is workable if data are aggregated.
- **Where BYM2 adds most value.** The ~97% zeros mean most counties have only a few positive months in 2000–2016. The BYM2 term **pools sparse county histories toward their neighbours**, which should improve ranking of rarely-flooded counties. This is the main argument for the instructor's suggestion. An iid county effect only (no spatial term) is a useful ablation.
- **Spatial confounding is mostly an interpretation issue here.** If the goal is prediction/allocation, confounding mainly affects interpretation of β (e.g., a precipitation or impervious-surface coefficient). If the project reports driver coefficients, it should present them with and without the spatial effect and note the Hodges–Reich caution.
- **Counts vs dollars.** INLA's built-in zero-inflated families are for counts. For dollar losses, a two-likelihood hurdle (binomial + Gaussian-on-log or gamma) is the practical route.

### Gaps
- **No published BYM/BYM2 model of SHELDUS county flood losses was found.** The closest are French flood claims (point/municipal) and Greek climate claims (regional counts).
- Exact performance comparisons of spatial vs non-spatial models in those flood/claims papers could not be extracted (full text blocked).
- The Hanks et al. (2015) content is known only by title/citation context. Its DOI (10.1002/env.2331, from memory) was not verified.

## Q3. Moraga, *Spatial Statistics for Data Science*, Chapter 9 "Bayesian spatial models": coverage and mapping to this problem

### Takeaway
**The chapter page could not be opened (host blocked).** From snippets, Chapter 9 sits in Part 2 ("Areal data"), between the spatial-autocorrelation chapter and Chapter 10 "Disease risk modeling". It:
- introduces Bayesian hierarchical models for areal data;
- explains INLA as approximate Bayesian inference for latent Gaussian models;
- presents the BYM model;
- shows how to write the model formula and `inla()` call (Section 9.2.4).

The book's companion chapters apply this to Pennsylvania lung-cancer counts (Poisson, expected counts, smoking covariate), and the book also covers SPDE for geostatistical data.

### Cited Findings
- The chapter opens with "Bayesian hierarchical models that can be used to analyze areal data", where an outcome is aggregated over areas forming a partition of the study region. It introduces the **Besag-York-Mollié (BYM)** model as "a commonly used spatial model". In the snippet the model is written with a Gaussian example Y_i ~ N(μ_i, σ²), μ_i = z_iβ + u_i + v_i (u = structured ICAR, v = unstructured iid). Section 9.1 describes **INLA** as "a computational approach to perform approximate Bayesian inference in latent Gaussian models". Section 9.2.4 is titled "Model formula and inla() call". [snippet] — [Moraga, Ch. 9 Bayesian spatial models](https://www.paulamoraga.com/book-spatial/bayesian-spatial-models.html)
- The book "gives detailed explanations on how to fit and interpret Bayesian spatial models using INLA and SPDE approaches". [snippet] — [Routledge book page](https://www.routledge.com/Spatial-Statistics-for-Data-Science-Theory-and-Practice-with-R/Moraga/p/book/9781032633510)
- **Chapter 10 (Disease risk modeling)** shows how to specify, fit and interpret a Bayesian spatial model of **lung cancer risk vs smoking in Pennsylvania (2002)**, with data from the SpatialEpi package and population from the 2000 census. [snippet] — [Moraga, Ch. 10 Disease risk modeling](https://www.paulamoraga.com/book-spatial/disease-risk-modeling.html)
- Moraga's earlier book (*Geospatial Health Data*, 2019) covers the same workflow: neighbourhood matrices, SIRs, and a BYM model in INLA for Pennsylvania lung cancer, i.e. Y_i ~ Poisson(E_i θ_i), log θ_i = β0 + β1·smoking + u_i + v_i, with relative risks, exceedance probabilities P(θ_i>1), and maps. [snippet] — [Geospatial Health Data, Ch. 5 Areal data](https://www.paulamoraga.com/book-geospatial/sec-arealdatatheory.html); [Moraga tutorial "Areal data: lung cancer risk in Pennsylvania"](https://www.paulamoraga.com/tutorial-areal-data/); [Moraga, R Journal 2018 "Small Area Disease Risk Estimation and Visualization Using R"](https://journal.r-project.org/archive/2018/RJ-2018-036/RJ-2018-036.pdf)
- The bookclub notes for this chapter list INLA latent models including `besag` ("Besag area model (CAR-model)") and `bym2` ("BYM-model with the PC priors"). [snippet] — [R4DS bookclub: Bayesian spatial models in INLA](https://r4ds.github.io/bookclub-spacestats/bayesian-spatial-models-in-inla-8.html)

### Inferences (mapping to the SHELDUS project)
| Moraga concept | SHELDUS county flood analogue |
|---|---|
| Areas = Pennsylvania counties; neighbourhood matrix from polygons (`spdep::poly2nb`) | 1,055 Midwest counties; queen-contiguity graph from county shapefile (check for islands/disconnected components, which BYM2 scaling requires) |
| Y_i = observed lung-cancer cases, E_i = expected cases (offset) | Option A: count of damage months per county (train period) with offset = number of months → Poisson/BYM2 gives a smoothed county "flood propensity". Option B: county-month binary any-damage → Bernoulli/BYM2 (occurrence part of the hurdle). Option C: log(loss) given loss>0 → Gaussian/BYM2 (severity part) |
| Covariate: smoking proportion | Precipitation extremes, river/floodplain exposure, impervious surface, property value, etc. |
| Relative risk θ_i, exceedance probability P(θ_i>1) | Posterior P(county in top-k risk) or P(loss > threshold) → directly usable for ranking/allocation with uncertainty |
| u_i (ICAR) + v_i (iid) | Spatially structured flood propensity (shared basins/climate) + county idiosyncrasy |
| Spatio-temporal extensions (Moraga's other chapters / Knorr-Held) | Add month-of-year seasonal effect and year effect (rw1/ar1) and optionally space × time interaction. Forecast 2017–2023 from 2000–2016 by leaving test responses NA in INLA |

- The textbook example is a **pure cross-sectional disease-mapping** example (one time point, Poisson counts, no excess zeros). The project needs to extend it with (a) a temporal component and (b) a hurdle/zero-inflated likelihood. These extensions are not in the cited chapter snippets, so they must be built from the INLA docs or the Portugal hurdle-BYM2 template.
- **Lowest-effort first step.** Fit a Poisson-BYM2 to *county totals of damage months, 2000–2016* (one row per county, offset log(204 months)). Use the posterior county propensity as a feature/prior in the existing numpy hurdle, and compare test-period ranking against a county-frequency baseline.

### Gaps
- The exact sections, equations, priors (PC priors?) and examples in Moraga Ch. 9 could not be verified because the page was blocked. The writer should open https://www.paulamoraga.com/book-spatial/bayesian-spatial-models.html directly, or ask the user to allow the host.
- Whether Ch. 9 discusses zero-inflation, spatial confounding or model comparison (DIC/WAIC/CPO) is unknown.

## Q4. Evaluation for ranking and allocation; good practice for temporal train/test splits

### Takeaway
For a 3%-positive outcome used to prioritise counties, evaluate each part separately as well as end to end:
- **Occurrence:** ROC-AUC plus PR-AUC (more informative at 3% prevalence), Brier score with a reliability/calibration curve, and a skill score against a climatology baseline.
- **Ranking:** Spearman/Kendall correlation of predicted vs observed county totals over the test window, and top-k hit rate / precision@k / share of total loss captured.
- **Severity / uncertainty:** error on log-loss for positive cases, and empirical coverage of 80/90/95% prediction intervals.

Use a strictly forward temporal split (as the project does) and, where tuning, rolling-origin or blocked CV rather than random CV.

### Cited Findings
- **Block, not random, CV.** Random CV underestimates predictive error when data have temporal or spatial dependence and invites overfitting to non-causal predictors. The authors recommend **block CV** "wherever dependence structures exist… even if no correlation structure is visible in the fitted model residuals, or if the fitted models account for such correlations". They warn that blocking can induce extrapolation. [snippet] — [Roberts et al. 2017, Ecography 40(8):913–929, doi:10.1111/ecog.02881 (author PDF)](https://www.biometrie.uni-freiburg.de/mitarbeiter/dormann/roberts-et-al-2017-ecography.pdf)
- **Leave-group-out CV for Bayesian spatial models**, which matters because neighbouring counties leak information. [snippet] — [arXiv:2504.15586](https://arxiv.org/pdf/2504.15586)
- **Moderate AUCs are typical in hazard-occurrence classification** (e.g., XGBoost ROC-AUC 0.675 for district flood risk). [snippet] — [JISI 2026](https://journal-isi.org/index.php/isi/article/download/1461/734)
- **Climatology baseline.** A county × month average was used as the baseline in the SHELDUS Delmarva study. [snippet] — [doi:10.1007/s00477-025-03157-z](https://link.springer.com/article/10.1007/s00477-025-03157-z)
- **Tweedie / insurance practice.** Uses Lorenz curves / Gini index to score how well predicted risk *ranks* observed losses, alongside Tweedie deviance. This is directly analogous to "share of loss captured by top-k counties". [snippet] — [scikit-learn Tweedie insurance example](https://scikit-learn.org/stable/auto_examples/linear_model/plot_tweedie_regression_insurance_claims.html)

### Inferences (practical guidance; standard practice, not individually sourced here)
- **Metrics checklist for the project:**
  1. Occurrence part: ROC-AUC, **PR-AUC** (baseline = prevalence ≈ 0.03), Brier score and **Brier skill score** vs county-month climatology, reliability diagram.
  2. Expected-loss ranking: Spearman ρ between predicted and observed 2017–2023 county totals. **Top-k hit rate** (overlap of predicted vs actual top-50/100 counties). **Loss captured@k** (fraction of total test-period dollars in the predicted top-k). Lorenz/Gini.
  3. Severity: RMSE/MAE on log-loss for positives, calibration of the expected-dollar sum (with smearing).
  4. Uncertainty: empirical coverage of prediction intervals (the Bayesian models give these natively; for numpy models, use residual bootstrap or quantile/conformal intervals).
- **Temporal split hygiene:**
  - Fit all preprocessing (scalers, county-level target encodings, climatologies, spatial-effect estimates) on 2000–2016 only.
  - Use rolling-origin validation inside the training years (e.g., train to 2012, validate 2013–2016) for hyperparameters.
  - Report results by test year to expose year-to-year volatility. A single big flood year such as 2019 in the Midwest can dominate.
  - Check for SHELDUS reporting-practice changes over time (the data-quality critique cited in Q1).
  - Use a moving-block bootstrap over years for confidence intervals on test metrics.
- **Ranking-aware design.** With 97% zeros, aggregating test evaluation to county level over 2017–2023 gives a much more stable signal than county-month scoring, and it matches an allocation use case.

### Gaps
- No flood-specific paper was found that reports top-k hit rate or interval coverage for county loss predictions, so there is no external benchmark number for these metrics.
- Specific literature on calibration (Brier/reliability) for flood-damage occurrence was not retrieved in this session.
