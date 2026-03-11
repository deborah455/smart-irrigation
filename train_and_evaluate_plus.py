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
    roc_curve, precision_recall_curve, average_precision_score,
    mean_absolute_error, precision_score, recall_score, f1_score
)
from sklearn.calibration import calibration_curve
from joblib import dump

# ---------- 0) Load data ----------
df = pd.read_csv("dataset2_training.csv")

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

# ---------- 1) Classifier (Logistic Regression) ----------
clf = Pipeline([
    ("imp", SimpleImputer(strategy="median")),
    ("lr", LogisticRegression(max_iter=1000))
])
clf.fit(Xtr, ytr)

proba = clf.predict_proba(Xte)[:,1]
pred  = (proba >= 0.5).astype(int)

# Metrics text
cm = confusion_matrix(yte, pred)
auc = roc_auc_score(yte, proba)
ap  = average_precision_score(yte, proba)
print("\n=== Confusion Matrix (rows=true, cols=pred) ===")
print(pd.DataFrame(cm, index=["True 0","True 1"], columns=["Pred 0","Pred 1"]))
print(f"\nAUROC: {auc:.3f}   Average Precision: {ap:.3f}")
print("\n=== Classification report ===")
print(classification_report(yte, pred, digits=3))

# ---------- 2) FIGURE: Confusion Matrix (image) ----------
plt.figure()
plt.imshow(cm, cmap="Blues")
plt.title("Confusion Matrix")
plt.xlabel("Predicted")
plt.ylabel("True")
for (i,j), v in np.ndenumerate(cm):
    plt.text(j, i, str(v), ha="center", va="center")
plt.colorbar()
plt.tight_layout()
plt.savefig("confusion_matrix.png", dpi=160)
plt.close()

# ---------- 3) FIGURE: ROC ----------
fpr, tpr, _ = roc_curve(yte, proba)
plt.figure()
plt.plot(fpr, tpr, label=f"AUC = {auc:.3f}")
plt.plot([0,1],[0,1],"--")
plt.xlabel("False Positive Rate")
plt.ylabel("True Positive Rate")
plt.title("ROC Curve")
plt.legend(loc="lower right")
plt.tight_layout()
plt.savefig("roc_curve.png", dpi=160)
plt.close()

# ---------- 4) FIGURE: Precision–Recall ----------
prec, rec, _ = precision_recall_curve(yte, proba)
plt.figure()
plt.plot(rec, prec, label=f"AP = {ap:.3f}")
plt.xlabel("Recall")
plt.ylabel("Precision")
plt.title("Precision–Recall Curve")
plt.legend(loc="lower left")
plt.tight_layout()
plt.savefig("pr_curve.png", dpi=160)
plt.close()

# ---------- 5) FIGURE: Calibration (Reliability) Curve ----------
prob_true, prob_pred = calibration_curve(yte, proba, n_bins=10, strategy="uniform")
plt.figure()
plt.plot([0,1],[0,1],"--", label="Perfectly calibrated")
plt.plot(prob_pred, prob_true, marker="o", label="Model")
plt.xlabel("Mean predicted probability")
plt.ylabel("Fraction of positives")
plt.title("Calibration Curve")
plt.legend()
plt.tight_layout()
plt.savefig("calibration_curve.png", dpi=160)
plt.close()

# ---------- 6) FIGURE: Feature Importance (LogReg |coef|) ----------
coefs = np.abs(clf.named_steps["lr"].coef_[0])
order = np.argsort(coefs)[::-1]
topk = min(15, len(FEATURES))
plt.figure(figsize=(8,6))
plt.barh([FEATURES[i] for i in order[:topk]][::-1], coefs[order[:topk]][::-1])
plt.title("Top Feature Importance (|LogReg Coefficients|)")
plt.xlabel("|Coefficient|")
plt.tight_layout()
plt.savefig("feature_importance.png", dpi=160)
plt.close()

# ---------- 7) FIGURE: Threshold Sweep (F1 / Precision / Recall) ----------
ths = np.linspace(0.05, 0.95, 19)
f1s, pres, recs = [], [], []
for t in ths:
    p = (proba >= t).astype(int)
    f1s.append(f1_score(yte, p, zero_division=0))
    pres.append(precision_score(yte, p, zero_division=0))
    recs.append(recall_score(yte, p, zero_division=0))
plt.figure()
plt.plot(ths, f1s, label="F1")
plt.plot(ths, pres, label="Precision")
plt.plot(ths, recs, label="Recall")
plt.xlabel("Threshold")
plt.ylabel("Score")
plt.title("Threshold vs F1 / Precision / Recall")
plt.legend()
plt.tight_layout()
plt.savefig("threshold_metrics.png", dpi=160)
plt.close()

# ---------- 8) Amount Regressor (optional) ----------
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
    mae = mean_absolute_error(yr_te, yr_pred)
    print(f"\nAmount regressor MAE: {mae:.3f} mm")

    # scatter figure
    plt.figure()
    plt.scatter(yr_te, yr_pred, alpha=0.5)
    lims = [0, max(12, float(np.nanmax(yr_te)*1.1))]
    plt.plot(lims, lims, "--")
    plt.xlabel("Actual amount_mm")
    plt.ylabel("Predicted amount_mm")
    plt.title("Amount Regressor: Pred vs Actual")
    plt.tight_layout()
    plt.savefig("amount_reg_scatter.png", dpi=160)
    plt.close()

    dump({"model": reg, "features": FEATURES}, "amount_reg.joblib")
    print("Saved amount_reg.joblib")
else:
    print("\nNot enough positive samples to train amount regressor.")

# ---------- 9) Save classifier model ----------
from joblib import dump
dump({"model": clf, "features": FEATURES}, "irrigate_clf.joblib")
print("Saved irrigate_clf.joblib")

print("\nSaved figures:",
      "confusion_matrix.png, roc_curve.png, pr_curve.png,",
      "calibration_curve.png, feature_importance.png, threshold_metrics.png,",
      "amount_reg_scatter.png (if available)")
