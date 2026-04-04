import time
import requests

# --- Config ---
BACKEND_URL = "http://localhost:8000/decide"   # Replace with your FastAPI endpoint
LOG_FILE = "rate_limit.log"

# --- Rate Limit Settings ---
MAX_REQUESTS = 5       # allowed requests
WINDOW_SECONDS = 10    # time window in seconds

# --- State ---
request_times = []

def log_event(message: str):
    """Append events to a log file for observability."""
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
    print(message)

def allow_request() -> bool:
    """Check if a new request is allowed under rate limiting."""
    global request_times
    now = time.time()

    # Remove timestamps outside the window
    request_times = [t for t in request_times if now - t < WINDOW_SECONDS]

    if len(request_times) < MAX_REQUESTS:
        request_times.append(now)
        return True
    else:
        return False

def simulate_requests():
    """Simulate sending requests with rate limiting applied."""
    for i in range(15):  # simulate 15 attempts
        if allow_request():
            try:
                response = requests.get(BACKEND_URL)
                log_event(f"Request {i+1}: Allowed → {response.status_code}")
            except Exception as e:
                log_event(f"Request {i+1}: Error → {e}")
        else:
            log_event(f"Request {i+1}: Blocked (rate limit exceeded)")
        time.sleep(1)  # wait 1 second between attempts

if __name__ == "__main__":
    simulate_requests()
