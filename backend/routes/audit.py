from fastapi import APIRouter, Body
from typing import Any, Dict, List, Optional
from datetime import datetime
import json

from db.database import insert_audit, get_audits

router = APIRouter()

@router.post("/audit/llm")
async def audit_llm(payload: Dict[str, Any] = Body(default_factory=dict)):
    """
    Store an LLM analysis blob with optional metrics snapshot.
    Expected payload:
      {
        "metrics": {...},    # optional
        "analysis": {...}    # required (object or string)
      }
    """
    metrics = payload.get("metrics") or {}
    analysis = payload.get("analysis")
    if analysis is None:
        return {"error": "analysis is required"}
    if not isinstance(analysis, (dict, list, str)):
        analysis = str(analysis)
    await insert_audit({
        "timestamp": datetime.now().isoformat(),
        "kind": "llm",
        "metrics": json.dumps(metrics),
        "analysis": json.dumps(analysis) if not isinstance(analysis, str) else analysis,
    })
    return {"status": "ok"}

@router.get("/audit")
async def list_audit(limit: int = 25):
    rows = await get_audits(limit=limit)
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({
            "id": int(r[0]),
            "timestamp": r[1],
            "kind": r[2],
            "metrics": r[3],
            "analysis": r[4],
        })
    return out

