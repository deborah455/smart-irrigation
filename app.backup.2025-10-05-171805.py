from fastapi import FastAPI
from pydantic import BaseModel
from joblib import load
from datetime import date
import requests

# Load the trained model bundle (created by train_and_save.py)
BUNDLE = load("irrigate_clf.joblib")
MODEL = BUNDLE["model"]
FEATS = BUNDLE["features"]

# NASA POWER daily weather endpoint + params
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS = "T2M_MIN,T2M_MAX,RH2M,WS2M,ALLSKY_SFC_SW_DWN,PRECTOTCORR"

app = FastAPI(title="Smart Irrigation (Minimal)")

class RecommendReq(BaseModel):
    lat: float
    lon: float
    soil_moisture_top: float | None = None   # farmer’s probe reading (0..1)
    soil_moisture_deep: float | None = None  # optional second depth
    area_m2: float = 400.0                    # plot area (m^2)

def fetch_power_today(lat: float, lon: float):
    d = date.today().strftime("%Y%m%d")
    url = (f"{POWER_URL}?parameters={PARAMS}&community=AG"
           f"&latitude={lat}&longitude={lon}&start={d}&end={d}&format=JSON")
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    p = r.json()["properties"]["parameter"]
    return {
        "t_min": list(p["T2M_MIN"].values())[0],
        "t_max": list(p["T2M_MAX"].values())[0],
        "rh": list(p["RH2M"].values())[0],
        "wind_ms": list(p["WS2M"].values())[0],
        "solar_mj": list(p["ALLSKY_SFC_SW_DWN"].values())[0],
        "rain_mm": list(p["PRECTOTCORR"].values())[0]
    }

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/recommend/today")
def recommend_today(req: RecommendReq):
    # 1) fetch today’s weather
    w = fetch_power_today(req.lat, req.lon)

    # 2) derive the same engineered features used during training
    t_mean = (w["t_min"] + w["t_max"]) / 2.0
    diurnal = max(0.0, w["t_max"] - w["t_min"])
    vpd_proxy = (t_mean * (100 - w["rh"])) / 100.0
    deficit_proxy = (
        diurnal * (100 - w["rh"]) / 100.0
        + max(0.0, w["wind_ms"] * 0.2)
        + max(0.0, w["solar_mj"] / 10.0)
    )

    row = {
        "soil_moisture_top": req.soil_moisture_top,
        "soil_moisture_deep": req.soil_moisture_deep,
        "air_temp": t_mean,
        "air_humidity": w["rh"],
        "wind_ms": w["wind_ms"],
        "solar_mj": w["solar_mj"],
        "rain_mm": w["rain_mm"],
        "leaf_wetness": None,              # optional sensor; None ok (imputed)
        "flow_lpm": None,                  # optional
        "soil_ec": None,                   # optional
        "t_mean": t_mean,
        "diurnal_range": diurnal,
        "vpd_proxy": vpd_proxy,
        "deficit_proxy": deficit_proxy,
        "rolling_rain_3d": w["rain_mm"],   # crude placeholder
        "rolling_evap_proxy_3d": deficit_proxy,
        "days_since_last_irrig": 1         # make this a real input later
    }

    # 3) predict with the trained model
    X = [[row.get(c) for c in FEATS]]
    need = int(MODEL.predict(X)[0])

    # 4) rule-of-thumb amount (mm) — replace with a regressor later
    base = 4 + 0.4 * diurnal - (w["rain_mm"] or 0.0)
    amount_mm = max(0.0, min(12.0, base))

    # safety: if deep layer is already wet, skip irrigation
    if (req.soil_moisture_deep is not None) and (req.soil_moisture_deep >= 0.35):
        need = 0
        amount_mm = 0.0

    amount_l = amount_mm * req.area_m2 / 1000.0

    return {
        "need": bool(need),
        "amount_mm": round(amount_mm, 2),
        "amount_l": round(amount_l, 2),
        "explanation": {
            "features_used": FEATS,
            "weather": w,
            "engineered": {
                "t_mean": t_mean,
                "diurnal_range": diurnal,
                "vpd_proxy": vpd_proxy,
                "deficit_proxy": deficit_proxy
            }
        }
    }

# ====== DEV Admin (SQLite viewer) ======
import os, sqlite3
from fastapi import HTTPException

DB_PATH = os.path.join("db", "smart_irrigation.db")

def _q(sql, args=()):
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail=f"DB not found at {DB_PATH}. Run the DDL first.")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(sql, args)
        return [dict(r) for r in cur.fetchall()]
    finally:
        con.close()

