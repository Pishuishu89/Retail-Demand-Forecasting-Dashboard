"""
M5 Demand Forecasting Pipeline  ->  Power BI star schema
--------------------------------------------------------
Scope: one store (STORE_ID) across all 3 categories, 3,049 SKUs.
Train on d_1..d_1913, forecast the 28-day horizon d_1914..d_1941,
and score against the REAL held-out actuals contained in the
evaluation file. Two models: a seasonal-naive baseline and a global
LightGBM (tweedie) model. Exports analytics-ready CSVs for Power BI.

To scale to the whole dataset: set STORE_ID = None (runs all 10 stores).
"""

import gc
import numpy as np
import pandas as pd
import lightgbm as lgb

UPLOADS = "/mnt/user-data/uploads"
OUT     = "/mnt/user-data/outputs/powerbi_data"

STORE_ID     = "CA_1"     # set to None to run all stores
TRAIN_END    = 1913       # last training day (d_1913)
HORIZON_END  = 1941       # last forecast day (d_1914..d_1941)
HIST_WINDOW  = 365        # days of actuals to export to the dashboard fact table

# ----------------------------------------------------------------------
# 1. CALENDAR  (tiny)
# ----------------------------------------------------------------------
print("[1/7] calendar", flush=True)
cal = pd.read_csv(f"{UPLOADS}/calendar.csv")
cal["dnum"] = cal["d"].str.replace("d_", "", regex=False).astype(int)
cal["date"] = pd.to_datetime(cal["date"])
for c in ["event_name_1", "event_type_1", "event_name_2", "event_type_2"]:
    cal[c] = cal[c].fillna("none")

# ----------------------------------------------------------------------
# 2. SALES  (wide -> long), filtered to STORE_ID
# ----------------------------------------------------------------------
print("[2/7] sales (evaluation file = full history + holdout actuals)", flush=True)
id_cols  = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
day_cols = [f"d_{i}" for i in range(1, HORIZON_END + 1)]
dtypes   = {c: "int16" for c in day_cols}
for c in id_cols:
    dtypes[c] = "category"

sales = pd.read_csv(f"{UPLOADS}/sales_train_evaluation.csv",
                    usecols=id_cols + day_cols, dtype=dtypes)
if STORE_ID is not None:
    sales = sales[sales["store_id"] == STORE_ID].copy()
print(f"      series: {len(sales):,}", flush=True)

long = sales.melt(id_vars=id_cols, value_vars=day_cols,
                  var_name="d", value_name="units")
del sales; gc.collect()
long["dnum"]  = long["d"].str.replace("d_", "", regex=False).astype(np.int32)
long["units"] = long["units"].astype(np.int32)

# attach calendar
long = long.merge(
    cal[["d", "date", "wm_yr_wk", "wday", "month", "year",
         "snap_CA", "snap_TX", "snap_WI",
         "event_name_1", "event_type_1"]],
    on="d", how="left")

# state-correct SNAP flag
state = STORE_ID.split("_")[0] if STORE_ID else None
long["snap"] = long[f"snap_{state}"].astype("int8") if state else long["snap_CA"]
long.drop(columns=["snap_CA", "snap_TX", "snap_WI"], inplace=True)
print(f"      long rows: {len(long):,}", flush=True)

# ----------------------------------------------------------------------
# 3. PRICES  (filtered to STORE_ID) joined on store+item+week
# ----------------------------------------------------------------------
print("[3/7] prices", flush=True)
prices = pd.read_csv(f"{UPLOADS}/sell_prices.csv",
                     dtype={"store_id": "category", "item_id": "category",
                            "wm_yr_wk": "int32", "sell_price": "float32"})
if STORE_ID is not None:
    prices = prices[prices["store_id"] == STORE_ID].copy()

long["item_id"]  = long["item_id"].astype(str)
long["store_id"] = long["store_id"].astype(str)
prices["item_id"]  = prices["item_id"].astype(str)
prices["store_id"] = prices["store_id"].astype(str)

long = long.merge(prices[["store_id", "item_id", "wm_yr_wk", "sell_price"]],
                  on=["store_id", "item_id", "wm_yr_wk"], how="left")
del prices; gc.collect()

# shrink: IDs back to category (huge over 5.9M rows), drop raw 'd'
long["item_id"]  = long["item_id"].astype("category")
long["store_id"] = long["store_id"].astype("category")
long.drop(columns=["d"], inplace=True, errors="ignore")
gc.collect()

# ----------------------------------------------------------------------
# 4. FEATURES  (all lags >= 28 so the 28-day horizon predicts in one shot,
#    no recursion and no leakage from the forecast period)
# ----------------------------------------------------------------------
print("[4/7] features", flush=True)
long.sort_values(["item_id", "dnum"], inplace=True)
g = long.groupby("item_id", observed=True)["units"]

# lags (all >= 28 so the 28-day horizon predicts in one shot; 364 = last year)
for lag in (28, 35, 42, 364):
    long[f"lag_{lag}"] = g.shift(lag).astype("float32")

