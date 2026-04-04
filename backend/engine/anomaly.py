from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler
import numpy as np
import os

# Train on "normal" baseline data
BASELINE = np.array([
    [30, 40, 50], [32, 38, 55], [28, 42, 48],
    [31, 39, 52], [29, 41, 51], [33, 37, 53],
])  # [cpu%, memory%, network_mbps]

# Hyperparameters with env overrides
_CONTAM = float(os.environ.get("ANOMALY_CONTAMINATION", "0.08"))
_ZSIGMA = float(os.environ.get("ANOMALY_ZSIGMA", "2.2"))  # z-score threshold

# Fit scaler on baseline to be robust to outliers
_scaler = RobustScaler().fit(BASELINE)
_baseline_scaled = _scaler.transform(BASELINE)

# Train IsolationForest on scaled features
model = IsolationForest(contamination=_CONTAM, random_state=42)
model.fit(_baseline_scaled)

def detect_anomaly(cpu: float, memory: float, network: float):
    data = np.array([[cpu, memory, network]], dtype=float)
    data_s = _scaler.transform(data)

    # Conservative early guard: clearly normal operating range
    if cpu <= 70.0 and memory <= 70.0 and network <= 300.0:
        return False, 5.0

    # IsolationForest signal (on scaled)
    score = model.decision_function(data_s)[0]
    prediction = model.predict(data_s)[0]  # -1 = anomaly, 1 = normal

    # Normalize confidence from IF score (lower score -> more anomalous)
    if_conf = min(100.0, max(0.0, (0.5 - float(score)) * 100.0 + 50.0))
    if_flag = bool(prediction == -1)

    # Z-score ensemble on scaled features against baseline statistics
    mu = _baseline_scaled.mean(axis=0)
    sigma = _baseline_scaled.std(axis=0) + 1e-6
    z = np.abs((data_s[0] - mu) / sigma)
    z_max = float(np.max(z))
    z_flag = bool(z_max >= _ZSIGMA)
    # Convert z to confidence-like [0, 100]; beyond threshold rises quickly
    z_over = max(0.0, z_max - _ZSIGMA)
    z_conf = float(min(100.0, 60.0 + 20.0 * z_over)) if z_flag else float(min(40.0, 10.0 * z_over))

    # Combine signals: take max confidence and OR flag
    is_anomaly = bool(if_flag or z_flag)
    confidence = float(round(max(if_conf, z_conf), 2))

    return is_anomaly, confidence