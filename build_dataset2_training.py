import pandas as pd, numpy as np
from datetime import datetime
rng = np.random.default_rng(123)

# 25+ crops
CROPS = [
    "maize","beans","cowpea","sorghum","millet","wheat","barley","rice","potato",
    "sweet_potato","cassava","tomato","onion","cabbage","kale","spinach","capsicum",
    "banana","coffee","tea","sugarcane","pineapple","mango","avocado","sunflower",
    "groundnut","cotton","watermelon"
]

REGION_TOGGLES = {
    "asal":     dict(use_humidity=0, use_wind=0, use_leaf_wetness=0),
    "coastal":  dict(use_humidity=1, use_wind=0, use_leaf_wetness=1),
    "highlands":dict(use_humidity=1, use_wind=0, use_leaf_wetness=0),
    "western":  dict(use_humidity=1, use_wind=0, use_leaf_wetness=0),
    "rift":     dict(use_humidity=1, use_wind=1, use_leaf_wetness=0)
}

def sample_plots(df_weather, plots_per_region=90):
    rows, pid = [], 1000
    for region in df_weather["region"].unique():
        wreg = df_weather[df_weather["region"]==region]
        dates = wreg["date"].sort_values().unique()
        lat = wreg["lat"].iloc[0]; lon = wreg["lon"].iloc[0]
        for _ in range(plots_per_region):
            crop = rng.choice(CROPS)
            start_idx = rng.integers(low=0, high=max(1, len(dates)-120))
            plant_date = pd.to_datetime(dates[start_idx]).date()
            area = float(rng.choice([200,300,400,500,600,800,1000]))
            rows.append(dict(plot_id=pid, region=region, crop=crop, planting_date=plant_date,
                             area_m2=area, lat=lat, lon=lon))
            pid += 1
    return pd.DataFrame(rows)

def derive_features(w, soil_top, soil_deep, days_since_irrig, toggles):
    t_min, t_max, rh = w["t_min"], w["t_max"], w["rh"]
    wind, solar, rain = w["wind_ms"], w["solar_mj"], w["rain_mm"]
    t_mean = (t_min + t_max)/2.0
    diurnal = max(0.0, t_max - t_min)
    vpd_proxy = (t_mean * (100 - rh))/100.0
    evap_proxy = (diurnal * (100 - rh)/100.0) + max(0.0, wind*0.2) + max(0.0, solar/10.0)
    rolling_rain_3d = rng.normal(loc=rain, scale=2.0)
    rolling_evap_3d = rng.normal(loc=evap_proxy, scale=0.5)
    leaf_wetness = rng.binomial(1, p=min(0.8, (rh/100.0)*0.6 + (rain>2)*0.3))
    flow_lpm_yday = max(0.0, rng.normal(0.5 if days_since_irrig==1 else 0.1, 0.2))
    soil_ec = np.clip(rng.normal(0.6, 0.15), 0.1, 1.5)

    if not toggles["use_humidity"]:
        rh = None
    if not toggles["use_wind"]:
        wind = None
    if not toggles["use_leaf_wetness"]:
        leaf_wetness = None

    def maybe_nan(x):  # ~6% missingness
        return (np.nan if rng.random() < 0.06 else x)

    return dict(
        soil_moisture_top=maybe_nan(soil_top),
        soil_moisture_deep=maybe_nan(soil_deep),
        air_temp=maybe_nan(t_mean),
        air_humidity=maybe_nan(rh),
        wind_ms=maybe_nan(wind),
        solar_mj=maybe_nan(solar),
        rain_mm=maybe_nan(rain),
        leaf_wetness=maybe_nan(leaf_wetness),
        flow_lpm=maybe_nan(flow_lpm_yday),
        soil_ec=maybe_nan(soil_ec),
        t_mean=maybe_nan(t_mean),
        diurnal_range=maybe_nan(diurnal),
        vpd_proxy=maybe_nan(vpd_proxy),
        deficit_proxy=maybe_nan(evap_proxy - (rain or 0.0)),
        rolling_rain_3d=maybe_nan(rolling_rain_3d),
        rolling_evap_proxy_3d=maybe_nan(rolling_evap_3d),
        days_since_last_irrig=days_since_irrig
    )

