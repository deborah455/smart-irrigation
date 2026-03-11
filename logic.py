#!/usr/bin/env python3
"""
Interactive Smart Irrigation CLI (resilient)
- Pick crop & region
- Enter only crop×region factors
- Weather: tries NASA POWER last 5 days -> dataset1_weather.csv -> regional defaults
- Works even if farmer doesn't know lat/lon (uses region centroid)
"""
from __future__ import annotations
import sys
from datetime import date, timedelta
from joblib import load
import requests
import pandas as pd

# ----------------------------
# Model features (must match training)
# ----------------------------
FEATS = [
    "soil_moisture_top","soil_moisture_deep","air_temp","air_humidity",
    "wind_ms","solar_mj","rain_mm","leaf_wetness","flow_lpm","soil_ec",
    "t_mean","diurnal_range","vpd_proxy","deficit_proxy",
    "rolling_rain_3d","rolling_evap_proxy_3d","days_since_last_irrig"
]

# ----------------------------
# Crops -> farmer-entered factors to prompt
# ----------------------------
CROP_FEATURES = {
  "maize":         {"core":["soil_moisture_top"], "optional":["flow_lpm","leaf_wetness","soil_ec"]},
  "beans":         {"core":["soil_moisture_top"], "optional":["leaf_wetness","flow_lpm"]},
  "cowpea":        {"core":["soil_moisture_top"], "optional":["soil_ec"]},
  "sorghum":       {"core":["soil_moisture_deep"], "optional":["soil_ec"]},
  "millet":        {"core":["soil_moisture_top"], "optional":[]},
  "wheat":         {"core":["soil_moisture_deep"], "optional":[]},
  "barley":        {"core":["soil_moisture_deep"], "optional":[]},
  "rice":          {"core":["flow_lpm"], "optional":["soil_moisture_top"]},
  "potato":        {"core":["soil_moisture_top"], "optional":["leaf_wetness","flow_lpm","soil_ec"]},
  "sweet_potato":  {"core":["soil_moisture_top"], "optional":[]},
  "cassava":       {"core":["soil_moisture_deep"], "optional":[]},
  "tomato":        {"core":["soil_moisture_top","leaf_wetness"], "optional":["flow_lpm","soil_ec"]},
  "onion":         {"core":["soil_moisture_top","leaf_wetness"], "optional":[]},
  "cabbage":       {"core":["soil_moisture_top","leaf_wetness"], "optional":[]},
  "kale":          {"core":["soil_moisture_top","leaf_wetness"], "optional":[]},
  "spinach":       {"core":["soil_moisture_top","leaf_wetness"], "optional":[]},
  "capsicum":      {"core":["soil_moisture_top","leaf_wetness"], "optional":[]},
  "banana":        {"core":["soil_moisture_deep"], "optional":["flow_lpm"]},
  "coffee":        {"core":["soil_moisture_deep"], "optional":[]},
  "tea":           {"core":["soil_moisture_top"], "optional":[]},
  "sugarcane":     {"core":["soil_moisture_deep"], "optional":[]},
  "pineapple":     {"core":["soil_moisture_top"], "optional":[]},
  "mango":         {"core":["soil_moisture_deep"], "optional":[]},
  "avocado":       {"core":["soil_moisture_deep"], "optional":[]},
  "sunflower":     {"core":["soil_moisture_deep"], "optional":[]},
  "groundnut":     {"core":["soil_moisture_top"], "optional":[]},
  "cotton":        {"core":["soil_moisture_deep"], "optional":[]},
  "watermelon":    {"core":["soil_moisture_top"], "optional":["leaf_wetness"]}
}

# ----------------------------
# Regions: toggles + centroids (no lat/lon? we’ll use these)
# ----------------------------
REGION_TOGGLES = {
  "asal":     {"use_humidity":0, "use_wind":0, "use_leaf_wetness":0},
  "coastal":  {"use_humidity":1, "use_wind":0, "use_leaf_wetness":1},
  "highlands":{"use_humidity":1, "use_wind":0, "use_leaf_wetness":0},
  "western":  {"use_humidity":1, "use_wind":0, "use_leaf_wetness":0},
  "rift":     {"use_humidity":1, "use_wind":1, "use_leaf_wetness":0}
}
REGION_CENTROIDS = {
  "asal":     (-1.8, 37.6),  # Makueni-like
  "coastal":  (-4.0, 39.7),  # Mombasa-like
  "highlands":(-0.4, 36.9),  # Nyeri-like
  "western":  (0.3, 34.8),   # Kakamega-like
  "rift":     (0.1, 35.3)    # Rift mix
}

# Regional default weather if everything fails (rough, reasonable)
REGION_WEATHER_DEFAULTS = {
  "asal":     dict(t_min=17, t_max=31, rh=45, wind_ms=2.0, solar_mj=20, rain_mm=0.2),
  "coastal":  dict(t_min=23, t_max=31, rh=80, wind_ms=3.0, solar_mj=18, rain_mm=1.5),
  "highlands":dict(t_min=12, t_max=24, rh=70, wind_ms=2.5, solar_mj=18, rain_mm=2.0),
  "western":  dict(t_min=18, t_max=28, rh=75, wind_ms=1.5, solar_mj=17, rain_mm=3.0),
  "rift":     dict(t_min=14, t_max=26, rh=65, wind_ms=2.5, solar_mj=19, rain_mm=1.0)
}

