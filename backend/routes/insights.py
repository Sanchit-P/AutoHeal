from fastapi import APIRouter, Body
from typing import Any, Dict, List, Optional

from db.database import get_logs
from engine import llm
from .metrics import latest_metrics

router = APIRouter()


def _coerce_metrics(m: Any) -> Dict[str, Any]:
    if not isinstance(m, dict):
        return dict(latest_metrics)
    out: Dict[str, Any] = {}
    for k, v in m.items():
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            out[k] = v
    return out


async def _healing_logs(limit: int) -> List[Dict[str, Any]]:
    rows = await get_logs(limit=limit)
    logs: List[Dict[str, Any]] = []
    for row in rows:
        logs.append({
            "id": int(row[0]),
            "timestamp": row[1],
            "metrics": row[2],
            "anomaly_type": row[3],
            "healing_action": row[4],
            "confidence": float(row[5]),
            "dry_run": bool(row[6]),
        })
    return logs


@router.post("/insights/explain")
async def explain_failure(
    payload: Optional[Dict[str, Any]] = Body(default=None),
):
    payload = payload or {}
    metrics = _coerce_metrics(payload.get("metrics") or latest_metrics)
    use_recent_logs = bool(payload.get("use_recent_logs", True))
    log_limit = int(payload.get("log_limit", 10))
    logs: List[Dict[str, Any]] = []
    if use_recent_logs:
        logs = await _healing_logs(log_limit)
    analysis = llm.suggest_root_cause(metrics=metrics, logs=logs)
    return {"metrics_snapshot": metrics, "analysis": analysis}


