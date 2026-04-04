import time
import requests
import random

# --- Config ---
BACKEND_URL = "http://127.0.0.1:8000/metrics/ingest"
LOG_FILE = "rate_limit.log"

# --- Rate Limit Settings (client-side throttle to demonstrate both allowed and blocked) ---
MAX_REQUESTS = 5        # allowed client sends within window
WINDOW_SECONDS = 10     # time window in seconds

# --- State ---
request_times = []

def log_event(message: str):
    """Append events to a log file for observability."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
    print(message)

def allow_request() -> bool:
    """Client-side throttle: Check if a new request is allowed under our window."""
    global request_times
    now = time.time()
    # Remove timestamps outside the window
    request_times = [t for t in request_times if now - t < WINDOW_SECONDS]
    if len(request_times) < MAX_REQUESTS:
        request_times.append(now)
        return True
    return False

def sample_payload():
    # Mildly varying metrics
    return {
        "cpu": random.randint(40, 75),
        "memory": random.randint(40, 75),
        "network": random.randint(100, 250),
        "dry_run": True,
    }

def simulate_requests(total_attempts: int = 20, interval_seconds: float = 1.0):
    """Simulate bursty requests to demonstrate 200 vs 429 behavior."""
    for i in range(total_attempts):
        try:
            if allow_request():
                resp = requests.post(BACKEND_URL, json=sample_payload(), timeout=4)
                if resp.status_code == 429:
                    log_event(f"Request {i+1}: Server rate-limited (429)")
                else:
                    log_event(f"Request {i+1}: Allowed → {resp.status_code}")
            else:
                log_event(f"Request {i+1}: Blocked locally (client window exceeded)")
        except Exception as e:
            log_event(f"Request {i+1}: Error → {e}")
        time.sleep(interval_seconds)

if __name__ == "__main__":
    log_event("Starting rate-limit simulation against /metrics/ingest ...")
    simulate_requests()