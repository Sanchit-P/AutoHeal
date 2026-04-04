# Causal Logic:
# High CPU + High Network  → DDoS Pattern  → Throttle Traffic
# High CPU + Normal Network → Internal Bug → Rolling Restart
# High Memory + Any        → Memory Leak   → Scale Up / Pod Restart
# Low CPU + Low Network    → Service Down  → Restart Service

def determine_healing(cpu: float, memory: float, network: float, confidence: float):
    action = "no_action"
    anomaly_type = "none"
    
    if confidence < 95:
        return action, anomaly_type  # Confidence guardrail
    
    if cpu > 75 and network > 80:
        action = "throttle_traffic"
        anomaly_type = "DDoS_Pattern"
    elif cpu > 75 and network <= 80:
        action = "rolling_restart"
        anomaly_type = "Internal_Overload"
    elif memory > 80:
        action = "scale_up_resources"
        anomaly_type = "Memory_Leak"
    elif cpu < 10 and network < 10:
        action = "restart_service"
        anomaly_type = "Service_Down"
    
    return action, anomaly_type