if os.getenv("DEV_ADMIN", "0") == "1":
    @app.get("/admin/db/tables")
    def admin_tables():
        rows = _q("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
        out = []
        for r in rows:
            name = r["name"]
            try:
                cnt = _q(f"SELECT COUNT(*) AS n FROM {name}")[0]["n"]
            except Exception:
                cnt = None
            out.append({"table": name, "rows": cnt})
        return {"db": DB_PATH, "tables": out}

    @app.get("/admin/db/schema/{table}")
    def admin_schema(table: str):
        cols = _q(f"PRAGMA table_info({table})")
        if not cols:
            raise HTTPException(status_code=404, detail=f"Table '{table}' not found")
        return {"table": table, "columns": cols}

    @app.get("/admin/db/rows/{table}")
    def admin_rows(table: str, limit: int = 50, offset: int = 0):
        try:
            rows = _q(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ? OFFSET ?", (limit, offset))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"table": table, "limit": limit, "offset": offset, "rows": rows}
# ====== end DEV Admin ======

# === SQLite persistence (DEV) ===
import os, json, sqlite3, time
DB_PATH = os.path.join("db", "smart_irrigation.db")
os.makedirs("db", exist_ok=True)

def _con():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def _get_or_create_demo_farmer():
    """Use a single demo farmer so we can store rows without changing the UI payload."""
    phone_hash = "DEMO"
    con = _con()
    try:
        cur = con.cursor()
        cur.execute("SELECT id FROM farmer WHERE phone_hash=?", (phone_hash,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("INSERT INTO farmer (name, phone_hash) VALUES (?,?)", ("Demo Farmer", phone_hash))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()

def _create_plot(farmer_id: int, name: str, crop: str, region: str, lat=None, lon=None) -> int:
    con = _con()
    try:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO plot (farmer_id,name,crop,region,lat,lon) VALUES (?,?,?,?,?,?)",
            (farmer_id, name, crop, region, lat, lon)
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()

def _save_snapshot_and_reco(plot_id: int, payload: dict, decision: str, mm: float, liters: float, weather: dict=None, model_ver: str="clf_v1|reg_v1") -> int:
    con = _con()
    try:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO factors_snapshot (plot_id, payload_json, device_id) VALUES (?,?,?)",
            (plot_id, json.dumps(payload), None)
        )
        snap_id = cur.lastrowid
        cur.execute(
            """INSERT INTO recommendation (snapshot_id, decision, amount_mm, amount_l, weather_json, model_version)
               VALUES (?,?,?,?,?,?)""",
            (snap_id, decision, float(mm), float(liters), json.dumps(weather) if weather else None, model_ver)
        )
        con.commit()
        return snap_id
    finally:
        con.close()
# === end SQLite persistence (DEV) ===

# === SQLite persistence (DEV) ===
import os, json, sqlite3, time
DB_PATH = os.path.join("db", "smart_irrigation.db")
os.makedirs("db", exist_ok=True)

def _con():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def _get_or_create_demo_farmer():
    """Use a single demo farmer so we can store rows without changing the UI payload."""
    phone_hash = "DEMO"
    con = _con()
    try:
        cur = con.cursor()
        cur.execute("SELECT id FROM farmer WHERE phone_hash=?", (phone_hash,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("INSERT INTO farmer (name, phone_hash) VALUES (?,?)", ("Demo Farmer", phone_hash))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()

def _create_plot(farmer_id: int, name: str, crop: str, region: str, lat=None, lon=None) -> int:
    con = _con()
    try:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO plot (farmer_id,name,crop,region,lat,lon) VALUES (?,?,?,?,?,?)",
            (farmer_id, name, crop, region, lat, lon)
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()

def _save_snapshot_and_reco(plot_id: int, payload: dict, decision: str, mm: float, liters: float, weather: dict=None, model_ver: str="clf_v1|reg_v1") -> int:
    con = _con()
    try:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO factors_snapshot (plot_id, payload_json, device_id) VALUES (?,?,?)",
            (plot_id, json.dumps(payload), None)
        )
        snap_id = cur.lastrowid
        cur.execute(
            """INSERT INTO recommendation (snapshot_id, decision, amount_mm, amount_l, weather_json, model_version)
               VALUES (?,?,?,?,?,?)""",
            (snap_id, decision, float(mm), float(liters), json.dumps(weather) if weather else None, model_ver)
        )
        con.commit()
        return snap_id
    finally:
        con.close()
# === end SQLite persistence (DEV) ===