long["u_lag28"] = g.shift(28)
gl = long.groupby("item_id", observed=True)["u_lag28"]
long["rmean_7"]  = gl.transform(lambda s: s.rolling(7,  min_periods=1).mean()).astype("float32")
long["rmean_28"] = gl.transform(lambda s: s.rolling(28, min_periods=1).mean()).astype("float32")
long["rmean_56"] = gl.transform(lambda s: s.rolling(56, min_periods=1).mean()).astype("float32")
long["rstd_28"]  = gl.transform(lambda s: s.rolling(28, min_periods=1).std()).astype("float32")
long.drop(columns=["u_lag28"], inplace=True)

# release day = first day the item was ever sold in this store; drop pre-release
first_sale = long.loc[long["units"] > 0].groupby("item_id", observed=True)["dnum"].min()
long["release"] = long["item_id"].map(first_sale)
long["days_since_release"] = (long["dnum"] - long["release"]).astype("float32")
long = long[long["dnum"] >= long["release"]].copy()   # remove leading zeros

# price context + momentum
item_price_mean = long.groupby("item_id", observed=True)["sell_price"].transform("mean")
long["price_norm"] = (long["sell_price"] / item_price_mean).astype("float32")
roll_price = long.groupby("item_id", observed=True)["sell_price"].transform(
    lambda s: s.shift(1).rolling(4, min_periods=1).mean())
long["price_momentum"] = (long["sell_price"] / roll_price).astype("float32")

# calendar encodings
long["event_name_1"] = long["event_name_1"].astype("category")
long["event_type_1"] = long["event_type_1"].astype("category")
long["dept_id"]      = long["dept_id"].astype("category")
long["cat_id"]       = long["cat_id"].astype("category")
long["has_event"]    = (long["event_name_1"] != "none").astype("int8")

FEATURES = ["wday", "month", "snap", "has_event", "days_since_release",
            "sell_price", "price_norm", "price_momentum",
            "lag_28", "lag_35", "lag_42", "lag_364",
            "rmean_7", "rmean_28", "rmean_56", "rstd_28",
            "dept_id", "cat_id", "event_name_1", "event_type_1"]
CATS = ["dept_id", "cat_id", "event_name_1", "event_type_1"]
gc.collect()

# ----------------------------------------------------------------------
# 5. TRAIN / FORECAST
# ----------------------------------------------------------------------
print("[5/7] train LightGBM (tweedie)", flush=True)
# forecast rows (small)
fut = long[(long["dnum"] > TRAIN_END) & (long["dnum"] <= HORIZON_END)].copy()

# baseline profile inputs (small) captured before we free `long`
tail = long[(long["dnum"] >= TRAIN_END - 27) & (long["dnum"] <= TRAIN_END)][
    ["item_id", "wday", "units"]].copy()

# ---- exports that need the full frame, captured before freeing it ----
dim_item  = long[["item_id", "dept_id", "cat_id"]].drop_duplicates().sort_values("item_id")
dim_store = long[["store_id", "state_id"]].drop_duplicates()
fact = long[long["dnum"] > HORIZON_END - HIST_WINDOW][
    ["date", "item_id", "store_id", "units", "sell_price"]].copy()

# ---- training arrays, then release the big frame ----
mask = (long["dnum"] >= 29) & (long["dnum"] <= TRAIN_END)
Xtr = long.loc[mask, FEATURES].copy()
ytr = long.loc[mask, "units"].copy()
del long; gc.collect()

dtrain = lgb.Dataset(Xtr, label=ytr, categorical_feature=CATS, free_raw_data=True)
params = dict(objective="tweedie", tweedie_variance_power=1.1,
             metric="rmse", learning_rate=0.05, num_leaves=63,
             min_data_in_leaf=100, feature_fraction=0.8,
             bagging_fraction=0.8, bagging_freq=1, max_bin=128,
             num_threads=1, verbose=-1)
model = lgb.train(params, dtrain, num_boost_round=400)
del Xtr, ytr, dtrain; gc.collect()

fut["forecast_lgbm"] = np.clip(model.predict(fut[FEATURES]), 0, None)

# seasonal-naive baseline: per-item mean units by weekday over last 4 training weeks
profile = tail.groupby(["item_id", "wday"], observed=True)["units"].mean().rename("forecast_baseline")
item_mean = tail.groupby("item_id", observed=True)["units"].mean()
fut = fut.merge(profile, on=["item_id", "wday"], how="left")
fut["forecast_baseline"] = fut["forecast_baseline"].fillna(fut["item_id"].map(item_mean)).fillna(0)

# ----------------------------------------------------------------------
# 6. SCORE on the held-out 28 days (real actuals)
# ----------------------------------------------------------------------
print("[6/7] score", flush=True)
def wmape(a, f):  return np.abs(a - f).sum() / max(a.sum(), 1e-9)
def bias(a, f):   return (f - a).sum()  / max(a.sum(), 1e-9)

