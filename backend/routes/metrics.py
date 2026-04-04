from fastapi import APIRouter
from engine.anomaly import detect_anomaly
from engine.healer import determine_healing
from db.database import insert_log
from datetime import datetime
import json

router = APIRouter()

# This will receive data FROM Ved's simulator
latest_metrics = {"cpu": 30.0, "memory": 40.0, "network": 50.0}

@router.post("/metrics/ingest")
async def ingest_metrics(data: dict):
    global latest_metrics
    # Normalize incoming metrics to native Python floats
    cpu = float(data["cpu"])
    memory = float(data["memory"])
    network = float(data["network"])
    latest_metrics = {"cpu": cpu, "memory": memory, "network": network}
    
    is_anomaly, confidence = detect_anomaly(cpu, memory, network)
    is_anomaly = bool(is_anomaly)
    confidence = float(confidence)
    
    healing_action, anomaly_type = "no_action", "none"
    if is_anomaly:
        healing_action, anomaly_type = determine_healing(cpu, memory, network, confidence)
    
    dry_run = data.get("dry_run", False)
    
    if is_anomaly and healing_action != "no_action":
        await insert_log({
            "timestamp": datetime.now().isoformat(),
            "metric_snapshot": json.dumps(data),
            "anomaly_type": anomaly_type,
            "healing_action": healing_action,
            "confidence": confidence,
            "dry_run": int(dry_run)
        })
    
    return {
        "cpu": cpu,
        "memory": memory,
        "network": network,
        "is_anomaly": is_anomaly,
        "confidence": confidence,
        "healing_action": healing_action,
        "anomaly_type": anomaly_type,
        "status": "healing" if is_anomaly else "healthy"
    }

@router.get("/metrics/latest")
async def get_latest():
    return latest_metrics