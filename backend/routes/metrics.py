from fastapi import APIRouter
from engine.anomaly import detect_anomaly
from engine.healer import determine_healing
from engine.llm import suggest_root_cause
from db.database import insert_log
from datetime import datetime
import json
import time
from typing import Dict, Any
from engine.predict import MetricHistory, summarize_forecast
import os

router = APIRouter()

# This will receive data FROM Ved's simulator
latest_metrics = {"cpu": 30.0, "memory": 40.0, "network": 50.0}

# Rolling histories for simple forecasting
_HISTORIES = {
    "cpu": MetricHistory(maxlen=180),
    "memory": MetricHistory(maxlen=180),
    "network": MetricHistory(maxlen=180),
}

# Soft thresholds for proactive alerts (percent / mbps-style scale), env-configurable
_THRESHOLDS = {
    "cpu": float(os.environ.get("FORECAST_CPU_THRESHOLD", "80")),
    "memory": float(os.environ.get("FORECAST_MEMORY_THRESHOLD", "80")),
    "network": float(os.environ.get("FORECAST_NETWORK_THRESHOLD", "400")),
}
_HORIZON_S = float(os.environ.get("FORECAST_HORIZON_SECONDS", "300"))  # default 5 minutes

@router.post("/metrics/ingest")
async def ingest_metrics(data: dict):
    global latest_metrics
    # Normalize incoming metrics to native Python floats
    cpu = float(data["cpu"])
    memory = float(data["memory"])
    network = float(data["network"])
    latest_metrics = {"cpu": cpu, "memory": memory, "network": network}
    # Update rolling histories
    now_s = time.time()
    _HISTORIES["cpu"].add(cpu, now_s)
    _HISTORIES["memory"].add(memory, now_s)
    _HISTORIES["network"].add(network, now_s)
    
    is_anomaly, confidence = detect_anomaly(cpu, memory, network)
    is_anomaly = bool(is_anomaly)
    confidence = float(confidence)
    
    healing_action, anomaly_type = "no_action", "none"
    if is_anomaly:
        healing_action, anomaly_type = determine_healing(cpu, memory, network, confidence)

    llm_analysis = None
    if is_anomaly:
        try:
            llm_analysis = suggest_root_cause(
                {"cpu": cpu, "memory": memory, "network": network},
                [],
            )
        except Exception:
            llm_analysis = None

    dry_run = data.get("dry_run", False)

    # Forecasts for proactive detection (e.g., memory leak before threshold)
    forecast: Dict[str, Any] = {
        "cpu": summarize_forecast(_HISTORIES["cpu"], _THRESHOLDS["cpu"], _HORIZON_S),
        "memory": summarize_forecast(_HISTORIES["memory"], _THRESHOLDS["memory"], _HORIZON_S),
        "network": summarize_forecast(_HISTORIES["network"], _THRESHOLDS["network"], _HORIZON_S),
    }

    # Suggest proactive action if memory is trending to cross threshold soon
    proactive_action = None
    mem_fore = forecast["memory"]
    mem_risk = mem_fore.get("risk")
    # Guard: require sufficient history + positive trend + below hard threshold
    has_history = _HISTORIES["memory"].has_enough_points()
    growth = float(mem_fore.get("approx_growth_rate_per_min") or mem_fore.get("slope_per_min") or 0.0)
    if has_history and growth > 0 and memory < _THRESHOLDS["memory"] and mem_risk in ("high", "medium"):
        proactive_action = "preemptive_scale_up" if memory > 70 else "preemptive_restart_candidate"
    
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
        "status": "healing" if is_anomaly else "healthy",
        "forecast": forecast,
        "proactive_action": proactive_action,
        "llm_analysis": llm_analysis,
    }

@router.get("/metrics/latest")
async def get_latest():
    return latest_metrics

@router.get("/metrics/forecast")
async def get_forecast():
    """Return short-horizon forecasts and risk for each metric."""
    out = {
        "cpu": summarize_forecast(_HISTORIES["cpu"], _THRESHOLDS["cpu"], _HORIZON_S),
        "memory": summarize_forecast(_HISTORIES["memory"], _THRESHOLDS["memory"], _HORIZON_S),
        "network": summarize_forecast(_HISTORIES["network"], _THRESHOLDS["network"], _HORIZON_S),
        "thresholds": dict(_THRESHOLDS),
        "horizon_seconds": _HORIZON_S,
    }
    return out