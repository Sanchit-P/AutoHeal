import time
import random
import requests

# --- Config ---
BACKEND_URL = "http://127.0.0.1:8000/metrics/ingest"
LOG_FILE = "simulation_leak.log"

def log_event(message: str):
    """Append events to a log file for Om's dashboard."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
    print(message)

def generate_leak_metrics():
    """Simulate CPU + Memory spikes (Leak scenario)."""
    cpu_usage = random.randint(85, 100)        # High CPU
    memory_usage = random.randint(80, 100)     # High memory (leak)
    network_traffic = random.randint(30, 80)   # Normal network
    return {
        "cpu": cpu_usage,
        "network": network_traffic,
        "memory": memory_usage,
        "dry_run": True,
    }

def format_prometheus(metrics: dict):
    """Format metrics in Prometheus-style key=value pairs."""
    return "\n".join([f"{k}={v}" for k, v in metrics.items()])

def act_layer(metrics: dict):
    """Send metrics to backend and act on decision."""
    try:
        response = requests.post(BACKEND_URL, json=metrics, timeout=5)
        response.raise_for_status()
        payload = response.json()
        decision = payload.get("healing_action", "no_action")
        status = payload.get("status", "unknown")

        if decision == "restart_service":
            log_event("Backend decision: Restart → Simulating process kill...")
        elif decision == "throttle_traffic":
            log_event("Backend decision: Throttle → Simulating traffic shaping...")
        elif decision == "rolling_restart":
            log_event("Backend decision: Rolling restart → Simulating rolling restart...")
        elif decision == "scale_up_resources":
            log_event("Backend decision: Scale up → Simulating resource scale-up...")
        else:
            log_event(f"Backend status: {status}. No action taken.")
    except Exception as e:
        log_event(f"Error contacting backend: {e}")

def main():
    log_event("Starting Leak simulation...")
    while True:
        metrics = generate_leak_metrics()
        prometheus_output = format_prometheus(metrics)
        log_event(f"Metrics:\n{prometheus_output}")
        act_layer(metrics)
        time.sleep(2)

if __name__ == "__main__":
    main()