FARMER_INPUTS = {
  "soil_moisture_top": ("Top soil moisture (0..1)", 0.18, 0.0, 1.0),
  "soil_moisture_deep": ("Deep soil moisture (0..1)", 0.22, 0.0, 1.0),
  "leaf_wetness": ("Leaf wetness (0 or 1)", 0, 0, 1),
  "flow_lpm": ("Irrigation flow yesterday (L/min)", 0.1, 0.0, 10.0),
  "soil_ec": ("Soil EC / salinity proxy (dS/m)", 0.6, 0.0, 5.0),
  "days_since_last_irrig": ("Days since last irrigation (integer)", 1, 0, 30),
  "area_m2": ("Plot area (m^2)", 400.0, 10.0, 100000.0)
}

# NASA POWER
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS    = "T2M_MIN,T2M_MAX,RH2M,WS2M,ALLSKY_SFC_SW_DWN,PRECTOTCORR"

def fetch_power_recent(lat: float, lon: float, lookback_days: int = 5):
    """
    Ask for the last `lookback_days` and use the latest available.
    This avoids same-day outages (HTTP 500).
    """
    end = date.today()
    start = end - timedelta(days=lookback_days)
    url = (f"{POWER_URL}?parameters={PARAMS}&community=AG"
           f"&latitude={lat}&longitude={lon}"
           f"&start={start.strftime('%Y%m%d')}&end={end.strftime('%Y%m%d')}&format=JSON")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    p = r.json()["properties"]["parameter"]
    dates = sorted(p["T2M_MIN"].keys())
    latest = dates[-1]
    i = dates.index(latest)
    return {
        "t_min": list(p["T2M_MIN"].values())[i],
        "t_max": list(p["T2M_MAX"].values())[i],
        "rh": list(p["RH2M"].values())[i],
        "wind_ms": list(p["WS2M"].values())[i],
        "solar_mj": list(p["ALLSKY_SFC_SW_DWN"].values())[i],
        "rain_mm": list(p["PRECTOTCORR"].values())[i]
    }

def fetch_from_local(region: str):
    """Fallback to dataset1_weather.csv (most recent row for region)."""
    try:
        df = pd.read_csv("dataset1_weather.csv", parse_dates=["date"])
        df = df[df["region"]==region].sort_values("date")
        if df.empty:
            return None
        last = df.iloc[-1]
        return {
            "t_min": float(last["t_min"]),
            "t_max": float(last["t_max"]),
            "rh": float(last["rh"]),
            "wind_ms": float(last["wind_ms"]),
            "solar_mj": float(last["solar_mj"]),
            "rain_mm": float(last["rain_mm"])
        }
    except Exception:
        return None

def engineered_from_weather(w):
    t_min, t_max, rh = w.get("t_min"), w.get("t_max"), w.get("rh")
    wind, solar, rain = w.get("wind_ms"), w.get("solar_mj"), w.get("rain_mm")
    t_mean = (t_min + t_max)/2.0 if (t_min is not None and t_max is not None) else None
    diurnal = max(0.0, t_max - t_min) if (t_min is not None and t_max is not None) else None
    vpd_proxy = (t_mean * (100 - rh))/100.0 if (t_mean is not None and rh is not None) else None
    deficit_proxy = None
    if diurnal is not None and rh is not None:
        deficit_proxy = (diurnal * (100 - rh) / 100.0) \
                        + (0 if wind is None else max(0.0, wind*0.2)) \
                        + (0 if solar is None else max(0.0, solar/10.0))
    return t_mean, diurnal, vpd_proxy, deficit_proxy, wind, solar, rain, rh

def ask_choice(prompt: str, options: list[str]) -> str:
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        s = input("Enter number: ").strip()
        if s.isdigit() and 1 <= int(s) <= len(options):
            return options[int(s)-1]
        print("Invalid choice. Try again.")

def ask_float(prompt: str, default: float, vmin: float, vmax: float, allow_blank: bool=True):
    txt = f"{prompt} [default {default}]: "
    while True:
        s = input(txt).strip()
        if s == "" and allow_blank:
            return default
        try:
            val = float(s)
            if vmin <= val <= vmax:
                return val
        except Exception:
            pass
        print(f"Enter a number between {vmin} and {vmax}, or press Enter for default.")

