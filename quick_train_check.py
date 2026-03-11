import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, f1_score
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression

df = pd.read_csv("dataset2_training.csv")

feature_cols = [
    "soil_moisture_top","soil_moisture_deep","air_temp","air_humidity",
    "wind_ms","solar_mj","rain_mm","leaf_wetness","flow_lpm","soil_ec",
    "t_mean","diurnal_range","vpd_proxy","deficit_proxy",
    "rolling_rain_3d","rolling_evap_proxy_3d","days_since_last_irrig"
]

X = df[feature_cols]
y = df["irrigate"].astype(int)

Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

pipe = Pipeline([
    ("imp", SimpleImputer(strategy="median")),
    ("lr", LogisticRegression(max_iter=600))
])

pipe.fit(Xtr, ytr)
proba = pipe.predict_proba(Xte)[:,1]
pred = (proba >= 0.5).astype(int)

print("Class balance train/test:", round(ytr.mean(),3), round(yte.mean(),3))
print("AUROC:", round(roc_auc_score(yte, proba), 3))
print("F1:", round(f1_score(yte, pred), 3))
