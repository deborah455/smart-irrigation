import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    confusion_matrix, classification_report, roc_auc_score,
    roc_curve, precision_recall_curve, average_precision_score, mean_absolute_error
)
from joblib import dump

# ---- load dataset
df = pd.read_csv("dataset2_training.csv")

# ---- features (15+)
FEATURES = [
    "soil_moisture_top","soil_moisture_deep","air_temp","air_humidity",
    "wind_ms","solar_mj","rain_mm","leaf_wetness","flow_lpm","soil_ec",
    "t_mean","diurnal_range","vpd_proxy","deficit_proxy",
    "rolling_rain_3d","rolling_evap_proxy_3d","days_since_last_irrig"
]

X = df[FEATURES]
y = df["irrigate"].astype(int)

Xtr, Xte, ytr, yte = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

# ---- classifier pipeline
clf = Pipeline([
    ("imp", SimpleImputer(strategy="median")),
    ("lr", LogisticRegression(max_iter=800))
])
clf.fit(Xtr, ytr)

# ---- metrics
proba = clf.predict_proba(Xte)[:, 1]
pred = (proba >= 0.5).astype(int)

cm = confusion_matrix(yte, pred)
auc = roc_auc_score(yte, proba)
print("\n=== Confusion Matrix ===")
print(pd.DataFrame(cm, index=["True 0","True 1"], columns=["Pred 0","Pred 1"]))
print("\nAUROC:", round(auc, 3))
print("\n=== Classification report ===")
print(classification_report(yte, pred, digits=3))

# ---- plot 1: ROC curve
fpr, tpr, _ = roc_curve(yte, proba)
plt.figure()
plt.plot(fpr, tpr, label=f"ROC AUC = {auc:.3f}")
plt.plot([0,1],[0,1], linestyle="--")
plt.xlabel("False Positive Rate")
plt.ylabel("True Positive Rate")
plt.title("ROC Curve")
plt.legend(loc="lower right")
plt.tight_layout()
plt.savefig("roc_curve.png", dpi=150)
plt.close()

# ---- plot 2: Precision-Recall curve
prec, rec, _ = precision_recall_curve(yte, proba)
ap = average_precision_score(yte, proba)
plt.figure()
plt.plot(rec, prec, label=f"AP = {ap:.3f}")
plt.xlabel("Recall")
plt.ylabel("Precision")
plt.title("Precision-Recall Curve")
plt.legend(loc="lower left")
plt.tight_layout()
plt.savefig("pr_curve.png", dpi=150)
plt.close()

# ---- regressor for amount_mm (only when irrigate==1)
df_pos = df[df["irrigate"]==1].copy()
if len(df_pos) > 100:
    Xr = df_pos[FEATURES]
    yr = df_pos["amount_mm"].astype(float)
    Xr_tr, Xr_te, yr_tr, yr_te = train_test_split(Xr, yr, test_size=0.25, random_state=42)
    reg = Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("rf", RandomForestRegressor(n_estimators=250, random_state=42))
    ])
    reg.fit(Xr_tr, yr_tr)
    yr_pred = reg.predict(Xr_te)
    print("\nRegressor MAE (amount_mm):", round(mean_absolute_error(yr_te, yr_pred), 3))
else:
    reg = None
    print("\nNot enough positive samples to train a regressor.")

# ---- save models
dump({"model": clf, "features": FEATURES}, "irrigate_clf.joblib")
print("Saved irrigate_clf.joblib")

if reg is not None:
    dump({"model": reg, "features": FEATURES}, "amount_reg.joblib")
    print("Saved amount_reg.joblib")

print("\nSaved figures: roc_curve.png, pr_curve.png")
