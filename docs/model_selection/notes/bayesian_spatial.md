# Bayesian spatial and spatio-temporal hurdle models for zero-heavy county-month flood loss (second method)

Context: 1,055 US counties x 288 months = 303,840 rows, 3.2% nonzero (about 9,700 positive rows), heavy-tailed positive amounts.

Access note: during this research, paulamoraga.com, arxiv.org, inlabru-courses.github.io and search.r-project.org did not resolve from the sandbox, and GitHub API access to the Moraga book repository was not enabled. Content from those sites below comes from search-engine abstracts and snippets only and is marked "(snippet-verified)". DOIs marked "(DOI from memory, unverified)" were not confirmed online in this session.

## 1. Which spatial prior suits county areal data (BYM, BYM2, Leroux, SPDE), how to add time, and what is feasible in R-INLA at about 300k rows

### Takeaway
For US county polygons, BYM2 with PC priors is the standard and most interpretable choice. Leroux is a close alternative, and SPDE is for point-referenced data, so it is the wrong tool here. Main effects for time are cheap: a BYM2 county effect, an rw1/ar1 effect for year (24 levels), and a cyclic rw2 effect for calendar month (12 levels). A full county-by-month Knorr-Held Type IV interaction (303,840 latent nodes with about 1,342 constraints) is the expensive part. It is feasible only with care, so start with Type I, or with Type II/IV interactions on county x year rather than county x month.

