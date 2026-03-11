import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from joblib import dump

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
    ("clf", LogisticRegression(max_iter=800))
])

pipe.fit(Xtr, ytr)
proba = pipe.predict_proba(Xte)[:,1]
pred = (proba >= 0.5).astype(int)

print("AUROC:", round(roc_auc_score(yte, proba), 3))
print(classification_report(yte, pred, digits=3))

dump({"model": pipe, "features": feature_cols}, "irrigate_clf.joblib")
print("saved irrigate_clf.joblib")
