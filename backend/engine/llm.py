import json
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv  # type: ignore

try:
    from groq import Groq  # type: ignore
except Exception:
    Groq = None  # type: ignore

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def _load_keys() -> List[str]:
    load_dotenv()
    keys: List[str] = []
    for k, v in os.environ.items():
        if k.upper().startswith("GROQ_API_KEY_") and v:
            keys.append(v)
    return keys


class KeyManager:
    def __init__(self, keys: List[str]):
        self.keys = keys
        self.current_index = 0

    def get_client(self):
        if not self.keys:
            raise RuntimeError("No GROQ_API_KEY_* found in environment.")
        return Groq(api_key=self.keys[self.current_index])

    def rotate(self):
        if not self.keys:
            return
        self.current_index = (self.current_index + 1) % len(self.keys)
        print(f"Switched to Groq Key Index: {self.current_index}")


_API_KEYS = _load_keys()
_key_manager = KeyManager(_API_KEYS)


def _llm_available() -> bool:
    return Groq is not None and bool(_API_KEYS)


def is_llm_configured() -> bool:
    """True when Groq SDK is importable and at least one GROQ_API_KEY_* is set."""
    return _llm_available()


def _groq_json(
    system: str,
    user_content: str,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    timeout: float = 14.0,
    max_attempts: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    if not _llm_available():
        return None
    attempts = max_attempts or max(len(_API_KEYS), 1)
    for _ in range(attempts):
        try:
            client = _key_manager.get_client()
            resp = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
                timeout=timeout,
            )
            content = resp.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as e:
            em = str(e).lower()
            if "429" in em or "rate" in em:
                print(f"Key {_key_manager.current_index} rate-limited. Rotating...")
                _key_manager.rotate()
                continue
            print(f"LLM error: {e}")
            break
    return None


def _fallback_rca(metrics: Dict[str, Any]) -> Dict[str, Any]:
    cpu = float(metrics.get("cpu", 0.0))
    memory = float(metrics.get("memory", 0.0))
    network = float(metrics.get("network", 0.0))

    reasons: List[str] = []
    suggestions: List[str] = []

    if cpu > 75 and network > 80:
        likely = "DDoS_Pattern"
        reasons.append("High CPU with high network throughput suggests external traffic surge.")
        suggestions.extend(["Throttle traffic", "Enable/adjust WAF rules", "Rate limit"])
        conf = 0.85
    elif cpu > 75 and network <= 80:
        likely = "Internal_Overload"
        reasons.append("High CPU without proportional network indicates internal hot path.")
        suggestions.extend(["Rolling restart", "Profile hotspots", "Scale replicas"])
        conf = 0.75
    elif memory > 80:
        likely = "Memory_Leak"
        reasons.append("Sustained high memory usage indicates leaks or unbounded caches.")
        suggestions.extend(["Restart/roll pod", "Add memory limits", "Investigate heap profiles"])
        conf = 0.8
    elif cpu < 10 and network < 10:
        likely = "Service_Down"
        reasons.append("Low CPU and network suggests process crash or hung service.")
        suggestions.extend(["Restart service", "Probe liveness/readiness failures", "Check recent deploys"])
        conf = 0.7
    else:
        likely = "Unknown"
        reasons.append("Signals do not match common failure patterns.")
        suggestions.extend(["Collect more metrics/logs", "Check recent changes", "Run health checks"])
        conf = 0.5

    return {
        "reasons": reasons,
        "likely_cause": likely,
        "confidence": round(conf * 100, 1),
        "remediation_suggestions": suggestions,
        "source": "deterministic_fallback",
    }


def _build_rca_prompt(metrics: Dict[str, Any], logs: List[Dict[str, Any]]) -> str:
    context = {
        "metrics": metrics,
        "recent_healing_logs": logs[:10],
        "instructions": [
            "You are a Senior SRE.",
            "Explain the likely root cause of the current server failure/anomaly.",
            "Use only the provided metrics and recent healing logs.",
            "Return strict JSON only with: reasons[], likely_cause, confidence(0-100), remediation_suggestions[].",
        ],
    }
    return json.dumps(context, indent=2)


