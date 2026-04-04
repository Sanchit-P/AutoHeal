from sklearn.ensemble import IsolationForest
import numpy as np

# Train on "normal" baseline data
BASELINE = np.array([
    [30, 40, 50], [32, 38, 55], [28, 42, 48],
    [31, 39, 52], [29, 41, 51], [33, 37, 53],
])  # [cpu%, memory%, network_mbps]

model = IsolationForest(contamination=0.1, random_state=42)
model.fit(BASELINE)

def detect_anomaly(cpu: float, memory: float, network: float):
    data = np.array([[cpu, memory, network]])
    score = model.decision_function(data)[0]
    prediction = model.predict(data)[0]  # -1 = anomaly, 1 = normal
    
    # Normalize confidence to 0-100%
    confidence = min(100, max(0, (0.5 - score) * 100 + 50))
    is_anomaly = bool(prediction == -1)

    return is_anomaly, float(round(confidence, 2))