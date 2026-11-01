# Predictive Models for Zero-Inflated, Heavy-Tailed Flood/Disaster Loss Data

Method note: page fetches were blocked in this session (arxiv.org and frontiersin.org did not resolve), so every finding below comes from search-engine snippets of abstracts, documentation pages and indexes. Numbers marked **[snippet]** were seen only in search snippets of the primary source's abstract. Items marked **[unverified, background knowledge]** come from the researcher's prior knowledge and were not confirmed in this session. The report writer should treat them as leads, not facts.

## Q1. In published comparisons on disaster, flood, insurance-claim or other zero-heavy loss data, how do GBM hurdle models, Tweedie GBMs, random forests and GLM hurdles rank?

### Takeaway
No published study benchmarks all of these families on flood or disaster loss data at county-month resolution. The available evidence comes in pieces. Tree ensembles (RF, bagging, XGBoost) consistently beat depth-damage functions, linear models and GLMs on flood-loss data. In insurance claims work, boosted Tweedie and zero-inflated-Tweedie GBMs beat Tweedie or Poisson GLMs, with CatBoost often the strongest library. The one direct hurdle-GBM vs Tweedie-GBM comparison found favours the hurdle, but it uses retail (customer lifetime value) data. The project should run its own head-to-head on the same temporal split.

