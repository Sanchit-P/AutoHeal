import os
import json
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv  # type: ignore

# Optional imports; handled gracefully if missing during cold start
try:
    from groq import Groq  # type: ignore
except Exception:
    Groq = None  # type: ignore

# Key rotation (compatible with your Flask snippet)
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

# Deterministic fallback leveraging your current healing logic
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
    }

def _build_prompt(metrics: Dict[str, Any], logs: List[Dict[str, Any]]) -> str:
    context = {
        "metrics": metrics,
        "recent_healing_logs": logs[:10],
        "instructions": [
            "You are a Senior SRE.",
            "Explain the likely root cause of the current server failure/anomaly.",
            "Use only the provided metrics and recent healing logs.",
            "Return strict JSON only with: reasons[], likely_cause, confidence(0-100), remediation_suggestions[]."
        ],
    }
    return json.dumps(context, indent=2)

# Main entry point used by FastAPI route
def suggest_root_cause(
    metrics: Dict[str, Any],
    logs: Optional[List[Dict[str, Any]]] = None,
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.2,
    timeout: float = 6.0,
    max_attempts: Optional[int] = None,
) -> Dict[str, Any]:
    if Groq is None:
        return {
            "reasons": ["Groq SDK not installed."],
            "likely_cause": "LLMUnavailable",
            "confidence": 0,
            "remediation_suggestions": ["pip install groq"]
        }

    if not _API_KEYS:
        return {
            "reasons": ["Missing GROQ_API_KEY_* environment variables."],
            "likely_cause": "ConfigurationError",
            "confidence": 0,
            "remediation_suggestions": ["Set GROQ_API_KEY_1, GROQ_API_KEY_2, ..."]
        }

    prompt = _build_prompt(metrics, logs or [])
    attempts = max_attempts or len(_API_KEYS)

    for _ in range(attempts):
        try:
            client = _key_manager.get_client()
            resp = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": "You are a precise SRE assistant. Respond only in valid JSON."},
                    {"role": "user", "content": f"Analyze and output strict JSON only:\n{prompt}"},
                ],
                response_format={"type": "json_object"},
                timeout=timeout,
            )
            content = resp.choices[0].message.content or "{}"
            parsed = json.loads(content)
            return {
                "reasons": parsed.get("reasons", []),
                "likely_cause": parsed.get("likely_cause", "Unknown"),
                "confidence": parsed.get("confidence", 50),
                "remediation_suggestions": parsed.get("remediation_suggestions", []),
            }
        except Exception as e:
            em = str(e).lower()
            if "429" in em or "rate" in em:
                print(f"Key {_key_manager.current_index} rate-limited. Rotating...")
                _key_manager.rotate()
                continue
            print(f"LLM error: {e}. Falling back to deterministic RCA.")
            break

    return _fallback_rca(metrics)