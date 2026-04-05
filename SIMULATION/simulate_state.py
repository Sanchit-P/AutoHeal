import time
import random
from prometheus_client import Gauge, start_http_server

# Define Prometheus metrics
state_metric = Gauge("system_state", "System state indicator (0=Normal,1=DDoS,2=CPU)")
cpu_usage = Gauge("cpu_usage_percent", "Simulated CPU usage percentage")
network_traffic = Gauge("network_traffic_mbps", "Simulated network traffic in Mbps")

def simulate_normal():
    state_metric.set(0)
    cpu_usage.set(random.uniform(10, 40))       # Normal CPU load
    network_traffic.set(random.uniform(50, 200)) # Normal traffic

def simulate_ddos():
    state_metric.set(1)
    cpu_usage.set(random.uniform(40, 70))       # Elevated CPU due to packet handling
    network_traffic.set(random.uniform(1000, 5000)) # Huge spike in traffic

def simulate_cpu_stress():
    state_metric.set(2)
    cpu_usage.set(random.uniform(80, 100))      # Maxed out CPU
    network_traffic.set(random.uniform(100, 300)) # Normal traffic

def main():
    start_http_server(8000)  # Prometheus scrapes metrics here
    states = [simulate_normal, simulate_ddos, simulate_cpu_stress]

    while True:
        # Cycle through states every 15 seconds
        state_fn = random.choice(states)
        state_fn()
        print("Updated metrics:", state_fn.__name__)
        time.sleep(15)

if __name__ == "__main__":
    main()