@router.post("/insights/playbook")
async def remediation_playbook(payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Remediation runbook: Kubernetes, systemd, or AWS-oriented steps."""
    p = payload or {}
    metrics = _coerce_metrics(p.get("metrics") or latest_metrics)
    target = str(p.get("target", "kubernetes"))
    logs = await _healing_logs(int(p.get("log_limit", 8))) if p.get("use_recent_logs", True) else []
    result = llm.generate_remediation_playbook(
        metrics,
        target=target,
        anomaly_type=str(p.get("anomaly_type", "unknown")),
        healing_action=str(p.get("healing_action", "unknown")),
        logs=logs,
    )
    return {"metrics_snapshot": metrics, "playbook": result}


@router.post("/insights/safety-check")
async def safety_check(payload: Dict[str, Any] = Body(default_factory=dict)):
    """Evaluate a proposed healing action before execution."""
    proposed = payload.get("proposed_action") or payload.get("healing_action")
    if not proposed:
        return {"error": "proposed_action (or healing_action) is required"}
    metrics = _coerce_metrics(payload.get("metrics") or latest_metrics)
    ctx = payload.get("context")
    if ctx is not None and not isinstance(ctx, str):
        ctx = str(ctx)
    return {"metrics_snapshot": metrics, "safety": llm.check_action_safety(proposed, metrics, ctx)}


@router.post("/insights/summarize")
async def incident_summarize(payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Human-readable incident summary + Slack-ready text."""
    p = payload or {}
    metrics = _coerce_metrics(p.get("metrics") or latest_metrics)
    logs = await _healing_logs(int(p.get("log_limit", 15))) if p.get("use_recent_logs", True) else []
    return {"metrics_snapshot": metrics, "incident": llm.summarize_incident(metrics, logs)}


@router.post("/insights/triage")
async def alert_triage(payload: Dict[str, Any] = Body(default_factory=dict)):
    """Deduplicate and prioritize a batch of alerts."""
    alerts = payload.get("alerts")
    if not isinstance(alerts, list):
        return {"error": "alerts must be a list of objects with id, title, optional metric_snapshot"}
    return {"triage": llm.triage_alerts(alerts)}


@router.post("/insights/postmortem")
async def postmortem_draft(payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Postmortem draft from healing log history."""
    p = payload or {}
    limit = int(p.get("log_limit", 25))
    logs = await _healing_logs(limit)
    return {"postmortem": llm.draft_postmortem(logs)}


@router.post("/insights/query")
async def nl_telemetry_query(payload: Dict[str, Any] = Body(default_factory=dict)):
    """Natural-language question over current metrics + recent logs."""
    q = payload.get("question")
    if not q:
        return {"error": "question is required"}
    metrics = _coerce_metrics(payload.get("metrics") or latest_metrics)
    logs = await _healing_logs(int(payload.get("log_limit", 10))) if payload.get("use_recent_logs", True) else []
    return {
        "metrics_snapshot": metrics,
        "answer": llm.answer_telemetry_question(str(q), metrics, logs),
    }


@router.post("/insights/canary")
async def canary(payload: Dict[str, Any] = Body(default_factory=dict)):
    """Compare pre/post deploy metrics; recommend hold, roll_forward, or rollback."""
    pre = payload.get("pre_metrics")
    post = payload.get("post_metrics")
    if not isinstance(pre, dict) or not isinstance(post, dict):
        return {"error": "pre_metrics and post_metrics objects are required"}
    pre_c = _coerce_metrics(pre)
    post_c = _coerce_metrics(post)
    label = payload.get("deploy_label")
    return {"guidance": llm.canary_guidance(pre_c, post_c, str(label) if label is not None else None)}


@router.post("/insights/slo")
async def slo(payload: Dict[str, Any] = Body(default_factory=dict)):
    """SLO / error-budget narrative and capacity ideas."""
    name = payload.get("slo_name") or "availability"
    try:
        target = float(payload.get("target_percent", 99.9))
        budget = float(payload.get("error_budget_remaining_percent", 50))
    except (TypeError, ValueError):
        return {"error": "target_percent and error_budget_remaining_percent must be numbers"}
    metrics = _coerce_metrics(payload.get("metrics") or latest_metrics)
    return {"metrics_snapshot": metrics, "slo": llm.slo_insights(str(name), target, budget, metrics)}


@router.post("/insights/dependencies")
async def dependencies(payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Infer likely downstream impact from symptoms."""
    p = payload or {}
    symptoms = p.get("symptoms")
    if symptoms is None:
        symptoms = _coerce_metrics(p.get("metrics") or latest_metrics)
    elif isinstance(symptoms, dict):
        symptoms = _coerce_metrics(symptoms)
    else:
        symptoms = {"description": str(symptoms)}
    known = p.get("known_dependencies")
    if known is not None and not isinstance(known, list):
        known = [str(known)]
    return {"impact": llm.dependency_impact_analysis(symptoms, known)}


@router.post("/insights/config-drift")
async def config_drift(payload: Dict[str, Any] = Body(default_factory=dict)):
    """Relate config/infra diff text to observed metrics."""
    diff = payload.get("config_diff") or payload.get("diff")
    if diff is None:
        return {"error": "config_diff (or diff) string is required"}
    metrics = _coerce_metrics(payload.get("metrics") or latest_metrics)
    return {"metrics_snapshot": metrics, "drift": llm.explain_config_drift(str(diff), metrics)}


@router.post("/insights/runbook-qa")
async def runbook_qa(payload: Dict[str, Any] = Body(default_factory=dict)):
    """Review a runbook: gaps, commands, environment-tailored steps."""
    text = payload.get("runbook_text") or payload.get("runbook")
    if not text:
        return {"error": "runbook_text is required"}
    env = payload.get("environment")
    if env is not None and not isinstance(env, dict):
        env = {"note": str(env)}
    return {"review": llm.review_runbook(str(text), env)}


@router.post("/insights/hypotheses")
async def hypotheses(payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Multiple ranked root-cause hypotheses with evidence."""
    p = payload or {}
    metrics = _coerce_metrics(p.get("metrics") or latest_metrics)
    logs = await _healing_logs(int(p.get("log_limit", 10))) if p.get("use_recent_logs", True) else []
    return {"metrics_snapshot": metrics, "hypotheses": llm.rank_root_cause_hypotheses(metrics, logs)}


@router.post("/insights/narrative")
async def narrative(payload: Optional[Dict[str, Any]] = Body(default=None)):
    """Proactive risk narrative across services + recent incidents."""
    p = payload or {}
    services = p.get("services")
    if services is not None and not isinstance(services, list):
        services = None
    logs = await _healing_logs(int(p.get("log_limit", 15))) if p.get("use_recent_logs", True) else []
    return {"narrative": llm.proactive_risk_narrative(services, logs)}


@router.post("/insights/log-signals")
async def log_signals(payload: Dict[str, Any] = Body(default_factory=dict)):
    """Turn unstructured log lines into structured signals for features/alerts."""
    lines = payload.get("log_lines") or payload.get("lines")
    if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
        return {"error": "log_lines must be a list of strings"}
    return {"signals": llm.unstructured_logs_to_signals(lines)}


@router.post("/insights/security-check")
async def security_check(payload: Dict[str, Any] = Body(default_factory=dict)):
    """Security-oriented triage (phishing/auth/generic) for supplied text/context."""
    text = payload.get("text") or payload.get("content")
    if not text:
        return {"error": "text (or content) is required"}
    check_type = str(payload.get("check_type", "generic"))
    return {"security": llm.security_context_check(str(text), check_type)}


@router.get("/insights/capabilities")
def list_capabilities():
    """Describe available LLM insight endpoints."""
    return {
        "endpoints": [
            {"path": "/insights/explain", "use_case": "single-label RCA + remediation hints"},
            {"path": "/insights/playbook", "use_case": "tool-specific remediation runbooks"},
            {"path": "/insights/safety-check", "use_case": "action risk / blast radius"},
            {"path": "/insights/summarize", "use_case": "incident summary + Slack snippet"},
            {"path": "/insights/triage", "use_case": "alert dedup and prioritization"},
            {"path": "/insights/postmortem", "use_case": "postmortem draft from logs"},
            {"path": "/insights/query", "use_case": "NL questions over telemetry"},
            {"path": "/insights/canary", "use_case": "canary hold / roll / rollback"},
            {"path": "/insights/slo", "use_case": "SLO breach narrative + capacity"},
            {"path": "/insights/dependencies", "use_case": "downstream impact"},
            {"path": "/insights/config-drift", "use_case": "config diff vs metrics"},
            {"path": "/insights/runbook-qa", "use_case": "runbook QA / copilot"},
            {"path": "/insights/hypotheses", "use_case": "ranked multi-hypothesis RCA"},
            {"path": "/insights/narrative", "use_case": "proactive risk narrative"},
            {"path": "/insights/log-signals", "use_case": "logs to structured signals"},
            {"path": "/insights/security-check", "use_case": "security-style text review"},
        ],
        "llm_configured": llm.is_llm_configured(),
    }
