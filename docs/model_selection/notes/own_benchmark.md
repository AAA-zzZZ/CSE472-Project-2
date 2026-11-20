# Own benchmark on the project's data (model_comparison.py, run 2026-11-01)

Same split and scores as hurdle_model.py: train 2000-2016 (215,220 county-months, 3.54% damage), test 2017-2023 once (88,620; 2,234 damage months, 2.52%). Tree models use all 39 inputs + state + calendar month; trees chosen by early stopping on 2000-2012 -> 2013-2016, then refit on 2000-2016. GLM = hurdle_model.py's full ridge logistic + linear model (17 inputs, month and state dummies). Top 5% = share of each month's loss in the model's top 5% of counties (53 of 1,055). This is first-hand evidence, not literature.

```
TEST 2017-2023 (88,620 county-months, 2,234 with damage)
                                        ROC-AUC  PR-AUC  Brier skill  mean P / rate  AUC within month  top 5%: share of loss  ... without largest month  ... median month  rank corr, year  MAE, damaged
baseline: county x month rate             0.728   0.066        0.000          1.403             0.709                  0.211                      0.266             0.023            0.113         0.905
GLM hurdle (hurdle_model.py)              0.859   0.193        0.114          1.372             0.824                  0.736                      0.742             0.408            0.259         0.862
random forest hurdle                      0.879   0.216        0.141          1.411             0.837                  0.608                      0.756             0.409            0.252         0.829
LightGBM hurdle                           0.886   0.252        0.150          1.276             0.848                  0.580                      0.723             0.366            0.303         0.816
LightGBM Tweedie (one part)               0.864   0.180          NaN            NaN             0.828                  0.450                      0.549             0.299            0.280           NaN
LightGBM hurdle, known in advance only    0.769   0.093        0.049          1.431             0.722                  0.315                      0.397             0.077            0.172         0.883

ROC-AUC differences, 95% interval from 200 county bootstrap samples:
  LGB        vs GLM       +0.0263  (+0.0213 to +0.0309)
  RF         vs GLM       +0.0196  (+0.0143 to +0.0241)
  Tweedie    vs GLM       +0.0046  (-0.0007 to +0.0098)
  LGB        vs Tweedie   +0.0218  (+0.0164 to +0.0266)
  LGB_prior  vs baseline  +0.0409  (+0.0327 to +0.0478)

LightGBM part 1, share of total gain by input (top 15):
p_month              0.316
rx5_rl_ratio         0.071
state_code           0.052
month                0.044
rain_x_wetsoil       0.034
snowmelt_mm          0.032
rx5                  0.027
elev_mean            0.025
spi2_prev            0.024
rx1                  0.021
snowmelt_prev_mm     0.020
swe_mm               0.020
log_housing_units    0.017
spi1_prev            0.016
rx3                  0.016
```

Notes: LightGBM hurdle trees chosen: part 1 = 465, part 2 = 184. Tweedie (variance power 1.5, not tuned) stopped at 120 trees. Random forest: 300 trees, min leaf 50 (classifier) / 10 (regressor), no tuning. The GLM's top-5% figure on all months is high because it caught March 2019 (21% of test loss) well; without the largest month RF 0.756 > GLM 0.742 > LGB 0.723; median month GLM 0.408 / RF 0.409 > LGB 0.366. No calibration applied: mean P / rate 1.28-1.43 for all models because the test-period damage rate fell (3.5% -> 2.5%).
