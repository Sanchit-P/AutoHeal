from fastapi import APIRouter
from typing import Optional, Dict, Any, List
from db.database import get_logs
from engine.llm import suggest_root_cause
from .metrics import latest_metrics

router = APIRouter()

@router.post("/insights/explain")
async def explain_failure(payload: Optional[Dict[str, Any]] = None):
    """
    Body (optional):
    {
      "metrics": {"cpu": .., "memory": .., "network": ..},
      "use_recent_logs": true,
      "log_limit": 10
    }
    """
    payload = payload or {}
    metrics = payload.get("metrics") or latest_metrics
    use_recent_logs = bool(payload.get("use_recent_logs", True))
    log_limit = int(payload.get("log_limit", 10))

    logs: List[Dict[str, Any]] = []
    if use_recent_logs:
        rows = await get_logs(limit=log_limit)
        for row in rows:
            logs.append({
                "id": row[0],
                "timestamp": row[1],
                "metrics": row[2],
                "anomaly_type": row[3],
                "healing_action": row[4],
                "confidence": row[5],
                "dry_run": bool(row[6]),
            })

    analysis = suggest_root_cause(metrics=metrics, logs=logs)
    return {"metrics_snapshot": metrics, "analysis": analysis}