def main():
    # Load models
    try:
        clf_bundle = load("irrigate_clf.joblib")
    except Exception:
        print("ERROR: Could not load 'irrigate_clf.joblib'. Run your training script first.")
        sys.exit(1)
    clf = clf_bundle["model"]

    try:
        reg_bundle = load("amount_reg.joblib")
        reg = reg_bundle["model"]
    except Exception:
        reg = None

    print("\n=== Smart Irrigation CLI ===")
    crop = ask_choice("Choose crop", sorted(CROP_FEATURES.keys()))
    region = ask_choice("Choose region", list(REGION_TOGGLES.keys()))
    toggles = REGION_TOGGLES[region]

    # Lat/Lon optional
    use_manual = input("\nDo you want to enter latitude/longitude? (y/N): ").strip().lower() == "y"
    if use_manual:
        lat = ask_float("Latitude", REGION_CENTROIDS[region][0], -90.0, 90.0, allow_blank=False)
        lon = ask_float("Longitude", REGION_CENTROIDS[region][1], -180.0, 180.0, allow_blank=False)
    else:
        lat, lon = REGION_CENTROIDS[region]

    # Which farmer factors to ask (based on crop × region)
    crop_core = list(CROP_FEATURES[crop]["core"])
    crop_opt  = list(CROP_FEATURES[crop]["optional"])
    if toggles["use_leaf_wetness"] == 0:
        if "leaf_wetness" in crop_core: crop_core.remove("leaf_wetness")
        if "leaf_wetness" in crop_opt:  crop_opt.remove("leaf_wetness")

    to_ask = []
    for key in crop_core + crop_opt + ["days_since_last_irrig", "area_m2"]:
        if key in FARMER_INPUTS and key not in to_ask:
            to_ask.append(key)

    print("\nWe'll collect these factors for your crop & region:")
    for k in to_ask: print(f" - {k}")

    answers = {}
    for k in to_ask:
        label, default, vmin, vmax = FARMER_INPUTS[k]
        answers[k] = ask_float(label, default, vmin, vmax, allow_blank=True)

    # Weather: try POWER -> local CSV -> regional defaults
    try:
        w = fetch_power_recent(lat, lon, lookback_days=5)
    except Exception as e:
        print("\n[WARN] NASA POWER failed. Trying local dataset1_weather.csv ...")
        w = fetch_from_local(region)
        if w is None:
            print("[WARN] Local dataset not available. Using regional defaults.")
            w = REGION_WEATHER_DEFAULTS[region]

    # Region toggles
    if toggles["use_humidity"] == 0: w["rh"] = None
    if toggles["use_wind"] == 0: w["wind_ms"] = None

    # Engineered features
    t_mean, diurnal, vpd_proxy, deficit_proxy, wind, solar, rain, rh = engineered_from_weather(w)

    row = {
        "soil_moisture_top": answers.get("soil_moisture_top"),
        "soil_moisture_deep": answers.get("soil_moisture_deep"),
        "air_temp": t_mean,
        "air_humidity": rh,
        "wind_ms": wind,
        "solar_mj": solar,
        "rain_mm": rain,
        "leaf_wetness": answers.get("leaf_wetness"),
        "flow_lpm": answers.get("flow_lpm"),
        "soil_ec": answers.get("soil_ec"),
        "t_mean": t_mean,
        "diurnal_range": diurnal,
        "vpd_proxy": vpd_proxy,
        "deficit_proxy": deficit_proxy,
        "rolling_rain_3d": rain,
        "rolling_evap_proxy_3d": deficit_proxy,
        "days_since_last_irrig": answers.get("days_since_last_irrig", 1),
    }

    X = [[row.get(c) for c in FEATS]]
    need = int(clf.predict(X)[0])

    # Amount: regressor if available + need=1; else rule
    if need == 1:
        if reg is not None:
            amount_mm = float(reg.predict(X)[0])
        else:
            base = (0 if diurnal is None else (4 + 0.4*diurnal)) - (rain or 0.0 if rain is not None else 0.0)
            amount_mm = base
        amount_mm = max(0.0, min(12.0, amount_mm))
    else:
        amount_mm = 0.0

    # Deep moist override
    sm_deep = answers.get("soil_moisture_deep")
    if sm_deep is not None and sm_deep >= 0.35:
        need = 0
        amount_mm = 0.0

    area_m2 = answers.get("area_m2", 400.0)
    amount_l = amount_mm * area_m2 / 1000.0

    # Output
    print("\n================= RESULT =================")
    print(f"Crop: {crop}   Region: {region}   Area: {area_m2:.1f} m^2")
    print(f"Location used: ({lat:.4f}, {lon:.4f})  (manual={use_manual})")
    if all(v is not None for v in [w.get('t_min'), w.get('t_max'), rh, wind, solar, rain]):
        print(f"Weather: Tmin={w['t_min']:.1f}°C  Tmax={w['t_max']:.1f}°C  RH={rh:.0f}%  Wind={wind:.2f} m/s  Solar={solar:.1f} MJ  Rain={rain:.1f} mm")
    else:
        print("Weather: some values missing/ignored by region toggles or fallbacks (model imputes).")
    print("Entered factors:")
    for k in to_ask:
        print(f"  - {k}: {answers.get(k)}")
    print("------------------------------------------")
    print(f"Decision: {'IRRIGATE' if need==1 else 'SKIP'}")
    print(f"Amount: {amount_mm:.2f} mm (~{amount_l:.1f} liters)")
    print("==========================================\n")

if __name__ == "__main__":
    main()
