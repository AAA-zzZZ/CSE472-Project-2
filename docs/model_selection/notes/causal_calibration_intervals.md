# Causal ML, Calibration Under Base-Rate Shift, and Prediction Intervals for a County-Month Flood-Loss Impact Model

Context: the target is tau(w; x, c), the effect of hazard intensity W (rainfall extremes, soil moisture) on county-month property loss Y, given exposure X and rain climate C, with backdoor path W <- C -> A -> Y. Data are 1,055 Midwest counties x 288 months, 3.2% nonzero, train 2000-2016, test 2017-2023. Predicted damage probabilities run 1.4x the test-period rate (up to 2.5x in some states) because reporting fell after 2016.

Verification note: in this session the documentation sites for EconML, DoubleML, MAPIE and scikit-learn could not be reached (DNS blocked), and arXiv could not be fetched directly. Library facts below were checked against **source code and READMEs on raw.githubusercontent.com** and **version numbers on PyPI**, on 2026-11-01. Paper facts come from web-search snippets of arXiv, journal and repository records. Anything marked **[unverified]** is a citation detail (DOI, volume or pages) from prior knowledge that I did not re-check this session.

## Q1. Causal estimation of a continuous treatment effect with ML (DML, GRF/causal forests, DR-learner, panel FE, overlap)

### Takeaway
A defensible plan has two layers. The baseline is the climate-econometrics panel design: county fixed effects plus time fixed effects, with W as within-county weather deviations. On top of it, use DML (EconML `LinearDML` or `CausalForestDML` with a continuous treatment, or the new DoubleML `DoubleMLPLPR` panel estimator) to get a heterogeneous effect tau(w; x, c), with C in the conditioning set to block the backdoor through adaptation A. The DR-learner and DoubleML's IRM/APO models need a discrete treatment, so they apply only if W is binned.