### Cited Findings
- Riebler, Sørbye, Simpson & Rue (2016), "An intuitive Bayesian spatial model for disease mapping that accounts for scaling," *Statistical Methods in Medical Research* 25(4):1145-1165 (arXiv 1601.01180; DOI 10.1177/0962280216660421, from memory, unverified). The paper introduces BYM2. It scales the ICAR component so that hyperpriors are interpretable and transferable across graphs with different structure, and it maps the precision parameter to a marginal standard deviation. PC priors on (sigma, phi) shrink toward a base model. The authors report that BYM2 "performs at least equally well as existing parameterisations, but only the new formulation offers parameters that are interpretable and hyperpriors that have a clear meaning." Fitting uses INLA without MCMC. — [arXiv 1601.01180](https://www.arxiv.org/abs/1601.01180); [Bath research portal](https://researchportal.bath.ac.uk/en/publications/an-intuitive-bayesian-spatial-model-for-disease-mapping-that-acco/)
- The bigDM package offers spatial CAR priors and spatio-temporal CAR models (`CAR_INLA`, `STCAR_INLA`, `MCAR_INLA`) for high-dimensional areal count data, all fitted with INLA. It uses a divide-and-conquer partition of the map (`clustering_partition` uses DBSC; `random_partition` uses a regular grid). It requires INLA 22.11.22 or later. — [bigDM README (CRAN mirror)](https://www.stats.bris.ac.uk/R/web/packages/bigDM/readme/README.html)
- Orozco-Acosta, Adin & Ugarte (2021), "Scalable Bayesian modeling for smoothing disease mapping risks in large spatial data sets using INLA," *Spatial Statistics* (DOI 10.1016/j.spasta.2021.100496, from memory, unverified). On colorectal cancer mortality across about 7,900 Spanish municipalities, the scalable model beat the standard global model on both goodness of fit and computation time. A follow-up preprint (2022) covers parallel and distributed spatio-temporal versions. — [Universidad Pública de Navarra repository](https://academica-e.unavarra.es/handle/2454/47055); [bigDM README](https://www.stats.bris.ac.uk/R/web/packages/bigDM/readme/README.html)
- Knorr-Held interaction Type IV is structured in both space and time and needs additional sum-to-zero constraints for identifiability (Schrödle & Held 2011). "The high number of constraints makes the models hard to compute for large studies, where either the number of time steps or the number of spatial regions is very large." Aanes & Storvik's HyMiK method treats part of the constraints as mixed effects and the rest by conditioning by kriging, giving a 2x to 4x speed-up with very similar results using standard INLA. — [Aanes & Storvik, arXiv 2304.11851](https://ar5iv.labs.arxiv.org/html/2304.11851)
- Abdul-Fattah, van Niekerk & Rue (arXiv 2206.09287) reformulate INLA with dense matrices so that compute time does not depend on the number of constraints for interaction Types I-IV, reporting up to a 40-fold speed-up over INLA in realistic scenarios (snippet-verified). — [arXiv 2206.09287 summary](https://arxiv.deeppaper.ai/papers/2206.09287v1)
- van Niekerk, Krainski, Rustand & Rue (2023), "A new avenue for Bayesian inference with INLA," *Computational Statistics & Data Analysis* 181:107692. The paper removes the linear predictor from the latent field ("extended latent Gaussian model"), which makes INLA faster and more stable for data-rich models: low-dimensional latent structure with high-dimensional data, which is this project's binomial part with 303,840 rows. Recent R-INLA uses this mode by default (the name `inla.mode="compact"` is from memory, unverified). — [arXiv 2204.06797](https://arxiv.org/pdf/2204.06797)
- Knorr-Held (2000), "Bayesian modelling of inseparable space-time variation in disease risk," *Statistics in Medicine* 19:2555-2567, defines the four interaction types. In Type I, delta_it is iid. Type II takes the temporal structure (rw) independently per area. Type III takes the spatial structure (ICAR) independently per time point. Type IV takes the Kronecker product of the two. — citation from memory, unverified; the computational consequences are described in [Aanes & Storvik](https://ar5iv.labs.arxiv.org/html/2304.11851)
- The Moraga book chapter recommended by the instructor (https://www.paulamoraga.com/book-spatial/bayesian-spatial-models.html) could not be fetched (host blocked). Its content is therefore not verified in these notes; see Gaps.

### Inferences
- SPDE assumes a continuous Gaussian field over point locations. With county aggregates, the adjacency-based BYM2 (built from a `spdep::poly2nb` graph, with islands or disconnected counties handled through `scale.model=TRUE` and per-component scaling) is the natural fit. Leroux (`model="besagproper2"` in INLA) is fine but has no transferable PC prior as standard.
- A suggested baseline formula for each hurdle part: `~ covariates + f(county, model="bym2", graph=g, scale.model=TRUE, hyper=pc) + f(year, model="rw1" or "ar1") + f(month, model="rw2", cyclic=TRUE) + f(county_year_iid)`. Each term has a small latent dimension: 1,055 x 2 + 24 + 12. Even with 303,840 binomial rows this should fit in minutes on a laptop.
- The Type IV county x month interaction adds 303,840 latent nodes and 1,055 + 288 - 1 = 1,342 constraints, which is very costly. A county x year Type II or IV interaction (25,320 nodes) captures "this county had a bad year" at much lower cost, while a Type I iid term per county-month is cheap but adds little.
- The positive (amount) part has only about 9,700 rows. A complex space-time interaction there would be poorly identified, so keep it to BYM2 plus year and month main effects.
- bigDM supports Poisson count likelihoods only (as far as the README describes). It is useful if the project switches to modelling the event count per county-month, not the amounts.

### Gaps
- Exact text and code from Moraga's "Bayesian spatial models" chapter (blocked host). It is generally known to cover INLA areal models such as BYM2 with PC priors, but this is not verified here.
- No published timing benchmark was found for INLA on 300k-row binomial models with BYM2. The feasibility claims above are inferences from the latent dimension.
- The Leroux et al. (2000) original citation was not retrieved.

## 2. How to build a hurdle model in INLA; limitations of the zeroinflated families; alternatives (brms, Stan, PyMC, inlabru, bigDM)

### Takeaway
The recommended INLA construction is a joint model with two likelihoods stacked in one fit. A binomial (logit) part models P(loss > 0) on all 303,840 rows. A Gaussian part on log(amount), or a gamma part on amount, models the about 9,700 positive rows. The spatial effect can be shared through `copy=` with an estimated scaling coefficient. INLA's built-in zeroinflated families are mixtures in which the zero probability is a single hyperparameter, not a function of covariates. That makes them a poor fit when the probability of a loss varies by county and season. brms `hurdle_lognormal` with `car(type="bym2")` is the most convenient alternative for full MCMC, but it is untested at this scale.

### Cited Findings
- An inlabru course practical (New Caledonia 2026) shows the hurdle model as a binomial likelihood for presence/absence plus a truncated count likelihood for positives. A shared spatial component is defined once and reused in the second part through a `copy` term with the scaling left unfixed. The practical also notes that without a shared component nothing links the two parts' parameters, so they could be estimated separately (snippet-verified; host blocked). — [inlabru practical: Zero Inflated](https://inlabru-courses.github.io/NewCaledonia2026/practical_zero_inflated.html)
- An R-INLA discussion-group thread shows a spatio-temporal binomial/gamma hurdle with covariates. It shares a random effect across the two parts via `copy=` using SPDE models. — [R-INLA group: spatio-temporal joint (hurdle) model](https://groups.google.com/g/r-inla-discussion-group/c/tuhR_QW-D-8)
- A 2025 R-INLA group thread discusses a BYM2 hurdle joint model with stacked responses (binomial plus a censored or truncated Poisson part). It is the closest worked areal BYM2 example. — [R-INLA group: BYM2 hurdle joint model with stacked responses](https://groups.google.com/g/r-inla-discussion-group/c/3HWyQ78OtQA)
- A 2017 R-sig-Geo reply on fitting a spatial hurdle model in INLA points to a joint Bernoulli (zeros) plus Gamma (positives) spatio-temporal model (Muñoz et al. 2016) as the template. — [R-sig-Geo 2017](https://stat.ethz.ch/pipermail/r-sig-geo/2017-February/025440.html)
- Another R-INLA thread discusses which likelihoods to use for a hurdle model and flags the misuse of zero-inflated likelihoods as hurdles. In INLA, `zeroinflatedpoisson0` and `zeroinflatednbinomial0` are the hurdle (zero-truncated) variants and the `...1` versions are mixtures. — [R-INLA group: Likelihoods for a hurdle model](https://groups.google.com/g/r-inla-discussion-group/c/DPvHIGcbd0E) (the type0/type1 definitions are from memory of the INLA likelihood docs, unverified)
- In brms, `car()` supports types "escar" (default), "esicar", "icar" and "bym2", with icar and bym2 implemented from Mitzi Morris's Stan case study. — [brms car() docs](https://rdrr.io/pkg/brms/man/car.html)
- On the Stan forums, the suggested way to put a spatial effect in the hurdle part is `hu ~ X + car(W, gr = unit, type = "bym2")`. A separate thread reports "SAR terms are not implemented for this family" for `sar()` with `hurdle_lognormal`. That error concerns `sar()`, not `car()`. — [Stan Discourse: BYM2 on hurdle component](https://discourse.mc-stan.org/t/hurdle-model-with-bym2-correlation-structure-on-hurdle-component/13391); [Stan Discourse: spatial autocorrelation in brms hurdle](https://discourse.mc-stan.org/t/considering-spatial-autocorrelation-in-hurdle-model-using-brms/25368)
- No confirmed working example of `hurdle_lognormal` combined with `car(type="bym2")` was found. Checking `make_stancode()` before relying on it is advised. — [same Stan Discourse threads](https://discourse.mc-stan.org/t/considering-spatial-autocorrelation-in-hurdle-model-using-brms/25368)

### Inferences
- A concrete INLA recipe:
  1. Build a two-column response matrix `Y = cbind(z, y_log)`, where z is 0/1 for all rows (NA in column 2) and y_log = log(amount) for positive rows only (NA in column 1). Duplicate the rows of the positive part. Gaussian on log amount is equivalent to a lognormal hurdle. Gamma with a log link is an alternative but has lighter tails.
  2. Use separate intercepts and covariates per part. Give the binomial part `f(county1, model="bym2", graph=g)` and the positive part `f(county2, copy="county1", fixed=FALSE)` (beta scaling), or an independent BYM2 for each part.
  3. Use `family=c("binomial","gaussian")` and `control.compute=list(waic=TRUE, cpo=TRUE)`. In inlabru, use `bru(comp, like(...binomial...), like(...gaussian...))` with a shared component.
- Because the positive part has only about 9,700 rows spread unevenly over counties, sharing (copying) the county effect from the data-rich binomial part is exactly what "borrows strength" for counties with few past events.
- Very heavy tails on positive amounts: a lognormal (Gaussian on log) may still understate extremes. Options are a Student-t on log amounts (`family="T"`) or the extended generalised Pareto (eGP) likelihood. Hu et al. (2026) implemented eGP in INLA for burned area (see Section 5).
- PyMC and Stan (hand-coded hurdle with ICAR or BYM2, following Morris's case study) are flexible. NUTS on 303,840 Bernoulli rows plus 1,055 + temporal latents is feasible but slow (hours). Aggregating the binomial part to binomial counts per county x month cell does not help, because each cell has one row; aggregating to county x calendar-month x covariate bins could.
- Treating INLA as the main Bayesian tool and brms or Stan as a sensitivity check is the pragmatic split.

### Gaps
- Exact R-INLA documentation text on the zeroinflated families (inla-project.org was not tested). The claim that the zero-probability hyperparameter cannot depend on covariates is from general knowledge, unverified here.
- No benchmarks were found comparing INLA hurdle with brms hurdle on large areal data.
- The full citation for Muñoz et al. (2016) was not retrieved.

## 3. Published applications to flood, disaster or insurance losses or similar zero-heavy areal outcomes, and predictive skill compared with GLMs or tree ensembles

### Takeaway
Directly comparable published work is thin. The nearest examples are a 2026 INLA preprint on French flood insurance, a Bayesian spatial weather-claims model for 319 Norwegian municipalities, a Norwegian water-damage ICAR/BYM pricing study, and the Portuguese wildfire XGBoost+INLA paper. In this literature, spatial random effects mainly help occurrence (frequency) rather than severity. No paper was found that benchmarks a Bayesian spatial hurdle model head-to-head against GBMs on zero-heavy areal losses, so the project's own comparison would be novel.

### Cited Findings
- Moriah, Vermet, Ailliot, Naveau & Legrand (2026 preprint), "Bayesian spatial modelling framework for assessing residential flood risk in property insurance." Point-referenced (SPDE) INLA models for claim occurrence and severity at the policyholder level on a French portfolio. Spatial dependence clearly improves occurrence prediction, with smaller gains for severity (snippet-verified; not peer reviewed). — [arXiv 2607.07609](https://arxiv.org/abs/2607.07609)
- Scheel et al. (2013), "A Bayesian hierarchical model with spatial variable selection: the effect of weather on insurance claims," *JRSS Series C* 62(1):85-100. Daily weather and claims data 1997-2006 for the 319 municipalities of southern and central Norway (Gjensidige, private buildings). Claim counts only, with spatially smoothed variable selection fitted by Gibbs sampling and reversible-jump MCMC. The authors report "precise out-of-sample predictions" and regional differences in weather effects, and suggest use for pricing and short- or long-term prediction. — [PMC3563012](https://pmc.ncbi.nlm.nih.gov/articles/PMC3563012)
- A Norwegian water-damage risk-premium study compared ICAR, BYM, independent random effects and spline models on about seven million policy observations. It reports that for big data, frequentist mgcv/REML gives "identical estimates at a much lower computational cost when compared with INLA" (snippet-verified). — [Norsk Regnesentral publication](https://nr.no/publikasjon/1924734/)
- A French home-insurance flood study found that rainfall indicators, especially a new metric for intense local precipitation, substantially improve claim modelling. It is frequency-severity modelling, not Bayesian spatial (snippet-verified). — [arXiv 2603.02418](https://arxiv.org/html/2603.02418v1)
- A norovirus wastewater study (2026 preprint) compared INLA-SPDE with random forest, the best ML comparator on accuracy, calibration and speed. The two gave similar weekly predictions, but INLA had wider uncertainty. The outcome is a continuous concentration, not zero-heavy (snippet-verified). — [arXiv 2609.20038](https://arxiv.org/pdf/2609.20038)
- A dengue study notes that zero-inflated incidence lowers ML prediction accuracy and proposes a hybrid ML approach without INLA (snippet-verified). — [Bohrium summary](https://bohrium.dp.tech/paper/arxiv/36869118)

### Inferences
- Expect the Bayesian hurdle model to be competitive with, but probably not better than, a tuned GBM on point metrics (RMSE/MAE of loss). Its advantages should appear in calibrated predictive intervals, in proper scores (log score/CRPS) on rare counties, and in the smoothed county risk surface.
- A fair comparison would use the same temporal holdout, evaluate both parts separately (AUC/Brier for occurrence; RMSE/CRPS on log amounts for severity) and the combined expected loss, and check calibration of intervals or quantiles.

### Gaps
- No published US county-level NFIP/OpenFEMA Bayesian spatial hurdle study was found.
- No quantitative skill numbers (e.g., Brier or CRPS deltas versus GLM or GBM) were retrievable from the insurance papers, because the full texts were blocked.

## 4. Spatial confounding (Hodges & Reich 2010; Hanks et al. 2015; Khan & Calder 2022) and what it means for covariate effects such as rain climate

### Takeaway
When a covariate is itself spatially smooth (a long-run county rain climatology, elevation, coastal exposure), adding a BYM2 county effect can absorb part of its effect. That shifts and inflates the uncertainty of its coefficient. Restricted spatial regression (RSR) "fixes" the point estimate, but its intervals can be badly anticonservative for areal data. So treat covariate coefficients in the spatial model as conditional, partially confounded associations, not causal effects, and focus interpretation on prediction and the time-varying (within-county) covariates.

### Cited Findings
- Hodges & Reich (2010), "Adding spatially-correlated errors can mess up the fixed effect you love," *The American Statistician* 64(4):325-334 (DOI 10.1198/tast.2010.10052, from memory, unverified). Spatial random effects can shift fixed-effect estimates, and the paper proposes restricting the random effect to the orthogonal complement of the fixed effects (RSR). — [UMN Experts](https://experts.umn.edu/en/publications/adding-spatially-correlated-errors-can-mess-up-the-fixed-effect-y/)
- Hanks, Schliep, Hooten & Hoeting (2015), "Restricted spatial regression in practice: geostatistical models, confounding, and robustness under model misspecification," *Environmetrics* 26:243-254 (DOI 10.1002/env.2331, from memory, unverified). In a Bayesian setting, unrestricted coefficients can be recovered from posterior samples. RSR can give poorer coverage and inappropriately narrow intervals under misspecification. — [USGS publication page](https://www.usgs.gov/publications/restricted-spatial-regression-practice-geostatistical-models-confounding-and)
- Khan & Calder (2022), "Restricted spatial regression methods: implications for inference," *JASA* 117(537):482-494 (DOI 10.1080/01621459.2020.1788949, from memory, unverified). For discrete (areal) support, RSR typically gives poorer coverage than even non-spatial models. — [arXiv 1905.09371](https://ar5iv.labs.arxiv.org/html/1905.09371)
- Later work: traditional spatial estimators (GLS, splines) beat OLS in most realistic confounding scenarios, and Bradley (2024) argues RSR is reasonable once its interpretation is clarified. — [arXiv 2308.12181](https://arxiv.org/html/2308.12181v4); [arXiv 2311.18039](https://arxiv.org/pdf/2311.18039)

### Inferences
- For this project, a static county rain climate (e.g., a 30-year mean) is nearly collinear with low-frequency eigenvectors of the BYM2 graph. Its coefficient will shrink or widen when BYM2 is added. Monthly precipitation anomalies vary within county over time and are much less confounded.
- Practical reporting:
  1. Show the coefficient with and without the spatial effect.
  2. Report the BYM2 phi (share of variance that is spatially structured) and sigma.
  3. Describe effects as "conditional on county-level spatial heterogeneity."
  4. Avoid causal claims about static county covariates.
- Spatial confounding mostly affects inference, not prediction. The predictive comparison with ML is unaffected.

### Gaps
- No paper was found that studies spatial confounding specifically in hurdle or two-part models.

## 5. Hybrid approaches: GBM prediction as offset or covariate in INLA, or spatial random effects as GBM features

### Takeaway
There is now peer-reviewed precedent: Hu et al. (2026, *Environmetrics*) feed an XGBoost forecast into an INLA latent Gaussian model as a synthetic covariate alongside spatial and temporal random effects, and INLA-RF (2025) uses a random-forest prediction as an offset or correction. This hybrid fits the project directly. Use GBM predictions of logit P(loss) and of E[log amount] as covariates or offsets in the two INLA hurdle parts, then read the BYM2 effect as residual spatial structure that the GBM missed. The reverse direction (posterior BYM2 means as GBM features) is plausible but was not found in published form.

### Cited Findings
- Hu, Bispo, Rue, DaCamara, Swallow & Castro-Camilo (2026), "XGBoost meets INLA: a two-stage spatio-temporal forecasting of wildfires in Portugal," *Environmetrics* 37(3):e70089, DOI 10.1002/env.70089 (arXiv 2508.09896, Aug 2025). Stage 1: XGBoost trained on windowed environmental covariates and wildfire history up to t predicts activity at t+1. Stage 2: the XGBoost forecast enters as a synthetic future covariate in an INLA latent Gaussian model with spatial and temporal Gaussian effects, giving posterior predictive distributions. The stated benefits are less reliance on future covariates, getting around INLA's difficulty with many predictors, and capturing complex interactions. The authors implement the extended generalised Pareto (eGP) likelihood in INLA with PC priors, for moderate and extreme events. Targets are monthly fire counts and burned area by council (about 278 councils, from memory, unverified). — [arXiv 2508.09896](https://arxiv.org/pdf/2508.09896); [Glasgow eprints](https://eprints.gla.ac.uk/382153)
- INLA-RF (arXiv 2507.18488, 2025) feeds random-forest predictions into INLA-SPDE, either as an offset or as a correction to latent field nodes. The authors report better spatio-temporal prediction "while maintaining interpretability and coherence in uncertainty estimates," evaluated on simulated environmental data (snippet-verified). — [arXiv 2507.18488](https://arxiv.org/html/2507.18488v1)

### Inferences
- Hybrid recipe:
  1. Fit LightGBM or XGBoost hurdle components out-of-fold (time-blocked folds) to avoid leakage.
  2. Add `logit(p_gbm)` to the INLA binomial part and `mu_gbm` (predicted log amount) to the Gaussian part, as covariates with an estimated coefficient (better than fixed offsets, since they let INLA recalibrate).
  3. Keep BYM2 plus temporal effects to capture residual spatial and temporal structure and to produce uncertainty.
- Using out-of-fold rather than in-sample GBM predictions is critical. In-sample GBM fits on 303k rows would overfit and leave the random effects nothing to explain.
- The reverse direction is to use posterior means of the BYM2 county effects from a training-period INLA fit, or simpler target-encoded county history, as GBM features. It gives GBMs a smoothed county risk prior, which helps counties with few events, but it does not give uncertainty.
- The hybrid's skill gain over plain GBM is likely to be modest on point metrics. The main deliverable is calibrated predictive distributions and interpretable residual spatial maps.

### Gaps
- Quantitative skill results from Hu et al. (2026) and INLA-RF could not be extracted (arXiv blocked; journal paywalled). The direction and magnitude of gains over XGBoost alone are unverified.
- No published example was found of the hybrid applied to a hurdle (two-part) structure specifically.
