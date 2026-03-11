from typing import Dict, Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import joblib
import numpy as np
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Smart Irrigation API", version="1.0")

# --- CORS (dev-friendly; tighten later) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        "*"  # DEV ONLY – replace with exact origins for production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
try:
    clf = joblib.load("irrigate_clf.joblib")
except Exception as e:
    clf = None
    print(f"[WARN] Could not load irrigate_clf.joblib: {e}")

try:
    reg = joblib.load("amount_reg.joblib")
except Exception as e:
    reg = None
    print(f"[WARN] Could not load amount_reg.joblib: {e}")

# --- Schemas ---
class FactorsIn(BaseModel):
    crop: str = Field(..., description="Crop name, e.g., 'maize'")
    region: str = Field(..., description="Region key: asal | coastal | highlands | western | rift")
    use_manual: bool = False
    lat: Optional[float] = None
    lon: Optional[float] = None
    factors: Dict[str, float] = Field(default_factory=dict)

class RecommendationOut(BaseModel):
    decision: str
    amount_mm: float
    amount_l: float

# --- Feature encoder (keep consistent with your training order) ---
def transform_to_features(crop: str, region: str, fx: Dict[str, float]) -> List[float]:
    def num(k, d=0.0):
        try:
            v = fx.get(k, d)
            return float(v) if v is not None else float(d)
        except Exception:
            return float(d)

    region_map = {"asal": 0, "coastal": 1, "highlands": 2, "western": 3, "rift": 4}
    crop_bias = (hash(crop) % 11) / 10.0  # light, stable signal

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

# --- Routes ---
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

    # Safety clamps
    if not np.isfinite(mm):
        mm = 0.0
    mm = max(0.0, mm)  # no negative irrigation

    area = 0.0
    try:
        area = float(p.factors.get("area_m2", 0.0) or 0.0)
    except Exception:
        area = 0.0

    liters = float(mm * area) if np.isfinite(mm * area) else 0.0

    # If tiny amounts, standardize to SKIP for user clarity
    if mm <= 0.5 or liters <= 1:
        decision = "SKIP"

    return RecommendationOut(decision=decision, amount_mm=mm, amount_l=liters)
