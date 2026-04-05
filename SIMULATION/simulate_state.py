import time
import random
import requests
import sys
import io

# Fix Windows Unicode issue with arrow characters in terminal
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# --- Config ---
BACKEND_URL = "http://127.0.0.1:8000/metrics/ingest"
LOG_FILE = "simulation_state.log"

# How long each state runs before switching (seconds)
STATE_DURATION = 15

def log_event(message: str):
    """Append events to a log file and print to terminal."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
    print(message)

# --- Metric Generators (mirroring simulate_ddos.py pattern) ---

def generate_normal_metrics() -> dict:
    """State 0: Healthy baseline — low CPU, normal network, normal memory."""
    return {
        "cpu":     round(random.uniform(10, 40), 2),
        "memory":  round(random.uniform(30, 55), 2),
        "network": round(random.uniform(50, 200), 2),
        "dry_run": False,
    }

def generate_ddos_metrics() -> dict:
    """State 1: DDoS attack — elevated CPU, massive network spike, normal memory."""
    return {
        "cpu":     round(random.uniform(40, 70), 2),
        "memory":  round(random.uniform(35, 60), 2),
        "network": round(random.uniform(1000, 5000), 2),
        "dry_run": False,
    }

def generate_cpu_stress_metrics() -> dict:
    """State 2: CPU stress / internal overload — maxed CPU, normal network."""
    return {
        "cpu":     round(random.uniform(80, 100), 2),
        "memory":  round(random.uniform(50, 75), 2),
        "network": round(random.uniform(100, 300), 2),
        "dry_run": False,
    }

# --- State map ---
STATES = {
    0: ("Normal",     generate_normal_metrics),
    1: ("DDoS",       generate_ddos_metrics),
    2: ("CPU Stress", generate_cpu_stress_metrics),
}

def format_prometheus(metrics: dict) -> str:
    """Format metrics in Prometheus-style key=value pairs for logging."""
    return " | ".join([f"{k}={v}" for k, v in metrics.items()])

def act_layer(metrics: dict):
    """Send metrics to backend and log the healing decision."""
    try:
        response = requests.post(BACKEND_URL, json=metrics, timeout=5)
        response.raise_for_status()
        payload = response.json()
        decision = payload.get("healing_action", "no_action")
        status   = payload.get("status", "unknown")
        conf     = payload.get("confidence", 0)

        if decision == "restart_service":
            log_event(f"  Backend [{conf}%] -> Restart: Simulating process kill...")
        elif decision == "throttle_traffic":
            log_event(f"  Backend [{conf}%] -> Throttle: Simulating traffic shaping...")
        elif decision == "rolling_restart":
            log_event(f"  Backend [{conf}%] -> Rolling restart: Simulating rolling restart...")
        elif decision == "scale_up_resources":
            log_event(f"  Backend [{conf}%] -> Scale up: Simulating resource scale-up...")
        else:
            log_event(f"  Backend [{conf}%] -> Status: {status}. No action taken.")
    except Exception as e:
        log_event(f"  Error contacting backend: {e}")

def main():
    log_event("=" * 60)
    log_event("AutoHeal State Simulator started.")
    log_event(f"Cycling states every {STATE_DURATION}s | Backend: {BACKEND_URL}")
    log_event("=" * 60)

    state_index = 0  # Start from Normal

    while True:
        state_name, metric_fn = STATES[state_index]

        log_event(f"\n[STATE {state_index}] Entering: {state_name}")

        # Run this state for STATE_DURATION seconds, sending every 2s
        elapsed = 0
        while elapsed < STATE_DURATION:
            metrics = metric_fn()
            log_event(f"  Metrics: {format_prometheus(metrics)}")
            act_layer(metrics)
            time.sleep(2)
            elapsed += 2

        # Cycle to next state (0 -> 1 -> 2 -> 0 -> ...)
        state_index = (state_index + 1) % len(STATES)

if __name__ == "__main__":
    main()