MODELS = [("Seasonal-naive baseline", "forecast_baseline"),
          ("LightGBM (tweedie)",      "forecast_lgbm")]

# --- item-day grain (hardest: intermittent SKUs) ---
rows = []
for name, col in MODELS:
    rows.append({"grain": "item-day", "model": name, "scope": "TOTAL",
                 "wmape": round(wmape(fut["units"], fut[col]), 4),
                 "bias":  round(bias(fut["units"],  fut[col]), 4)})
    for c, sub in fut.groupby("cat_id", observed=True):
        rows.append({"grain": "item-day", "model": name, "scope": c,
                     "wmape": round(wmape(sub["units"], sub[col]), 4),
                     "bias":  round(bias(sub["units"],  sub[col]), 4)})

# --- aggregate planning grains (errors net out, as planners see them) ---
for grain, keys in [("category-day", ["date", "cat_id"]), ("total-day", ["date"])]:
    agg = fut.groupby(keys, observed=True).agg(
        actual=("units", "sum"),
        forecast_baseline=("forecast_baseline", "sum"),
        forecast_lgbm=("forecast_lgbm", "sum")).reset_index()
    for name, col in MODELS:
        rows.append({"grain": grain, "model": name, "scope": "TOTAL",
                     "wmape": round(wmape(agg["actual"], agg[col]), 4),
                     "bias":  round(bias(agg["actual"],  agg[col]), 4)})

score = pd.DataFrame(rows)[["grain", "model", "scope", "wmape", "bias"]]
print(score.to_string(index=False), flush=True)

lgbm_tot = score[(score.grain=="item-day") & (score.scope=="TOTAL") &
                 (score.model=="LightGBM (tweedie)")]["wmape"].iloc[0]
base_tot = score[(score.grain=="item-day") & (score.scope=="TOTAL") &
                 (score.model=="Seasonal-naive baseline")]["wmape"].iloc[0]
print(f"\nItem-day WMAPE: baseline {base_tot:.1%} -> LightGBM {lgbm_tot:.1%} "
      f"({(base_tot-lgbm_tot)/base_tot:.1%} relative improvement)", flush=True)
agg_lgbm = score[(score.grain=="total-day") & (score.model=="LightGBM (tweedie)")]["wmape"].iloc[0]
print(f"Total-day (aggregate) WMAPE, LightGBM: {agg_lgbm:.1%}", flush=True)

# ----------------------------------------------------------------------
# 7. EXPORT star schema for Power BI
# ----------------------------------------------------------------------
print("[7/7] export", flush=True)

# dim_calendar (full range incl. forecast dates)
dim_cal = cal[cal["dnum"] <= HORIZON_END][
    ["date", "dnum", "wday", "weekday", "month", "year",
     "event_name_1", "event_type_1"]].copy()
dim_cal["is_weekend"] = dim_cal["wday"].isin([1, 2]).astype(int)  # M5: 1=Sat,2=Sun
dim_cal["is_forecast_period"] = (dim_cal["dnum"] > TRAIN_END).astype(int)
dim_cal.rename(columns={"event_name_1": "event_name",
                        "event_type_1": "event_type"}, inplace=True)
dim_cal.to_csv(f"{OUT}/dim_calendar.csv", index=False)

# dim_item / dim_store  (captured before the frame was freed)
dim_item.to_csv(f"{OUT}/dim_item.csv", index=False)
dim_store.to_csv(f"{OUT}/dim_store.csv", index=False)

# fact_sales (recent HIST_WINDOW days of actuals)
fact["revenue"] = (fact["units"] * fact["sell_price"]).astype("float32")
fact.to_csv(f"{OUT}/fact_sales.csv", index=False)

# fact_forecast (28-day horizon: actual vs both models)
ff = fut[["date", "item_id", "store_id", "cat_id", "units",
          "forecast_baseline", "forecast_lgbm"]].copy()
ff.rename(columns={"units": "actual"}, inplace=True)
ff["forecast_baseline"] = ff["forecast_baseline"].round(2)
ff["forecast_lgbm"]     = ff["forecast_lgbm"].round(2)
ff["abs_err_baseline"]  = (ff["actual"] - ff["forecast_baseline"]).abs().round(2)
ff["abs_err_lgbm"]      = (ff["actual"] - ff["forecast_lgbm"]).abs().round(2)
ff.to_csv(f"{OUT}/fact_forecast.csv", index=False)

# scorecard + feature importance
score.to_csv(f"{OUT}/model_scorecard.csv", index=False)
imp = pd.DataFrame({"feature": model.feature_name(),
                    "importance": model.feature_importance(importance_type="gain")}
                   ).sort_values("importance", ascending=False)
imp.to_csv(f"{OUT}/feature_importance.csv", index=False)

import os
print("\nFiles written:")
for f in sorted(os.listdir(OUT)):
    mb = os.path.getsize(f"{OUT}/{f}") / 1e6
    print(f"  {f:28s} {mb:7.1f} MB")
print("\nDONE")
