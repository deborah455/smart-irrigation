import requests, pandas as pd

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS = "T2M_MIN,T2M_MAX,RH2M,WS2M,ALLSKY_SFC_SW_DWN,PRECTOTCORR"

# Kenya regions (lat, lon, region_code)
SEEDS = [
    (-1.8, 37.6, "asal"),      # Makueni-like
    (-4.0, 39.7, "coastal"),   # Mombasa-like
    (-0.4, 36.9, "highlands"), # Nyeri-like
    (0.3, 34.8, "western"),    # Kakamega-like
    (0.1, 35.3, "rift")        # Rift Valley
]

def fetch_power(lat, lon, start, end):
    url = (f"{POWER_URL}?parameters={PARAMS}&community=AG"
           f"&latitude={lat}&longitude={lon}&start={start}&end={end}&format=JSON")
    r = requests.get(url, timeout=45)
    r.raise_for_status()
    p = r.json()["properties"]["parameter"]
    df = pd.DataFrame({
        "date": list(p["T2M_MIN"].keys()),
        "t_min": list(p["T2M_MIN"].values()),
        "t_max": list(p["T2M_MAX"].values()),
        "rh": list(p["RH2M"].values()),
        "wind_ms": list(p["WS2M"].values()),
        "solar_mj": list(p["ALLSKY_SFC_SW_DWN"].values()),
        "rain_mm": list(p["PRECTOTCORR"].values())
    })
    df["date"] = pd.to_datetime(df["date"])
    df["t_mean"] = (df["t_min"] + df["t_max"]) / 2.0
    df["diurnal_range"] = (df["t_max"] - df["t_min"]).clip(lower=0)
    df["vpd_proxy"] = (df["t_mean"].clip(lower=0) * (100 - df["rh"]).clip(lower=0)) / 100.0
    return df

if __name__ == "__main__":
    # 18 months; 5 regions -> comfortably > 3k rows
    start, end = "20240101", "20250630"
    frames = []
    for lat, lon, region in SEEDS:
        w = fetch_power(lat, lon, start, end)
        w["lat"], w["lon"], w["region"] = lat, lon, region
        frames.append(w)
    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["date","lat","lon"])
    df = df.sort_values(["region","date"]).reset_index(drop=True)
    print("Rows:", len(df))
    df.to_csv("dataset1_weather.csv", index=False)
    print("Saved dataset1_weather.csv")
