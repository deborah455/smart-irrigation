from typing import Dict, Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import joblib
import numpy as np
import os, json, sqlite3, time

# ---------------- FastAPI app ----------------
app = FastAPI(title="Smart Irrigation API", version="1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "*"  # DEV ONLY; tighten in production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Models ----------------
clf = None
reg = None
try:
    clf = joblib.load("irrigate_clf.joblib")
except Exception as e:
    print(f"[WARN] Could not load irrigate_clf.joblib: {e}")

try:
    reg = joblib.load("amount_reg.joblib")
except Exception as e:
    print(f"[WARN] Could not load amount_reg.joblib: {e}")

# ---------------- Request/Response ----------------
class FactorsIn(BaseModel):
    crop: str
    region: str  # asal | coastal | highlands | western | rift
    use_manual: bool = False
    lat: Optional[float] = None
    lon: Optional[float] = None
    factors: Dict[str, float] = Field(default_factory=dict)

class RecommendationOut(BaseModel):
    decision: str
    amount_mm: float
    amount_l: float

# ---------------- Feature transform ----------------
def transform_to_features(crop: str, region: str, fx: Dict[str, float]) -> List[float]:
    def num(k, d=0.0):
        try:
            v = fx.get(k, d)
            return float(v) if v is not None else float(d)
        except Exception:
            return float(d)

    region_map = {"asal": 0, "coastal": 1, "highlands": 2, "western": 3, "rift": 4}
    crop_bias = (hash(crop) % 11) / 10.0  # small stable signal

    feats = [
        num("soil_moisture_top", 0.20),
        num("soil_moisture_deep", 0.25),
        num("et0_mm", 4.0),
        num("rain_mm", 0.0),
        num("air_temp_c", 26.0),
        num("rel_humidity", 60.0),
        num("wind_ms", 2.0),
        num("area_m2", 400.0),
        float(region_map.get(region, 0)),
        float(crop_bias),
    ]
    return feats

# ---------------- SQLite helpers (auto-creates schema) ----------------
DB_PATH = os.path.join("db", "smart_irrigation.db")
SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS farmer (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  phone_hash CHAR(64) NOT NULL UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS plot (
  id INTEGER PRIMARY KEY,
  farmer_id INTEGER NOT NULL REFERENCES farmer(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  crop TEXT NOT NULL,
  region TEXT NOT NULL,
  lat REAL,
  lon REAL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS factors_snapshot (
  id INTEGER PRIMARY KEY,
  plot_id INTEGER NOT NULL REFERENCES plot(id) ON DELETE CASCADE,
  payload_json TEXT NOT NULL,
  device_id TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recommendation (
  id INTEGER PRIMARY KEY,
  snapshot_id INTEGER NOT NULL UNIQUE REFERENCES factors_snapshot(id) ON DELETE CASCADE,
  decision TEXT NOT NULL,
  amount_mm REAL NOT NULL,
  amount_l REAL NOT NULL,
  weather_json TEXT,
  model_version TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_version (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  path TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_plot_farmer   ON plot(farmer_id);
CREATE INDEX IF NOT EXISTS idx_snap_plot     ON factors_snapshot(plot_id, created_at);
CREATE INDEX IF NOT EXISTS idx_reco_created  ON recommendation(created_at);
"""

def init_db():
    os.makedirs("db", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()

def _con():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def _get_or_create_demo_farmer():
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

# create DB schema at import
try:
    init_db()
    print(f"[INFO] DB ready at {DB_PATH}")
except Exception as e:
    print(f"[WARN] could not init DB: {e}")

# ---------------- Routes ----------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"message": "Smart Irrigation API. POST /recommend/today"}

@app.post("/recommend/today", response_model=RecommendationOut)
def recommend_today(p: FactorsIn):
    if clf is None or reg is None:
        raise HTTPException(status_code=500, detail="Models not loaded on server")

    X = np.asarray([transform_to_features(p.crop, p.region, p.factors)], dtype=float)

    try:
        prob = float(clf.predict_proba(X)[0, 1])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"classifier error: {e}")

    decision = "IRRIGATE" if prob >= 0.50 else "SKIP"

    try:
        mm = float(reg.predict(X)[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"regressor error: {e}")

    if not np.isfinite(mm):
        mm = 0.0
    mm = max(0.0, mm)
    area = 0.0
    try:
        area = float(p.factors.get("area_m2", 0.0) or 0.0)
    except Exception:
        area = 0.0
    liters = float(mm * area) if np.isfinite(mm * area) else 0.0

    if mm <= 0.5 or liters <= 1:
        decision = "SKIP"

    # --- persist to DB (demo farmer/plot) ---
    try:
        farmer_id = _get_or_create_demo_farmer()
        plot_name = f"{p.crop}-{p.region}-{int(time.time())}"
        plot_id = _create_plot(farmer_id, plot_name, p.crop, p.region, p.lat, p.lon)
        payload = {
            "crop": p.crop, "region": p.region, "use_manual": p.use_manual,
            "lat": p.lat, "lon": p.lon, "factors": p.factors
        }
        _save_snapshot_and_reco(plot_id, payload, decision, mm, liters, weather=None, model_ver="clf_v1|reg_v1")
    except Exception as e:
        print(f"[WARN] DB save skipped: {e}")

    return RecommendationOut(decision=decision, amount_mm=mm, amount_l=liters)

# ---------------- Optional: tiny admin viewer (enable with DEV_ADMIN=1) ----------------
if os.getenv("DEV_ADMIN", "0") == "1":
    @app.get("/admin/db/tables")
    def admin_tables():
        con = _con()
        try:
            cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
            tables = []
            for (name,) in cur.fetchall():
                try:
                    cnt = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                except Exception:
                    cnt = None
                tables.append({"table": name, "rows": cnt})
            return {"db": DB_PATH, "tables": tables}
        finally:
            con.close()