### Cited Findings
**Flood and disaster loss studies**
- Salas, Saha & Ravela (2022), "Learning Inter-Annual Flood Loss Risk Models From Historical Flood Insurance Claims and Extreme Rainfall Data", arXiv:2212.08660. Compares conditional GANs (neural network), XGBoost and Gaussian-process regressors on NFIP claims. Reports R² = 0.807 for coastal counties in eight US South-West states. In 11 high-claim counties, "Extreme Gradient Boosting provides the best results". Adding a Daymet rainfall predictor improved performance, and Burr-distribution bias correction improved distributional match **[snippet]**. — [arXiv abstract](https://arxiv.org/abs/2212.08660); [MIT Climate Extremes listing](https://www.climate-extremes.mit.edu/publicationslist/publications1-dxd6x)
- Alipour, Ahmadalipour, Abbaszadeh & Moradkhani (2020), "Leveraging machine learning for predicting flash flood damage in the Southeast US", *Environmental Research Letters* 15(2), DOI 10.1088/1748-9326/ab6edd. Uses more than 14,000 flash-flood events and hazard, exposure and vulnerability features. Random forest is used in two stages, effectively a two-part model: (1) a binary classifier for whether a region was damaged, about 81% accuracy; (2) a regression on transformed damage amounts with "good agreement" with observed property damage **[snippet; no AUC or PR-AUC reported in snippets]**. — [Moradkhani lab page](https://moradkhani.ua.edu/archives/2393); [Bohrium index](https://www.bohrium.com/paper-details/leveraging-machine-learning-for-predicting-flash-flood-damage-in-the-southeast-us/812687788246827009-2992)
- Collins et al. (2022), "Predicting flood damage probability across the conterminous United States", *Environmental Research Letters*. A random forest trained on 71,434 historical flood-damage locations with geospatial predictors reached an average AUC of 0.75 **[snippet]**. — [USGS publication page](https://www.usgs.gov/publications/predicting-flood-damage-probability-across-conterminous-united-states); [USGS Pubs 70236587](https://pubs.usgs.gov/publication/70236587)
- Merz, Kreibich & Lall (2013), NHESS 13:53. Regression trees and bagging decision trees on more than 1,000 German household flood-damage records, compared with stage-damage functions. Later GFZ work describes these trees as showing "superior performance" for flood-loss estimation. — [NHESS 13/53/2013](https://nhess.copernicus.org/articles/13/53/2013/); [GFZ PDF](https://gfzpublic.gfz-potsdam.de/pubman/item/item_3155889_4/component/file_3158909/3155889.pdf)
- Wagenaar, de Jong & Bouwer (2017), NHESS. On the 1993 Meuse flood, compares regression trees, bagging, random forest and a Bayesian network against depth-damage models. States that supervised learning on multi-variable data "can produce significantly better flood damage estimates", but needs extensive data. — [DOAJ record](https://doaj.org/article/350ff8eae946441fb868c26390f37be0)
- Kreibich, Botto, Merz & Schröter (2017), "Probabilistic, Multivariable Flood Loss Modeling on the Mesoscale with BT-FLEMO", *Risk Analysis* 37(4):774-787. Bagging trees at municipality scale (19 municipalities, 2002 Mulde flood), validated against six deterministic models. The approach also yields predictive uncertainty. — [RePEc](https://econpapers.repec.org/RePEc:wly:riskan:v:37:y:2017:i:4:p:774-787)
- 2026 EGUsphere preprint, "Outrunning flash floods: XGBoost and sparse impact reports deliver global medium-range probabilistic forecasts of flash flood occurrence". XGBoost trained on NOAA Storm Events (2001-2020, CONUS) with ERA5 inputs and SHAP. Benchmarked against other GBM libraries, random forests and a feed-forward neural network **[snippet; rankings not seen]**. — [EGUsphere egusphere-2026-1591](https://egusphere.copernicus.org/preprints/2026/egusphere-2026-1591/)
- A 2026 *Frontiers in AI* paper on an ML insurance pipeline for disaster claims reportedly finds strong random-split accuracy that falls sharply under temporal splits **[snippet from search summary only; could not open]**. — [Frontiers frai.2026.1802461](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1802461/full); see also [PMC13312540](https://pmc.ncbi.nlm.nih.gov/articles/PMC13312540/)
- No SHELDUS-based ML benchmark of these model families was found in searches.

**Insurance-claim / zero-inflated loss studies (actuarial)**
- Yang, Qian & Zou (2018), "Insurance Premium Prediction via Gradient Tree-Boosted Tweedie Compound Poisson Models" (TDboost), *J. Business & Economic Statistics*. Argues that the linear log-mean of a Tweedie GLM is too rigid. On auto-insurance data, the boosted Tweedie gives more accurate premium predictions than existing methods, including the Tweedie GLM **[snippet]**. — [UMN Experts](https://experts.umn.edu/en/publications/insurance-premium-prediction-via-gradient-tree-boosted-tweedie-co/); [author PDF](https://myweb.uiowa.edu/boxwang/papers/sktweedie.pdf)
- Zhou, Qian & Yang, "Tweedie Gradient Boosting for Extremely Unbalanced Zero-inflated Data" (EMTboost), arXiv:1811.10192. Zero-inflated Tweedie boosting fitted with EM, aimed at extremely imbalanced data (synthetic and auto-insurance). — [arXiv PDF](https://arxiv.org/pdf/1811.10192); [ResearchGate](https://www.researchgate.net/publication/342875431_Tweedie_gradient_boosting_for_extremely_unbalanced_zero-inflated_data)
- So (2023/24), "Enhanced Gradient Boosting for Zero-Inflated Insurance Claims and Comparative Analysis of CatBoost, XGBoost, and LightGBM", arXiv:2307.07771 (indexed as published in *Scandinavian Actuarial Journal*). Proposes a zero-inflated Poisson boosted tree and compares it with a Poisson boosted tree, a ZIP model and a Poisson GLM. Concludes that CatBoost is best for auto claim-frequency models on predictive performance, and that LightGBM is the fastest but not the most accurate **[snippet]**. — [arXiv](https://arxiv.org/pdf/2307.07771); [ResearchGate](https://www.researchgate.net/publication/372416039_Enhanced_Gradient_Boosting_for_Zero-Inflated_Insurance_Claims_and_Comparative_Analysis_of_CatBoost_XGBoost_and_LightGBM)
- So & Valdez (2024), "Zero-Inflated Tweedie Boosted Trees with CatBoost for Insurance Loss Analytics", arXiv:2406.16206. Models zero claims separately, with the zero-inflation probability linked to the mean, on a telematics dataset. Reports "a marked improvement" over a plain Tweedie model **[snippet; no Gini numbers seen]**. A related paper, "Advancing Zero-Inflated Tweedie Models and Evaluating Gradient Boosting Libraries for Auto Claims", appears in *North American Actuarial Journal* 29(4):887-904 (2025). It is likely the published version, but this was not confirmed. — [arXiv 2406.16206](https://arxiv.org/abs/2406.16206v1); [IDEAS/RePEc NAAJ](https://ideas.repec.org/a/taf/uaajxx/v29y2025i4p887-904.html)
- Two-stage hurdle LightGBM vs single-stage Tweedie (2025/26, *Applied Sciences* 16(13):6550, DOI 10.3390/app16136550). On customer-lifetime-value data with 62.5% zeros, the ranking is Two-stage Hurdle > Single-MSE > Tweedie, with p < 0.05. LightGBM-Tweedie (power fixed at 1.5) gave R² = -0.287. Caveats: a single dataset, a single variance power, and far fewer zeros than the 96.8% in this project **[snippet]**. — [MDPI](https://www.mdpi.com/2076-3417/16/13/6550)

### Inferences
- Expected ranking for this project, inferred from the evidence above rather than from any direct benchmark: GBM (LightGBM, XGBoost or CatBoost) hurdle ≈ Tweedie GBM > random forest hurdle > GLM hurdle or Tweedie GLM ≫ ZIP/ZINB GLMs. The flood literature favours tree ensembles over parametric models. The actuarial literature favours boosted over GLM Tweedie, and CatBoost slightly over XGBoost and LightGBM.
- Zero-inflated count models (ZIP/ZINB) fit the outcome poorly: SHELDUS losses are continuous dollars, not counts. They only apply to an event-count target.
- With 3.2% positives (about 9,700 nonzero rows) and a heavy tail, the severity stage of a hurdle model is fitted on few rows. Simple, strongly regularised severity models, such as a Gamma or log-normal GBM with shallow trees, may generalise as well as complex ones.

### Gaps
- No AUC, PR-AUC or top-k loss-capture metrics were found for any flood-loss study comparing hurdle GBM, Tweedie GBM, RF and GLM on the same data.
- No SHELDUS-based ML comparison was found.
- Exact metric tables in So (2023), So & Valdez (2024) and Salas et al. (2022) could not be read because arXiv was blocked.

## Q2. When does deep learning beat gradient boosting on tabular data of this size, and are there flood-loss studies using LSTMs or GNNs?

### Takeaway
On tabular data of about 10K to a few hundred thousand rows with heterogeneous, skewed features, tuned GBMs match or beat deep nets in the major benchmarks. Deep learning (DL) gains are dataset-specific and are often smaller than the gain from tuning the GBM. Published LSTM and GNN flood work targets hazard (inundation extent, water level, flooded tracts), not monetary loss. No GNN or LSTM county-level flood-loss model was found.

### Cited Findings
- Grinsztajn, Oyallon & Varoquaux (2022), NeurIPS Datasets & Benchmarks. Covers 45 datasets with a 20,000 compute-hour hyperparameter search. Tree models remain state of the art on medium-sized data (~10K samples). The gap is not explained by categorical features and does not close with tuning. Neural nets struggle with uninformative features and with irregular target functions, and are not invariant to rotation. — [arXiv 2207.08815](https://arxiv.org/abs/2207.08815); [NeurIPS poster](https://nips.cc/virtual/2022/poster/55627)
- Shwartz-Ziv & Armon (2022), "Tabular Data: Deep Learning is Not All You Need", *Information Fusion* (arXiv 2106.03253). XGBoost beat the deep models (TabNet, NODE, DNF-Net, 1D-CNN) on 8 of 11 datasets (p < 0.005), and its hyperparameter search was much shorter. An ensemble of deep models plus XGBoost did best. Each deep model degraded on datasets other than those in its own paper. — [arXiv 2106.03253](https://arxiv.org/abs/2106.03253v2); [ar5iv](https://ar5iv.labs.arxiv.org/html/2106.03253)
- McElfresh et al. (2023), "When Do Neural Nets Outperform Boosted Trees on Tabular Data?", NeurIPS 2023 (arXiv 2305.02997). Covers 19 algorithms on 176 datasets. The neural-net-vs-GBDT difference is often negligible, or smaller than the gain from light GBDT tuning. CatBoost and TabPFN were the two best overall. GBDTs are "much better" than neural nets on skewed or heavy-tailed feature distributions and other irregularities. — [arXiv 2305.02997](https://arxiv.org/html/2305.02997v4)
- Graph models for flood hazard:
  - A spatio-temporal graph model for urban flood nowcasting (Harris County, Hurricane Harvey) beat an LSTM baseline at predicting flooded census tracts, notably on precision and recall. — [arXiv 2111.08450](https://arxiv.org/pdf/2111.08450)
  - FloodGNN-GRU models inundation on about 3.2M 30-m cells in Harris County. — [Environmental Data Science (Cambridge)](https://www.cambridge.org/core/journals/environmental-data-science/article/floodgnngru-a-spatiotemporal-graph-neural-network-for-flood-prediction/93BA1DA8D6ECC93D985656C3BC1EA3DE)
  - FloodGTN (GNN plus LSTM) forecasts water levels at South Florida stations. — [arXiv 2310.07631](https://arxiv.org/pdf/2310.07631)
  - LSTM flood-susceptibility mapping. — [J. Hydrology 2021, ADS](https://ui.adsabs.harvard.edu/abs/2021JHyd..59425734F/abstract)
- Salas et al. (2022) included a conditional GAN, a neural approach, for NFIP loss, and XGBoost still performed best in high-claim counties **[snippet]**. — [arXiv 2212.08660](https://arxiv.org/abs/2212.08660)
- **[unverified, background knowledge]** TabPFN v2 (Hollmann et al., *Nature*, Jan 2025) reports strong results on small tabular datasets, up to about 10K rows. That is far below 303,840 rows, so it is not directly applicable without subsampling.

### Inferences
- The dataset has about 300K rows, but only about 9.7K positives, and features are hand-crafted, skewed and partly uninformative (census, terrain). Grinsztajn's and McElfresh's conditions favouring trees apply. An MLP is unlikely to beat a tuned GBM. If included, it is best treated as a baseline, or as an ensemble member per Shwartz-Ziv & Armon.
- An LSTM or GNN would only add value if raw sequences (daily rainfall history) or explicit spatial spillover are not already captured by engineered features, such as lagged or rolling rainfall extremes and neighbour-county aggregates. Lagged and spatially lagged features in a GBM are the cheaper first step.
- Ranking metrics like top-5% loss capture are dominated by a few extreme months. DL's extra variance on rare positives makes it riskier there.

### Gaps
- No published LSTM or GNN model predicting monetary flood loss (NFIP, SHELDUS, Storm Events) at county-month scale was found.
- TabPFN and other tabular-foundation-model results on rows of this size were not verified.

## Q3. Practical guidance for GBMs with rare positives: class weights, calibration, monotone constraints, early stopping on a time-based split, SHAP

### Takeaway
For ranking metrics (AUC, PR-AUC, top-k capture), class weighting rarely helps much, because the ordering of scores is largely unaffected. It also distorts probabilities, which matters when P(loss>0) is multiplied by severity in a hurdle model. Prefer training without weights, or weighting and then re-calibrating on a time-held-out validation set. Use monotone constraints on hazard drivers. Early-stop on a later-in-time validation block (for example 2014-2016), not a random split. Use TreeSHAP for interpretation.

### Cited Findings
- Per the LightGBM/sklearn-API documentation as quoted, `is_unbalance` and `scale_pos_weight` (binary) "will result in poor estimates of the individual class probabilities. You may want to consider performing probability calibration" **[quoted via secondary blog]**. — [CSDN quote of LightGBM docs](https://blog.csdn.net/weixin_42666153/article/details/127839770)
- `is_unbalance` sets weights to n_neg/n_pos automatically and cannot be combined with `scale_pos_weight`. Calibrate afterwards with Platt or isotonic scaling. Thresholds change when weights are used. — [AWS SageMaker LightGBM hyperparameters](https://docs.aws.amazon.com/ja_jp/sagemaker/latest/dg/lightgbm-hyperparameters.html); [Galaxy guide](https://www.getgalaxy.io/learn/glossary/tuning-lightgbm-for-imbalanced-data-a-practical-guide); [neuralbase threshold note](https://theneuralbase.com/lightgbm/learn/intermediate/threshold-optimization/)
- In XGBoost, `monotone_constraints` takes +1 (increasing), -1 (decreasing) or 0 per feature, and also accepts feature names. With `hist`/`approx` tree methods, constraints can produce overly shallow trees, and increasing `max_bin` can help. — [XGBoost Monotonic Constraints tutorial](https://xgboost.readthedocs.io/en/latest/tutorials/monotonic.html)
- Random splits can overstate performance relative to temporal splits for disaster-claims forecasting **[snippet only]**. — [Frontiers frai.2026.1802461](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1802461/full)
- The 2026 EGUsphere flash-flood XGBoost study used SHAP to interpret predictions from Storm Events and ERA5 data. — [EGUsphere](https://egusphere.copernicus.org/preprints/2026/egusphere-2026-1591/)
- **[unverified, background knowledge]**
  - LightGBM also supports `monotone_constraints`, with `monotone_constraints_method` options basic, intermediate and advanced.
  - Both libraries support early stopping on a user-supplied eval set.
  - scikit-learn's `HistGradientBoosting*` supports `monotonic_cst`, and its `TimeSeriesSplit` gives forward-chaining folds.
  - XGBoost, LightGBM and CatBoost all expose exact TreeSHAP contributions natively (`pred_contrib=True` / `pred_contribs=True` / `get_feature_importance(type='ShapValues')`).

### Inferences
- Suggested protocol for this project:
  - Training years 2000-2013, validation years 2014-2016 for early stopping, tuning and calibration, then refit on 2000-2016 with the selected number of trees, and test on 2017-2023.
  - Optionally use rolling-origin folds by year blocks.
  - Never let the same month across counties leak between folds. Spatially correlated storms make same-month rows non-independent.
- Monotone +1 constraints on rainfall-extreme, soil-moisture and snowmelt features are physically defensible. They usually cost little accuracy and improve extrapolation to unseen extreme months, which matters because single months hold 20% of losses. Avoid constraints on census and land-cover variables, whose direction is ambiguous.
- For the hurdle classifier, train unweighted or with mild weights. Report AUC and PR-AUC, which are insensitive to monotone recalibration. Apply isotonic calibration on the validation block before multiplying by severity.
- Report SHAP mean |value| rankings and dependence plots for rainfall features, and check that they agree with the monotone constraints.

### Gaps
- LightGBM's official parameter page and XGBoost's Tweedie parameter page could not be opened. No study was found quantifying class-weight effects on PR-AUC specifically for flood or disaster loss.

## Q4. Tweedie vs two-part (hurdle) for ranking expected loss: pros, cons and variance power choice

### Takeaway
A single Tweedie GBM, with variance power p in (1,2), models E[loss] directly in one model. It is simple and well suited to ranking by expected loss. A two-part model, P(loss>0) × E[loss | loss>0], has a separately optimised occurrence classifier, which often helps AUC and PR-AUC. It also gives interpretable parts, but multiplies the errors of the two parts. Evidence is mixed: actuarial work shows boosted Tweedie ≫ GLM and zero-inflated Tweedie > plain Tweedie under heavy zero inflation, while one retail study shows hurdle > Tweedie. Tune p (for example over 1.1-1.9) on the time-based validation block rather than fixing 1.5.

### Cited Findings
- The scikit-learn example "Tweedie regression on insurance claims" (French MTPL data) contrasts a direct Tweedie model of pure premium (power between 1 and 2) with a "product model" (Poisson frequency × Gamma severity). Models are scored by D², MAE, MSE and mean Tweedie deviance. The Gamma severity model needs strictly positive amounts. — [scikit-learn example](https://scikit-learn.org/stable/auto_examples/linear_model/plot_tweedie_regression_insurance_claims.html)
- **[unverified, background knowledge]** The same scikit-learn example also plots Lorenz curves and computes Gini indices to compare risk ranking, and finds the Tweedie and product models rank risks similarly.
- Plain Tweedie models "fall short in accurately representing the large incidence of zero claims", which motivates zero-inflated Tweedie boosting. That approach reports marked improvement on a telematics dataset. — [So & Valdez arXiv 2406.16206](https://arxiv.org/abs/2406.16206v1)
- EMTboost (zero-inflated Tweedie boosting) targets "extremely unbalanced" zero-inflated data, where plain Tweedie boosting underperforms. — [arXiv 1811.10192](https://arxiv.org/pdf/1811.10192)
- Hurdle LightGBM significantly beat Tweedie LightGBM with p fixed at 1.5 (R² of -0.287 for Tweedie) on retail data with 62.5% zeros **[snippet]**. — [MDPI Applied Sciences 16(13):6550](https://www.mdpi.com/2076-3417/16/13/6550)
- Hurdle models use a truncated-at-zero positive part, while zero-inflated models mix a point mass with a full distribution. — [same MDPI paper](https://doi.org/10.3390/app16136550)
- H2O's XGBoost wrapper states that the Tweedie power must be between 1 and 2, default 1.5. — [H2O docs](https://docs.h2o.ai/h2o/latest-stable/h2o-r/docs/reference/h2o.xgboost.html)
- **[unverified, background knowledge]** Native XGBoost uses `reg:tweedie` with `tweedie_variance_power` defaulting to 1.5, range (1,2). LightGBM uses `objective='tweedie'` with `tweedie_variance_power` defaulting to 1.5, range [1,2).
- **[unverified, background knowledge]** In a compound Poisson-gamma Tweedie, p near 1 behaves like Poisson (a zero-mass/frequency focus) and p near 2 behaves like Gamma (a severity focus). With very high zero shares, p is typically estimated in the 1.3-1.7 range. A heavier tail (CV of positive losses very large) pushes toward larger p.

### Inferences
**Tweedie GBM, pros**
- One model, one hyperparameter search.
- Optimises a deviance on E[loss], which aligns with the "share of loss captured in the top 5%" metric.
- No retransformation bias from log-severity models.
- Handles the 96.8% zeros natively through the compound-Poisson point mass.

**Tweedie GBM, cons**
- A single p ties the mean-variance relation for occurrence and severity together.
- Extreme months (20% of loss) can dominate gradients.
- No explicit occurrence probability for AUC reporting. The predicted mean can be used as a ranking score, which still yields an AUC, but it is not an optimised classifier.

**Two-part GBM, pros**
- The classifier is directly optimised for the AUC/PR-AUC goal.
- The severity model can use a Gamma or log-normal loss and different features or monotone constraints.
- The parts are interpretable ("where" vs "how bad").

**Two-part GBM, cons**
- The severity stage is fitted on about 9.7K rows with a very heavy tail.
- Probability calibration matters for the product.
- A log-normal severity model needs a smearing correction.
- Errors compound across the two parts.

**Recommendation:** fit both on identical temporal folds and compare on all three target metrics.
- Expected pattern, a hypothesis: the hurdle classifier wins AUC and PR-AUC, and the Tweedie GBM is equal or better on top-5% loss capture and Tweedie deviance.
- A simple average of the two expected-loss rankings is a cheap ensemble.
- Choose p by grid search on validation deviance or top-k capture. Also report Gini/Lorenz concentration curves.

### Gaps
- No flood-loss or disaster-loss study directly comparing Tweedie GBM vs hurdle GBM was found.
- No published guidance on variance-power choice specific to flood losses was found.
- The scikit-learn example's Gini/Lorenz numbers could not be verified because the page fetch was blocked.