def suggest_root_cause(
    metrics: Dict[str, Any],
    logs: Optional[List[Dict[str, Any]]] = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    timeout: float = 6.0,
    max_attempts: Optional[int] = None,
) -> Dict[str, Any]:
    if Groq is None:
        out = _fallback_rca(metrics)
        out["reasons"] = ["Groq SDK not installed."] + out["reasons"]
        out["likely_cause"] = "LLMUnavailable"
        out["remediation_suggestions"] = ["pip install groq"] + out["remediation_suggestions"]
        return out

    if not _API_KEYS:
        out = _fallback_rca(metrics)
        out["reasons"] = ["Missing GROQ_API_KEY_* environment variables."] + out["reasons"]
        out["likely_cause"] = "ConfigurationError"
        return out

    prompt = _build_rca_prompt(metrics, logs or [])
    system = "You are a precise SRE assistant. Respond only in valid JSON."
    user = f"Analyze and output strict JSON only:\n{prompt}"
    parsed = _groq_json(system, user, model=model, temperature=temperature, timeout=timeout, max_attempts=max_attempts)
    if parsed:
        return {
            "reasons": parsed.get("reasons", []),
            "likely_cause": parsed.get("likely_cause", "Unknown"),
            "confidence": parsed.get("confidence", 50),
            "remediation_suggestions": parsed.get("remediation_suggestions", []),
            "source": "llm",
        }
    out = _fallback_rca(metrics)
    out["source"] = "deterministic_fallback"
    return out


# --- Use-case helpers (prompt + optional fallback) ---

def _stub(source: str, use_case: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"source": source, "use_case": use_case, **payload}