### Cited Findings
**Core DML theory**
- DML (Chernozhukov, Chetverikov, Demirer, Duflo, Hansen, Newey, Robins), "Double/debiased machine learning for treatment and structural parameters," *The Econometrics Journal* 21: C1-C68 (2018), doi:10.1111/ectj.12097. DoubleML is built on this paper and names its model classes: partially linear regression (PLR), partially linear IV (PLIV), interactive regression (IRM) and interactive IV (IIVM). — [DoubleML README](https://raw.githubusercontent.com/DoubleML/doubleml-for-py/main/README.md); [DOI](https://doi.org/10.1111/ectj.12097)
- The PLR model, Y = theta*D + g(X) + e, treats D as continuous. The score is "partialling out": residualize Y on X and D on X, then regress residual on residual. This identifies an average linear effect of W. — [DoubleMLPLR/PLPR source](https://raw.githubusercontent.com/DoubleML/doubleml-for-py/main/doubleml/plm/plpr.py)

**Nonparametric continuous treatments (dose-response)**
- Colangelo and Lee, "Double Debiased Machine Learning Nonparametric Inference with Continuous Treatments," arXiv:2004.03036 (v8, Sept 2023). They give a kernel-based DML estimator for the average dose-response function and partial effects of a continuous treatment. It is asymptotically normal at nonparametric rates and comes with a data-driven bandwidth. — [arXiv:2004.03036](https://arxiv.org/abs/2004.03036)
- Klosin, "Automatic Double Machine Learning for Continuous Treatment Effects," arXiv:2104.10334. It is a nonparametric estimator of the average dose-response function. — [arXiv:2104.10334](https://arxiv.org/pdf/2104.10334)
- A web search found no native continuous dose-response estimator in DoubleML. A DoubleML docs notebook instead discretizes a continuous treatment into quantile levels and uses discrete-treatment models. Third-party Python options are `causal-curve` and `npDoseResponse`. — [DoubleML docs PR](https://github.com/DoubleML/doubleml-docs/pull/252/files); [causal-curve on PyPI](https://pypi.org/project/causal-curve/); [npDoseResponse](https://npdoseresponse.readthedocs.io/en/latest/_sources/index.rst.txt)
- Kennedy, Ma, McHugh and Small (2017), "Non-parametric methods for doubly robust estimation of continuous treatment effects," *JRSS-B* 79(4), doi:10.1111/rssb.12212 **[unverified]**.

**Heterogeneous effects: GRF / causal forests and the DR-learner**
- Generalized random forests: Athey, Tibshirani and Wager, *Annals of Statistics* 47(2):1148-1178 (2019), doi:10.1214/18-AOS1709 **[unverified]**. Causal forests: Wager and Athey, *JASA* 113:1228-1242 (2018), doi:10.1080/01621459.2017.1319839 **[unverified]**.
- EconML `CausalForestDML` accepts `discrete_treatment=False`, i.e. a continuous T. Its arguments include `criterion='het'`, `min_samples_leaf` and `max_samples`, with nuisance models `model_y` and `model_t`. Confidence intervals come from "Bootstrap-of-Little-Bags". — [EconML README](https://raw.githubusercontent.com/py-why/EconML/main/README.md)
- EconML `LinearDML` gives OLS or bootstrap CIs for a CATE that is linear in X. `SparseLinearDML` gives debiased-lasso CIs. `NonParamDML` takes an arbitrary ML final stage. `DynamicDML` (econml.panel.dml) takes `groups=` for panels. `DMLOrthoForest` is listed with `discrete_treatment=False`. Meta-learners (S/T/X) are also included. — [EconML README](https://raw.githubusercontent.com/py-why/EconML/main/README.md)
- EconML's current release is v0.17.0 (July 31, 2026, per README; v0.17.0 also on PyPI). — [EconML README](https://raw.githubusercontent.com/py-why/EconML/main/README.md); [PyPI](https://pypi.org/pypi/econml/json)
- DR-learner: Kennedy, "Towards optimal doubly robust estimation of heterogeneous causal effects," *Electronic Journal of Statistics* 17(2):3008-3049 (2023), doi:10.1214/23-EJS2157, arXiv:2004.14497. It is a two-stage estimator that regresses a doubly robust pseudo-outcome (the uncentered efficient influence function) on covariates, with model-agnostic error bounds under double sample splitting. — [arXiv:2004.14497](https://arxiv.org/abs/2004.14497); [Project Euclid](https://projecteuclid.org/journals/electronic-journal-of-statistics/volume-17/issue-2/Towards-optimal-doubly-robust-estimation-of-heterogeneous-causal-effects/10.1214/23-EJS2157.full)
- The DR-learner's pseudo-outcome is built for a binary or discrete treatment. EconML's `DRLearner` is for discrete treatments only **[unverified for v0.17; from prior knowledge of the API]**.

**DML with panel fixed effects**
- Clarke and Polselli, "Double Machine Learning for Static Panel Models with Fixed Effects," arXiv:2312.08174 (v5, Dec 2024), accepted at *The Econometrics Journal*. They extend within-group, first-difference and correlated-random-effects approaches to Robinson's partially linear model, and they recommend first-differencing. In their Monte Carlo study, least squares does well even under nonlinear DGPs, and DML's bias reduction pays off when the true effect is nonlinear or discontinuous. — [arXiv:2312.08174](https://arxiv.org/abs/2312.08174v5)
- DoubleML's main branch now has `DoubleMLPLPR` ("Double machine learning for partially linear panel regression models"). It takes a `DoubleMLPanelData` object with `approach` in {`cre_general`, `cre_normal`, `fd_exact` (default), `wg_approx`} "in Clarke and Polselli (2025)". The package also exports `DoubleMLClusterData`, `DoubleMLAPO` and `DoubleMLAPOS` (average potential outcomes at discrete treatment levels), plus `DoubleMLBLP` (best linear predictor of CATE). — [DoubleML `__init__.py`](https://raw.githubusercontent.com/DoubleML/doubleml-for-py/main/doubleml/__init__.py); [plpr.py](https://raw.githubusercontent.com/DoubleML/doubleml-for-py/main/doubleml/plm/plpr.py)
- The DoubleML release on PyPI is 0.11.4. I did not check whether `DoubleMLPLPR` ships in 0.11.4 or only on main. — [PyPI](https://pypi.org/pypi/doubleml/json)

**Climate-econometrics panel designs and flood applications**
- Hsiang, "Climate Econometrics," *Annual Review of Resource Economics* 8(1):43-75 (2016), doi:10.1146/annurev-resource-100815-095343. It reviews how weather variation is used as identifying variation for climate impacts. NBER WP 22181 is the working-paper version. — [NBER w22181](https://www.nber.org/papers/w22181); [RePEc](https://ideas.repec.org/a/anr/reseco/v8y2016p43-75.html)
- Dell, Jones and Olken, "What Do We Learn from the Weather? The New Climate-Economy Literature," *Journal of Economic Literature* 52(3):740-798 (2014), doi:10.1257/jel.52.3.740 **[unverified]**.
- Closest applied analog: Davenport, Burke and Diffenbaugh, "Contribution of historical precipitation change to US flood damages," *PNAS* (2021), doi:10.1073/pnas.2017524118. They use fixed-effects panel regressions at the **state-month** level on more than 6,600 state-level flood damage reports. Their estimate is that about 36% of US flood damages in 1988-2017, roughly $73B (95% CI $39-91B), came from historical precipitation change. — [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/7848586/); [CA Water Library abstract](https://cawaterlibrary.net/?p=29571)
- Causal-forest applications in nearby environmental and climate settings exist, but I found none for flood damages. Examples: Stetter and Sauer, "Exploring the heterogeneous effects of weather on productivity using generalized random forests" (AES 2021 conference paper; only metadata seen); a causal-forest household study of climate immobility (arXiv:2403.09470); and fire-smoke air-quality effects (arXiv:2609.12977). — [RePEc AES 2021](https://ideas.repec.org/p/ags/aesc21/312074.html); [arXiv:2403.09470](https://arxiv.org/pdf/2403.09470); [arXiv:2609.12977](https://arxiv.org/pdf/2609.12977)

### Inferences
- **Identification for this DAG.** C (long-run rain climate) is time-invariant or slowly varying, and A (adaptation) depends on C. County fixed effects absorb C and the time-invariant part of A. That is the standard Hsiang/Dell-Jones-Olken argument: W, read as a within-county deviation, is as good as random. Two ways to proceed:
  - (a) Use FE/first-difference DML (`DoubleMLPLPR`, `fd_exact` or `wg_approx`) for an average effect.
  - (b) For heterogeneity tau(w; x, c), put C and X into the effect-modifier set (EconML's `X`). Put time controls (month-of-year, year or trend dummies, or county-demeaned features) into `W` (EconML's confounder argument; note the name clash with the hazard W). Residualizing hazard on county means is a practical substitute for FE inside `CausalForestDML`.
- **Year fixed effects also absorb the post-2016 reporting decline** when it is common across counties, or state-by-year fixed effects when it varies by state. Reporting probability then acts as a time-varying multiplicative measurement error in Y. It biases levels, but not within-period effects of W, as long as it does not depend on W. This is a strong argument for including time FE in the causal model even though the predictive model needs recalibration (Q2).
- **Nonlinearity in w.** Options:
  - Featurize W (splines or bins of rainfall percentiles) and use `LinearDML` or `CausalForestDML` on the multi-dimensional treatment.
  - Bin W into hazard classes and use DoubleML `DoubleMLAPOS`, or the EconML DR-learner, on the discrete levels.
  - Report the marginal effect d tau/dw from the PLR coefficient as a robustness check.
  Treatment featurizers exist in EconML (`treatment_featurizer`) **[unverified in v0.17 docs]**.
- **Zeros (96.8%).** Model Y as log(1+loss), or split it into a hurdle (effect on P(Y>0)) and an intensive margin. Linear-score DML works on either outcome. With a binary outcome, use a classifier for `model_y`.
- **Overlap/positivity with a continuous W.** Check the generalized propensity score. Fit `model_t` (the W | X, C nuisance) and inspect the residual variance of W given X and C across strata. Plot W's distribution against C deciles: wet-climate counties may never see the extreme percentiles that dry counties see. Trim regions where Var(W | X, C) is near 0, and restrict tau(w) to the empirical support of w within each C bin. Expressing W as county-specific percentiles (relative to the county's own climatology) improves overlap by design. The literature is standardized on this point: Hirano and Imbens (2004) GPS, and Kennedy et al. (2017) **[unverified]**.
- **Inference.** Errors are correlated within county over time and across neighbouring counties in the same month. Use cluster-robust SEs: DoubleML `DoubleMLClusterData` allows two-way clustering (county and month); EconML's `groups=` keeps a county's rows together in cross-fitting.

### Gaps
- Could not open DoubleML or EconML docs pages (DNS blocked), so I have not checked whether `DoubleMLPLPR` is in release 0.11.4, or the exact EconML v0.17 API for `treatment_featurizer` and `DRLearner` continuous-treatment support.
- Found no published paper that applies causal forests or DML specifically to flood damages or NFIP/SHELDUS losses at county level.
- Did not verify the GRF, causal-forest, Dell-Jones-Olken or Kennedy-2017 DOIs this session.

## Q2. Recalibration when the base rate shifts between train and test (prior/label shift)

### Takeaway
The 1.4x overprediction is a base-rate (prior) shift caused by reporting, not by hazard. Three fixes, cheapest first, all evaluated on a recent held-out window:
1. A Saerens et al. (2002) prior-shift correction of the logit, with the new prior either known (the 2017-2023 rate) or estimated by EM on unlabeled recent data.
2. Platt (sigmoid) recalibration fit on a recent window (e.g. 2014-2016, or rolling).
3. Isotonic recalibration, only where the window has enough positives (scikit-learn suggests more than about 1000 samples).
Fit state-specific intercepts if the over-prediction differs by state (1.4x overall, up to 2.5x in some states).

### Cited Findings
- Saerens, Latinne and Decaestecker, "Adjusting the Outputs of a Classifier to New a Priori Probabilities: A Simple Procedure," *Neural Computation* 14(1):21-41 (2002), doi:10.1162/089976602753284446. It corrects posterior probabilities for new class priors without retraining. An EM procedure also estimates the new priors from unlabeled data. — [UCLouvain record](https://research.dial.uclouvain.be/entities/publication/ff0a9d02-c8d6-4e6a-8320-5665e5cb85ba); [ULB full-text PDF](https://dipot.ulb.ac.be/dspace/bitstream/2013/68391/1/Decaestecker_NeuralComp02.pdf); [mlanthology](https://mlanthology.org/neco/2002/saerens2002neco-adjusting)
- scikit-learn `CalibratedClassifierCV` supports `method="sigmoid"` (Platt), `"isotonic"` and `"temperature"`. An already-fitted model can be recalibrated on separate data with `CalibratedClassifierCV(estimator=FrozenEstimator(estimator))`. "It is up to the user to make sure that the data used for fitting the classifier is disjoint from the data used for fitting the calibrator." — [scikit-learn calibration guide source](https://raw.githubusercontent.com/scikit-learn/scikit-learn/main/doc/modules/calibration.rst)
- scikit-learn guide: isotonic "will perform as well as or better than 'sigmoid' when there is enough data (greater than ~1000 samples)", but it is "more prone to overfitting, especially on small datasets", and it introduces ties that can change ROC-AUC. Sigmoid is strictly monotonic and preserves ranking. — [scikit-learn calibration guide source](https://raw.githubusercontent.com/scikit-learn/scikit-learn/main/doc/modules/calibration.rst)
- scikit-learn guide: reliability diagrams (`calibration_curve`, `CalibrationDisplay.from_estimator`). Brier score and log loss jointly measure calibration and discrimination, so a lower Brier does not by itself mean better calibration. — [same source](https://raw.githubusercontent.com/scikit-learn/scikit-learn/main/doc/modules/calibration.rst)
- Related label-shift methods: Lipton, Wang and Smola (2018), "Detecting and Correcting for Label Shift with Black Box Predictors" (BBSE), ICML, arXiv:1802.03916 **[unverified]**. Alexandari, Kundaje and Shrikumar (2020), "Maximum Likelihood with Bias-Corrected Calibration is Hard-To-Beat at Label Shift Adaptation," ICML, arXiv:1901.06852 **[unverified]**: EM à la Saerens works well when the model is first calibrated.

### Inferences
- **Closed-form Saerens correction (binary case).** With training prior pi_tr and target prior pi_te:
  logit p_new = logit p_old + log[pi_te / (1 - pi_te)] - log[pi_tr / (1 - pi_tr)]
  This shifts only the intercept. With per-state priors it becomes a state-specific intercept shift, matching the 1.4x versus 2.5x pattern. It is exactly a Platt recalibration with the slope fixed at 1.
- **The label-shift assumption P(x|y) = constant probably fails here.** A drop in reporting likely removes mostly *small* losses. The remaining positives then look more severe, so P(x|y=1) also shifts. Platt (free slope) or isotonic on a recent window can absorb that; Saerens cannot. Recommend comparing all three in a table.
- **Temporal validation design.**
  1. Train 2000-2013.
  2. Calibrate on 2014-2016, or better, on the most recent labeled window before the test period.
  3. Test 2017-2023.
  If the reporting drop starts in 2017, a pre-2017 calibration window cannot see it. The honest options: (a) treat 2017-2018 as the calibration window and report test metrics on 2019-2023; or (b) do rolling-origin evaluation (expanding window, recalibrate yearly, score the next year). Report both "frozen" and "recalibrated" results.
- **Frame for the write-up.** The causal tau(w; x, c) estimated with time FE is a separate object from P(Y>0) at a given time. Recalibration fixes the predictive base rate, while tau's within-period effect of W is unaffected under the assumptions in Q1.
- **Metrics.** Report the ratio of mean predicted to observed rate by year and state, reliability diagrams, Brier and log loss, and expected calibration error. Report AUC/PR-AUC separately, since recalibration should leave ranking roughly unchanged (exactly unchanged for sigmoid).

### Gaps
- Found no paper that studies prior-shift recalibration specifically for disaster-loss reporting changes (e.g. NFIP or SHELDUS reporting declines). The 1.4x/2.5x figures are the user's own and were not checked externally.
- Lipton 2018 and Alexandari 2020 citation details were not re-verified this session.

## Q3. Prediction intervals for skewed, zero-heavy targets (conformal, CQR, adaptive conformal, quantile GBMs) and how to report coverage

### Takeaway
Use **conformalized quantile regression (CQR)** with LightGBM quantile models: MAPIE's `ConformalizedQuantileRegressor` explicitly supports `LGBMRegressor`. Calibrate on a recent window. For the temporal shift, add **adaptive conformal inference (ACI)** via MAPIE's `TimeSeriesRegressor(method="aci")`, or weighted conformal (Barber et al. 2023). Because 96.8% of targets are zero, marginal coverage is nearly free (an interval of {0} covers most points). Report coverage **conditional on Y>0**, by state and by year, along with interval width. A two-stage hurdle conformal approach (prediction set {0} or an interval) fits this structure.

### Cited Findings
- Romano, Patterson and Candès, "Conformalized Quantile Regression," NeurIPS 32 (2019), arXiv:1905.03222. — [MAPIE README references](https://raw.githubusercontent.com/scikit-learn-contrib/MAPIE/master/README.md)
- MAPIE's `ConformalizedQuantileRegressor` and `CrossConformalizedQuantileRegressor` (in `mapie.regression`) recognize `QuantileRegressor`, `GradientBoostingRegressor` and `LGBMRegressor` (loss via `objective`, quantile via `alpha`) as valid quantile estimators. — [MAPIE quantile_regression.py](https://raw.githubusercontent.com/scikit-learn-contrib/MAPIE/master/mapie/regression/quantile_regression.py); [MAPIE regression __init__](https://raw.githubusercontent.com/scikit-learn-contrib/MAPIE/master/mapie/regression/__init__.py)
- MAPIE `TimeSeriesRegressor` has two methods, `"enbpi"` and `"aci"`. EnbPI (Xu and Xie, ICML 2021) updates conformal scores online through `update`. ACI (Gibbs and Candès) adjusts the working quantile when realized values fall outside the interval. — [MAPIE time_series_regression.py](https://raw.githubusercontent.com/scikit-learn-contrib/MAPIE/master/mapie/regression/time_series_regression.py)
- MAPIE v1 (2025) changed the API. In 2026 it added exchangeability tests ("to help users verify when MAPIE can be legitimately applied") and new adaptive conformal methods. The current PyPI version is 1.6.0. Cite MAPIE as Cordier et al., COPA 2023 (PMLR), or Taquet et al., arXiv:2207.12274. — [MAPIE README](https://raw.githubusercontent.com/scikit-learn-contrib/MAPIE/master/README.md); [PyPI](https://pypi.org/pypi/mapie/json)
- Gibbs and Candès, "Adaptive Conformal Inference Under Distribution Shift," NeurIPS 2021, arXiv:2106.00170. The update rule is alpha_{t+1} = alpha_t + gamma*(alpha - err_t). It guarantees the long-run coverage frequency "irrespective of the true data generating process", not per-step coverage. — [arXiv:2106.00170](https://arxiv.org/abs/2106.00170v3); [NeurIPS proceedings](https://proceedings.neurips.cc/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html)
- Barber, Candès, Ramdas and Tibshirani, "Conformal Prediction Beyond Exchangeability," *Annals of Statistics* 51(2):816-845 (2023), doi:10.1214/23-AOS2276, arXiv:2202.13415. It bounds the coverage gap under drift and proposes weighted split, full and jackknife+ conformal; for example, weighting recent calibration points more heavily. — [arXiv:2202.13415](https://arxiv.org/abs/2202.13415); [journal record](https://academicnewsletter.sufe.edu.cn/info/433941)
- Tibshirani, Barber, Candès and Ramdas, "Conformal Prediction Under Covariate Shift," NeurIPS 2019, arXiv:1904.06019 (likelihood-ratio weighting). — [arXiv:1904.06019](https://arxiv.org/abs/1904.06019)
- Zero-inflated conformal: Li et al., "Classification-Powered Conformal Inference for Zero-inflated Outcomes," arXiv:2605.04219 (May 2026). A classifier first decides zero versus nonzero, then conformal regression builds an interval for the nonzero part. Prediction sets are {0} or an interval, with marginal coverage under exchangeability and asymptotically minimal length. A third-party summary claims 60-80% shorter intervals at high zero proportions **[secondary claim; unverified]**. The paper is recent and I found no replication. — [arXiv:2605.04219](https://arxiv.org/abs/2605.04219); [review summary](https://www.themoonlight.io/review/classification-powered-conformal-inference-for-zero-inflated-outcomes)
- A 2025 paper notes that "there remains a lack of conformal approaches specifically tailored to zero-inflated data." — [arXiv:2508.10284](https://arxiv.org/pdf/2508.10284)
- Background: Angelopoulos and Bates, "Conformal prediction: A gentle introduction," *Foundations and Trends in ML* 16(4):494-591 (2023). — [MAPIE README references](https://raw.githubusercontent.com/scikit-learn-contrib/MAPIE/master/README.md)
- Later extensions: Zaffran et al. (2022), AgACI, aggregated ACI for time series, ICML, arXiv:2202.07282 **[unverified]**. Gibbs and Candès (2024), DtACI, JMLR, arXiv:2208.08401 **[unverified]**.

### Inferences
- **Recommended pipeline.**
  1. Hurdle stage: a calibrated classifier for P(Y>0), taken from Q2.
  2. Severity stage: LightGBM quantile regressors (`objective="quantile"`, alpha in {0.05, 0.5, 0.95}) on log(1+loss) for Y>0, conformalized with MAPIE CQR on the recent calibration window.
  3. Combined set: {0} when P(Y>0) is below a threshold chosen so the overall miscoverage budget holds (the CPCI idea); otherwise [0 or lower bound, upper bound].
  4. Shift adaptation: wrap with ACI (`TimeSeriesRegressor(method="aci")`) and update month by month through the 2017-2023 test period. Alternatively, use Barber-style weighted conformal with exponentially decaying weights on calibration months.
- **Exchangeability.** Split conformal assumes exchangeable calibration and test points. The post-2016 reporting drop breaks that, so static split-conformal coverage on 2017-2023 will likely be off; for losses it will likely over-cover because predictions are inflated. Show static split conformal against ACI or weighted conformal to make the point.
- **Months as the time index.** ACI is designed for a single sequence. With 1,055 counties per month, either run ACI on the pooled monthly miscoverage (one alpha_t shared across counties) or run one per state. Spatial correlation within a month means guarantees hold over months, not county-months.
- **How to report coverage (minimum table).**
  - Empirical coverage and mean or median width at nominal 80% and 90%, both overall and **for Y>0 only**.
  - Coverage by year (shows drift) and by state (ties to the 1.4x-2.5x pattern).
  - Coverage by predicted-risk decile.
  - The interval (Winkler) score, which penalizes width plus misses: Gneiting and Raftery (2007), *JASA* 102:359-378, doi:10.1198/016214506000001437 **[unverified]**.
  - Pinball loss for the raw quantile models.
  - For ACI, the rolling 12-month coverage curve against the target.
- **Feasibility.** Every piece is available in pip-installable Python:
  - scikit-learn: `CalibratedClassifierCV` and `FrozenEstimator` for recalibration; `QuantileRegressor` and `GradientBoostingRegressor(loss="quantile")`.
  - LightGBM: quantile and Tweedie objectives.
  - MAPIE 1.6.0: split, CV+/jackknife+, CQR, EnbPI, ACI.
  - EconML 0.17.0: `LinearDML`, `CausalForestDML` with continuous T, DR-learner for binned T.
  - DoubleML 0.11.4: PLR, IRM, APO/APOS, cluster data; `DoubleMLPLPR` on main.
  Prior-shift correction is a few lines of NumPy. The CPCI zero-inflated method has no package that I found, but it can be composed from a classifier plus MAPIE.

### Gaps
- Could not open MAPIE's docs to confirm v1.6.0 class names for split conformal (`SplitConformalRegressor`) or the new 2026 adaptive methods. I only confirmed `ConformalizedQuantileRegressor`, `CrossConformalizedQuantileRegressor` and `TimeSeriesRegressor` (enbpi/aci) in master-branch source.
- Found no application of conformal prediction to county-level flood or disaster loss data.
- No code was found for the CPCI zero-inflated method (arXiv:2605.04219).
