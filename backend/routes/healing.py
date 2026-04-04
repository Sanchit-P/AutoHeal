from fastapi import APIRouter
from db.database import get_logs

router = APIRouter()

@router.get("/healinglog")
async def get_healing_log():
    rows = await get_logs(limit=20)
    logs = []
    for row in rows:
        logs.append({
            "id": row[0], "timestamp": row[1],
            "metrics": row[2], "anomaly_type": row[3],
            "healing_action": row[4], "confidence": row[5],
            "dry_run": bool(row[6])
        })
    return logs