def generate_remediation_playbook(
    metrics: Dict[str, Any],
    target: str = "kubernetes",
    anomaly_type: str = "unknown",
    healing_action: str = "unknown",
    logs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    target = (target or "kubernetes").lower()
    ctx = {
        "metrics": metrics,
        "anomaly_type": anomaly_type,
        "healing_action": healing_action,
        "target_platform": target,
        "recent_healing_logs": (logs or [])[:8],
        "output_schema": {
            "title": "string",
            "steps": ["ordered CLI or console steps tailored to the target"],
            "prerequisites": ["checks before acting"],
            "rollback_steps": ["how to undo"],
            "tools": ["e.g. kubectl, systemctl, aws cli"],
        },
    }
    system = (
        "You are a senior SRE. Produce a practical remediation runbook. "
        "Steps must match the target platform (kubernetes vs systemd vs aws). "
        "Respond only in valid JSON matching output_schema keys."
    )
    parsed = _groq_json(system, json.dumps(ctx, indent=2), timeout=16.0)
    if parsed:
        parsed["source"] = "llm"
        return parsed
    base = _fallback_rca(metrics)
    return _stub(
        "deterministic_fallback",
        "playbook",
        {
            "title": f"Remediate {base['likely_cause']} on {target}",
            "steps": base["remediation_suggestions"],
            "prerequisites": ["Confirm blast radius", "Take a snapshot of current metrics"],
            "rollback_steps": ["Revert last config change", "Scale replicas back"],
            "tools": ["kubectl"] if target == "kubernetes" else ["systemctl"] if target == "systemd" else ["aws"],
        },
    )


def check_action_safety(
    proposed_action: str,
    metrics: Dict[str, Any],
    context: Optional[str] = None,
) -> Dict[str, Any]:
    ctx = {
        "proposed_healing_action": proposed_action,
        "current_metrics": metrics,
        "extra_context": context or "",
        "output_schema": {
            "risk_level": "low|medium|high",
            "blast_radius": "string",
            "prerequisites": [],
            "blockers": [],
            "approve_recommendation": "proceed|hold|reject",
            "rationale": "string",
        },
    }
    system = "You are an SRE safety reviewer. Assess risk before automation runs. JSON only."
    parsed = _groq_json(system, json.dumps(ctx, indent=2), temperature=0.1)
    if parsed:
        parsed["source"] = "llm"
        return parsed
    return _stub(
        "deterministic_fallback",
        "safety_check",
        {
            "risk_level": "medium",
            "blast_radius": "Single host / service scope assumed",
            "prerequisites": ["Verify dry_run flag", "Notify on-call"],
            "blockers": [],
            "approve_recommendation": "hold",
            "rationale": "LLM unavailable; default to human review.",
        },
    )


def summarize_incident(metrics: Dict[str, Any], logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    ctx = {"metrics": metrics, "healing_logs": logs[:15], "output_schema": {
        "title": "string",
        "severity": "sev1|sev2|sev3|sev4",
        "summary": "2-4 sentences",
        "timeline_bullets": [],
        "slack_message": "short paste-ready message",
    }}
    system = "You are an incident commander writing concise updates. JSON only."
    parsed = _groq_json(system, json.dumps(ctx, indent=2))
    if parsed:
        parsed["source"] = "llm"
        return parsed
    base = _fallback_rca(metrics)
    return _stub(
        "deterministic_fallback",
        "summarize",
        {
            "title": "Anomaly detected",
            "severity": "sev3",
            "summary": f"Signals point to {base['likely_cause']}. " + (base["reasons"][0] if base["reasons"] else ""),
            "timeline_bullets": [f"Latest: {log.get('timestamp', '?')}" for log in logs[:3]],
            "slack_message": f":rotating_light: Anomaly — {base['likely_cause']}. Investigating.",
        },
    )


def triage_alerts(alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    ctx = {"alerts": alerts[:30], "output_schema": {
        "groups": [{"group_id": "string", "alert_ids": [], "theme": "string"}],
        "priority_order": ["alert ids highest impact first"],
        "suppress_suggestions": [{"alert_ids": [], "reason": "string"}],
        "notes": "string",
    }}
    system = "You deduplicate and triage infra alerts. JSON only."
    parsed = _groq_json(system, json.dumps(ctx, indent=2))
    if parsed:
        parsed["source"] = "llm"
        return parsed
    ids = [str(a.get("id", i)) for i, a in enumerate(alerts[:10])]
    return _stub(
        "deterministic_fallback",
        "triage",
        {
            "groups": [{"group_id": "g1", "alert_ids": ids, "theme": "ungrouped"}],
            "priority_order": ids,
            "suppress_suggestions": [],
            "notes": "LLM unavailable; review alerts manually.",
        },
    )


def draft_postmortem(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    ctx = {"healing_log_history": logs[:25], "output_schema": {
        "title": "string",
        "timeline": [],
        "contributing_factors": [],
        "five_whys": [],
        "action_items": [{"owner": "string", "item": "string"}],
    }}
    system = "You draft blameless postmortems from incident logs. JSON only."
    parsed = _groq_json(system, json.dumps(ctx, indent=2), timeout=18.0)
    if parsed:
        parsed["source"] = "llm"
        return parsed
    return _stub(
        "deterministic_fallback",
        "postmortem",
        {
            "title": "Draft postmortem (insufficient LLM)",
            "timeline": [f"{log.get('timestamp', '?')}: {log.get('anomaly_type', '?')}" for log in logs[:5]],
            "contributing_factors": ["Limited automated analysis without LLM"],
            "five_whys": ["Why? Anomaly observed", "Why? Threshold/model flagged it", "Why? Load or failure pattern", "Why? TBD", "Why? TBD"],
            "action_items": [{"owner": "sre", "item": "Review healing_log entries"}],
        },
    )


def answer_telemetry_question(
    question: str,
    metrics: Dict[str, Any],
    logs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    ctx = {
        "question": question,
        "current_metrics": metrics,
        "recent_logs_excerpt": logs[:10],
        "output_schema": {
            "answer": "string",
            "confidence": "0-100 number",
            "evidence": ["bullet refs to metrics or log fields"],
        },
    }
    system = "You answer natural-language questions about telemetry using only provided data. JSON only."
    parsed = _groq_json(system, json.dumps(ctx, indent=2))
    if parsed:
        parsed["source"] = "llm"
        return parsed
    return _stub(
        "deterministic_fallback",
        "nl_query",
        {
            "answer": "Cannot answer precisely without LLM; see current_metrics and recent_logs_excerpt in request context.",
            "confidence": 20,
            "evidence": [f"cpu={metrics.get('cpu')}", f"memory={metrics.get('memory')}", f"network={metrics.get('network')}"],
        },
    )


def canary_guidance(
    pre_metrics: Dict[str, Any],
    post_metrics: Dict[str, Any],
    deploy_label: Optional[str] = None,
) -> Dict[str, Any]:
    ctx = {
        "pre_deploy_metrics": pre_metrics,
        "post_deploy_metrics": post_metrics,
        "deploy_label": deploy_label or "unspecified",
        "output_schema": {
            "recommendation": "hold|roll_forward|rollback",
            "rationale": "string",
            "key_deltas": {"cpu": "string", "memory": "string", "network": "string"},
        },
    }
    system = "You compare canary vs baseline metrics and recommend hold, roll_forward, or rollback. JSON only."
    parsed = _groq_json(system, json.dumps(ctx, indent=2))
    if parsed:
        parsed["source"] = "llm"
        return parsed

    def delta(a: Dict[str, Any], b: Dict[str, Any], k: str) -> float:
        return float(b.get(k, 0)) - float(a.get(k, 0))

    d_cpu = delta(pre_metrics, post_metrics, "cpu")
    d_mem = delta(pre_metrics, post_metrics, "memory")
    rec = "hold"
    if d_cpu > 25 or d_mem > 20:
        rec = "rollback"
    elif abs(d_cpu) < 8 and abs(d_mem) < 8:
        rec = "roll_forward"
    return _stub(
        "deterministic_fallback",
        "canary",
        {
            "recommendation": rec,
            "rationale": "Heuristic delta on cpu/memory vs pre-deploy snapshot.",
            "key_deltas": {
                "cpu": f"{d_cpu:+.1f}",
                "memory": f"{d_mem:+.1f}",
                "network": f"{delta(pre_metrics, post_metrics, 'network'):+.1f}",
            },
        },
    )


def slo_insights(
    slo_name: str,
    target_percent: float,
    error_budget_remaining_percent: float,
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    ctx = {
        "slo_name": slo_name,
        "target_availability_or_success_percent": target_percent,
        "error_budget_remaining_percent": error_budget_remaining_percent,
        "live_metrics": metrics,
        "output_schema": {
            "breach_explanation": "string",
            "capacity_or_throttling_suggestions": [],
            "tradeoffs": "string",
        },
    }
    system = "You explain SLO/error-budget posture and suggest capacity or throttling. JSON only."
    parsed = _groq_json(system, json.dumps(ctx, indent=2))
    if parsed:
        parsed["source"] = "llm"
        return parsed
    return _stub(
        "deterministic_fallback",
        "slo",
        {
            "breach_explanation": f"{slo_name}: budget at {error_budget_remaining_percent}% vs target {target_percent}%.",
            "capacity_or_throttling_suggestions": ["Scale out if latency tied to CPU", "Add rate limits if network-bound"],
            "tradeoffs": "Higher cost vs reliability; tune autoscaling thresholds.",
        },
    )


def dependency_impact_analysis(
    symptoms: Dict[str, Any],
    known_dependencies: Optional[List[str]] = None,
) -> Dict[str, Any]:
    ctx = {
        "symptom_metrics_or_text": symptoms,
        "known_dependencies": known_dependencies or [],
        "output_schema": {
            "likely_affected_downstreams": [],
            "reasoning": "string",
            "past_pattern_hints": [],
        },
    }
    system = "You infer dependency impact from symptoms and known edges. JSON only."
    parsed = _groq_json(system, json.dumps(ctx, indent=2))
    if parsed:
        parsed["source"] = "llm"
        return parsed
    downs = list(known_dependencies or ["api-gateway", "worker-queue", "cache"])
    return _stub(
        "deterministic_fallback",
        "dependencies",
        {
            "likely_affected_downstreams": downs[:3],
            "reasoning": "High CPU/network often backs up callers; verify listed dependencies.",
            "past_pattern_hints": ["Check error rates on downstream dashboards"],
        },
    )


def explain_config_drift(
    config_diff: str,
    related_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    ctx = {
        "config_diff": config_diff[:8000],
        "related_metrics": related_metrics,
        "output_schema": {
            "summary": "string",
            "correlation_hypothesis": "string",
            "verification_steps": [],
        },
    }
    system = "You connect infra/config drift to observed metrics. JSON only."
    parsed = _groq_json(system, json.dumps(ctx, indent=2))
    if parsed:
        parsed["source"] = "llm"
        return parsed
    return _stub(
        "deterministic_fallback",
        "config_drift",
        {
            "summary": "Diff provided; correlate manually with metric shifts.",
            "correlation_hypothesis": "Config changes near deploy window often explain latency/CPU shifts.",
            "verification_steps": ["Diff last release", "Compare autoscaling settings", "Audit env vars"],
        },
    )


def review_runbook(runbook_text: str, environment: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ctx = {
        "runbook_markdown_or_plaintext": runbook_text[:12000],
        "environment_hints": environment or {},
        "output_schema": {
            "gaps": [],
            "suggested_commands": [],
            "tailored_steps": [],
        },
    }
    system = "You QA runbooks: find gaps, suggest concrete commands, tailor to environment. JSON only."
    parsed = _groq_json(system, json.dumps(ctx, indent=2), timeout=16.0)
    if parsed:
        parsed["source"] = "llm"
        return parsed
    return _stub(
        "deterministic_fallback",
        "runbook_qa",
        {
            "gaps": ["Add rollback section", "Add verification checks"],
            "suggested_commands": ["kubectl get pods -A", "systemctl status <unit>", "curl -sSf localhost/health"],
            "tailored_steps": ["Fill in service names from environment_hints"],
        },
    )


def rank_root_cause_hypotheses(
    metrics: Dict[str, Any],
    logs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    ctx = {
        "metrics": metrics,
        "recent_healing_logs": logs[:10],
        "output_schema": {
            "hypotheses": [
                {"cause": "string", "confidence": "0-100", "evidence": []},
            ],
        },
    }
    system = "You produce multiple ranked root-cause hypotheses with evidence. JSON only."
    parsed = _groq_json(system, json.dumps(ctx, indent=2))
    if parsed and parsed.get("hypotheses"):
        parsed["source"] = "llm"
        return parsed
    base = _fallback_rca(metrics)
    return _stub(
        "deterministic_fallback",
        "hypotheses",
        {
            "hypotheses": [
                {"cause": base["likely_cause"], "confidence": base["confidence"], "evidence": base["reasons"]},
                {"cause": "Transient load spike", "confidence": 35.0, "evidence": ["IsolationForest anomaly without sustained trend in logs"]},
                {"cause": "Misconfigured autoscaling", "confidence": 25.0, "evidence": ["Requires external confirmation"]},
            ],
        },
    )


def proactive_risk_narrative(
    services: Optional[List[Dict[str, Any]]],
    logs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    ctx = {
        "services_metrics": services or [],
        "recent_incident_logs": logs[:15],
        "output_schema": {
            "top_risks": [{"service": "string", "risk": "string", "evidence": "string"}],
            "suggested_checks": [],
            "executive_summary": "string",
        },
    }
    system = "You write a concise proactive risk narrative for ops leadership. JSON only."
    parsed = _groq_json(system, json.dumps(ctx, indent=2), timeout=16.0)
    if parsed:
        parsed["source"] = "llm"
        return parsed
    risks = []
    for row in logs[:5]:
        risks.append({
            "service": "from_logs",
            "risk": str(row.get("anomaly_type", "unknown")),
            "evidence": str(row.get("healing_action", "")),
        })
    if not risks:
        risks = [{"service": "cluster", "risk": "No recent incidents in log window", "evidence": "empty"}]
    return _stub(
        "deterministic_fallback",
        "narrative",
        {
            "top_risks": risks,
            "suggested_checks": ["Review error budgets", "Scan for memory growth trends"],
            "executive_summary": "Limited history; enable LLM for richer narrative.",
        },
    )


def unstructured_logs_to_signals(log_lines: List[str]) -> Dict[str, Any]:
    ctx = {
        "raw_log_lines": log_lines[:40],
        "output_schema": {
            "signals": [
                {"name": "string", "value": "string or number", "severity": "info|warn|error"},
            ],
        },
    }
    system = "Extract structured signals suitable for anomaly features from unstructured logs. JSON only."
    parsed = _groq_json(system, json.dumps(ctx, indent=2))
    if parsed:
        parsed["source"] = "llm"
        return parsed
    signals = []
    for i, line in enumerate(log_lines[:10]):
        low = line.lower()
        sev = "info"
        if "error" in low or "fail" in low:
            sev = "error"
        elif "warn" in low:
            sev = "warn"
        signals.append({"name": f"log_line_{i}", "value": line[:200], "severity": sev})
    return _stub("deterministic_fallback", "log_signals", {"signals": signals})


def security_context_check(
    text: str,
    check_type: str = "generic",
) -> Dict[str, Any]:
    check_type = (check_type or "generic").lower()
    ctx = {
        "content": text[:8000],
        "check_type": check_type,
        "output_schema": {
            "flags": [],
            "risk_summary": "string",
            "recommendation": "string",
        },
    }
    system = (
        "You are a security analyst. For check_type phishing|auth|generic, assess risk. "
        "JSON only."
    )
    parsed = _groq_json(system, json.dumps(ctx, indent=2), temperature=0.15)
    if parsed:
        parsed["source"] = "llm"
        return parsed
    return _stub(
        "deterministic_fallback",
        "security",
        {
            "flags": ["manual_review_required"],
            "risk_summary": "LLM unavailable; no automated security classification.",
            "recommendation": "Route to SOC or use dedicated email security pipeline.",
        },
    )