def label_rule(feat):
    sm_vals = [feat["soil_moisture_top"], feat["soil_moisture_deep"]]
    sm = np.nanmean([v for v in sm_vals if v is not None])
    if np.isnan(sm): sm = 0.22
    deficit = 0.0 if pd.isna(feat["deficit_proxy"]) else feat["deficit_proxy"]
    rain = 0.0 if pd.isna(feat["rain_mm"]) else feat["rain_mm"]
    score = (0.6 * (0.22 - sm)) + (0.03 * deficit) - (0.04 * rain) + 0.02 * feat["days_since_last_irrig"]
    p = 1/(1 + np.exp(-5*score))
    p = np.clip(p + np.random.normal(0, 0.05), 0, 1)  # noise to avoid perfect AUROC
    need = 1 if np.random.random() < p else 0
    base = 4 + 0.5*(0 if pd.isna(feat["diurnal_range"]) else feat["diurnal_range"]) \
             + 0.02*(0 if pd.isna(feat["rolling_evap_proxy_3d"]) else feat["rolling_evap_proxy_3d"]) \
             - 0.6*(rain)
    amount = float(np.clip(base + np.random.normal(0,1.2), 0, 12))
    return need, (amount if need==1 else 0.0)

if __name__ == "__main__":
    weather = pd.read_csv("dataset1_weather.csv", parse_dates=["date"])
    plots = sample_plots(weather, plots_per_region=90)  # ~450 plots total
    rows = []

    for _, p in plots.iterrows():
        wreg = weather[(weather["region"]==p["region"]) & (weather["lat"]==p["lat"]) & (weather["lon"]==p["lon"])]
        wreg = wreg[wreg["date"]>=pd.to_datetime(p["planting_date"])].head(90)  # ~90 days per plot
        if len(wreg)==0: 
            continue

        days_since_irrig = rng.integers(0, 5)
        soil_top = rng.normal(0.20, 0.05)
        soil_deep = rng.normal(0.25, 0.05)
        toggles = REGION_TOGGLES[p["region"]]

        for _, wr in wreg.iterrows():
            evap_eff = (max(0, wr["diurnal_range"])*0.002 + max(0, (100-wr["rh"])/100)*0.003)
            rain_eff = (wr["rain_mm"] or 0.0) * 0.004
            soil_top = np.clip(soil_top - evap_eff + rain_eff + np.random.normal(0,0.004), 0.04, 0.45)
            soil_deep = np.clip(soil_deep - evap_eff*0.6 + rain_eff*0.6 + np.random.normal(0,0.003), 0.06, 0.50)

            feat = derive_features(wr, soil_top, soil_deep, days_since_irrig, toggles)
            need, amount = label_rule(feat)

            if need == 1:
                soil_top = np.clip(soil_top + amount*0.006, 0.04, 0.45)
                soil_deep = np.clip(soil_deep + amount*0.004, 0.06, 0.50)
                days_since_irrig = 0
            else:
                days_since_irrig += 1

            rows.append({
                "date": wr["date"].date(), "plot_id": p["plot_id"], "region": p["region"], "crop": p["crop"],
                "lat": p["lat"], "lon": p["lon"], "area_m2": p["area_m2"], "planting_date": p["planting_date"],
                **feat,
                "irrigate": need, "amount_mm": amount
            })

    df = pd.DataFrame(rows)

    # ~8% label noise to keep AUROC realistic
    flip = np.random.default_rng(7).random(len(df)) < 0.08
    df.loc[flip, "irrigate"] = 1 - df.loc[flip, "irrigate"]

    print("Rows built:", len(df))
    df = df.sample(frac=1.0, random_state=7).reset_index(drop=True)
    df.to_csv("dataset2_training.csv", index=False)
    print("Saved dataset2_training.csv")
