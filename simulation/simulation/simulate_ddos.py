import time
import random
import requests

# --- Config ---
BACKEND_URL = "http://localhost:8000/decide"   # Replace with Sanchit's FastAPI endpoint
LOG_FILE = "simulation.log"

def log_event(message: str):
    """Append events to a log file for Om's dashboard."""
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
    print(message)

def generate_ddos_metrics():
    """Simulate CPU + Network spikes (DDoS scenario)."""
    cpu_usage = random.randint(85, 100)        # High CPU
    network_traffic = random.randint(200, 500) # High network traffic
    memory_usage = random.randint(40, 70)      # Normal memory
    return {
        "cpu_usage": cpu_usage,
        "network_traffic": network_traffic,
        "memory_usage": memory_usage
    }

def format_prometheus(metrics: dict):
    """Format metrics in Prometheus-style key=value pairs."""
    return "\n".join([f"{k}={v}" for k, v in metrics.items()])

def act_layer(metrics: dict):
    """Send metrics to backend and act on decision."""
    try:
        response = requests.post(BACKEND_URL, json=metrics)
        decision = response.json().get("action", "None")

        if decision == "Restart":
            log_event("Backend decision: Restart → Simulating process kill...")
        elif decision == "Throttle":
            log_event("Backend decision: Throttle → Simulating traffic shaping...")
        else:
            log_event("Backend decision: No action taken.")
    except Exception as e:
        log_event(f"Error contacting backend: {e}")

def main():
    log_event("Starting DDoS simulation...")
    while True:
        metrics = generate_ddos_metrics()
        prometheus_output = format_prometheus(metrics)
        log_event(f"Metrics:\n{prometheus_output}")
        act_layer(metrics)
        time.sleep(2)  # simulate near-real-time feed

if __name__ == "__main__":
    main()
