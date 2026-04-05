# AutoHeal — Digital Immune System

> **TESSERACT '26 | AI/ML Track — Problem Statement 2**
> *Autonomous IT: Rethinking the Future of Self-Managing Systems*

---

## Team OutLawz

| Name | Role |
|------|------|
| Sanchit Pimpalkar | Backend & AI/ML |
| Ved Rokde | DevOps & Simulation |
| Om Salunke | Frontend & UI/UX |
| Ruturaj Raut | Integration & Presenter |

---

## Problem Statement

Large-scale IT environments are too complex for human response times. When thousands of microservices run simultaneously, a single cascading failure can bring down entire systems before any engineer can react. Traditional monitoring tools only *notify* — they don't *act*.

**The cost of human delay is measured in downtime, data loss, and revenue.**

---

## Solution

AutoHeal is a **Digital Immune System** for IT infrastructure. It continuously monitors system metrics at near-zero latency, detects anomalies using a dual-model AI engine, understands *why* a failure occurred using Causal Inference, and autonomously executes the correct healing action — all in under a second.

It moves beyond reactive automation into **Agentic Reasoning**: the system doesn't just restart — it diagnoses.

---

## Key Features

- **Sub-second Anomaly Detection** — IsolationForest + Z-score ensemble detects deviations before they become failures
- **Causal Inference Engine** — Distinguishes between a DDoS attack and a natural traffic spike using multi-signal reasoning
- **Confidence Guardrails** — Actions only execute when AI confidence exceeds the configured threshold (default: 85%)
- **Dry-Run Mode** — Human operators can verify decisions before enabling full autonomy
- **Predictive Forecasting** — Linear and exponential trend models predict threshold crossings before they happen
- **LLM-Powered Insights** — Groq-backed root cause analysis, postmortem drafts, runbook QA, and incident summaries
- **Live Audit Trail** — Every detection, decision, and action is logged with full explainability
- **Real-Time Dashboard** — Live metrics, healing events, and confidence scores visualized as they happen

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AUTOHEAL SYSTEM                         │
│                                                             │
│  ┌──────────────┐    ┌──────────────────────────────────┐  │
│  │  Simulator   │───▶│         FastAPI Backend           │  │
│  │  (eBPF sim)  │    │                                  │  │
│  └──────────────┘    │  ┌────────────┐ ┌─────────────┐ │  │
│                       │  │  Anomaly   │ │  Forecaster │ │  │
│  Scenarios:           │  │  Engine    │ │  (predict)  │ │  │
│  • Normal             │  │  IF+Zscore │ │  Lin / Exp  │ │  │
│  • DDoS Attack        │  └─────┬──────┘ └─────────────┘ │  │
│  • Memory Leak        │        │                         │  │
│  • Service Crash      │  ┌─────▼──────┐ ┌─────────────┐ │  │
│                       │  │  Causal    │ │  LLM Layer  │ │  │
│                       │  │  Healer    │ │  (Groq/     │ │  │
│                       │  │  Engine    │ │  Fallback)  │ │  │
│                       │  └─────┬──────┘ └─────────────┘ │  │
│                       │        │                         │  │
│                       │  ┌─────▼──────┐                 │  │
│                       │  │  SQLite    │                 │  │
│                       │  │  Audit Log │                 │  │
│                       │  └────────────┘                 │  │
│                       └──────────────────────────────────┘  │
│                                  │                           │
│                       ┌──────────▼──────────┐               │
│                       │   HTML Dashboard    │               │
│                       │  (served via nginx) │               │
│                       └─────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

---

## How the AI Works — Observe → Orient → Decide → Act

### Step 1: Observe
eBPF-inspired metric sensors emit CPU, memory, and network readings every second.

### Step 2: Orient — Dual Anomaly Detection
```
Signal 1: IsolationForest
  Trained on healthy baseline → scores deviation from normal
  
Signal 2: Z-Score Ensemble  
  Computes standard deviations from baseline mean
  
Combined: OR logic on flags, MAX on confidence scores
```

### Step 3: Decide — Causal Rule Engine
```
CPU > 75% + Network > 80  →  DDoS Pattern      →  Throttle Traffic
CPU > 75% + Network ≤ 80  →  Internal Overload  →  Rolling Restart
Memory > 80%              →  Memory Leak        →  Scale Up
CPU < 10% + Network < 10  →  Service Down       →  Restart Service
```
*Actions only fire if confidence ≥ configured threshold (default 85%)*

### Step 4: Act
Healing action executes, is logged to the audit trail, and the dashboard updates in real-time.

---

## LLM Insights Layer

When Groq is configured, AutoHeal gains 16 AI-powered endpoints:

| Endpoint | Purpose |
|----------|---------|
| `/insights/explain` | Root cause analysis with remediation hints |
| `/insights/playbook` | Step-by-step runbooks for Kubernetes / systemd / AWS |
| `/insights/safety-check` | Risk assessment before executing an action |
| `/insights/summarize` | Incident summary + Slack-ready message |
| `/insights/postmortem` | Blameless postmortem draft from healing logs |
| `/insights/hypotheses` | Multiple ranked root-cause hypotheses |
| `/insights/triage` | Alert deduplication and prioritization |
| `/insights/query` | Natural language questions over live telemetry |
| `/insights/canary` | Pre/post deploy comparison — hold/rollback/proceed |
| `/insights/slo` | SLO breach narrative and capacity suggestions |

> All endpoints fall back to deterministic logic if LLM is unavailable — the system never crashes without Groq.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **AI / Anomaly** | scikit-learn (IsolationForest), NumPy |
| **Forecasting** | NumPy (linear + exponential trend models, R² selection) |
| **LLM** | Groq API — `llama-3.3-70b-versatile` with key rotation |
| **Database** | SQLite via aiosqlite (async) |
| **Frontend** | HTML5, CSS3, JavaScript, Chart.js |
| **Web Server** | Nginx (Docker) |
| **Containerization** | Docker, Docker Compose |
| **Simulation** | Python (requests, random, time) |

---

## Getting Started

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- (Optional) Groq API key for LLM features

---

### Option A — Run with Docker (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/outlawz/autoheal.git
cd autoheal

# 2. Set up environment variables
cp .env.example .env
# Edit .env and add your GROQ_API_KEY_1 if you have one

# 3. Create assets folder
mkdir -p assets
# Place chart_umd_min.js and favicon.ico inside /assets

# 4. Start everything with one command
docker-compose up --build

# Backend:   http://localhost:8000
# Dashboard: http://localhost:8080
# API Docs:  http://localhost:8000/docs
```

---

### Option B — Run Locally

```bash
# 1. Set up backend
cd backend
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Mac/Linux)
source venv/bin/activate

pip install -r requirements.txt

# 2. Set environment variables
cp .env.example .env
# Add GROQ_API_KEY_1=your_key_here to .env

# 3. Start the backend
uvicorn main:app --reload --port 8000

# 4. Open the dashboard
# Open Webpage.html in your browser
# OR serve it: python -m http.server 8080
```

---

## Running Failure Simulations

Open a new terminal with the virtual environment activated:

```bash
cd simulator

# Normal healthy traffic (establishes baseline)
python simulate_normal.py

# Simulate a DDoS Attack (CPU + Network spike)
python simulate_ddos.py

# Simulate a Memory Leak (Memory slowly climbs)
python simulate_leak.py

# Simulate rate limiting behavior
python simulate_rate_limit.py
```

Watch the dashboard at `http://localhost:8080` — the system will detect, decide, and heal in real-time.

---

## Configuration

All settings are controlled via environment variables in `.env`:

```env
# Groq LLM (optional but recommended)
GROQ_API_KEY_1=gsk_your_key_here
GROQ_API_KEY_2=gsk_backup_key   # Optional: rotated on rate limit

# Anomaly Detection Sensitivity
ANOMALY_CONTAMINATION=0.08       # IsolationForest contamination ratio
ANOMALY_ZSIGMA=2.2               # Z-score threshold for flagging

# Healing Confidence Guardrail
HEALING_MIN_CONFIDENCE=85        # Minimum % confidence to trigger action

# Forecasting
FORECAST_CPU_THRESHOLD=80        # CPU% to forecast toward
FORECAST_MEMORY_THRESHOLD=80     # Memory% to forecast toward
FORECAST_NETWORK_THRESHOLD=400   # Network Mbps to forecast toward
FORECAST_HORIZON_SECONDS=300     # 5-minute lookahead window

# Safety
ADMIN_ENABLE_CRASH=0             # Set to 1 only for testing crash recovery
```

---

## API Reference

### Core Endpoints

```
POST /metrics/ingest     Push metric snapshot, get anomaly + healing decision
GET  /metrics/latest     Current metric values
GET  /metrics/forecast   Trend forecasts and risk levels for all metrics
GET  /healinglog         Last 20 healing events with full audit trail
GET  /                   Health check
GET  /docs               Interactive Swagger API documentation
```

### Example: Ingest Metrics
```bash
curl -X POST http://localhost:8000/metrics/ingest \
  -H "Content-Type: application/json" \
  -d '{"cpu": 92, "memory": 55, "network": 450, "dry_run": false}'
```

**Response:**
```json
{
  "cpu": 92.0,
  "memory": 55.0,
  "network": 450.0,
  "is_anomaly": true,
  "confidence": 94.5,
  "healing_action": "throttle_traffic",
  "anomaly_type": "DDoS_Pattern",
  "status": "healing",
  "forecast": {
    "cpu": { "risk": "high", "eta_seconds_to_threshold": 42.3 },
    "memory": { "risk": "none", "eta_seconds_to_threshold": null },
    "network": { "risk": "high", "eta_seconds_to_threshold": 18.7 }
  },
  "proactive_action": null,
  "llm_analysis": {
    "reasons": ["High CPU with high network throughput suggests external traffic surge."],
    "likely_cause": "DDoS_Pattern",
    "confidence": 85,
    "remediation_suggestions": ["Throttle traffic", "Enable WAF rules", "Rate limit"]
  }
}
```

---

## Dashboard Features

- **System Status Banner** — Live green / red / blue indicator that shifts during healing
- **Live Metric Charts** — Rolling 30-point line charts for CPU, Memory, Network
- **Confidence Score Gauge** — Circular dial showing AI certainty in real-time
- **Healing Audit Log** — Color-coded feed of every detected anomaly and action taken
- **Dry-Run Toggle** — Switch between full autonomy and human-verification mode
- **Anomaly Type Badge** — DDoS / Memory Leak / Internal Overload / Service Down labels
- **Forecast Risk Indicators** — Shows proactive risk level before threshold is hit

---

## Project Structure

```
autoheal/
│
├── backend/
│   ├── main.py                 ← FastAPI app, CORS, startup
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── db/
│   │   └── database.py         ← SQLite init, insert, query
│   ├── engine/
│   │   ├── anomaly.py          ← IsolationForest + Z-score detection
│   │   ├── healer.py           ← Causal rule engine
│   │   ├── predict.py          ← Trend forecasting module
│   │   └── llm.py              ← Groq LLM with key rotation + fallbacks
│   └── routes/
│       ├── metrics.py          ← /metrics/* endpoints
│       ├── healing.py          ← /healinglog endpoint
│       ├── insights.py         ← /insights/* LLM endpoints
│       └── admin.py            ← /admin/* (disabled by default)
│
├── simulator/
│   ├── simulate_ddos.py        ← DDoS scenario (CPU + Network spike)
│   ├── simulate_leak.py        ← Memory leak scenario
│   ├── simulate_rate_limit.py  ← Rate limiting demonstration
│   └── requirements.txt
│
├── assets/
│   ├── chart_umd_min.js        ← Chart.js (offline)
│   └── favicon.ico
│
├── Webpage.html                ← Live dashboard (served via nginx)
├── docker-compose.yml          ← Runs backend + frontend together
├── .env.example                ← Environment variable template
└── README.md
```

---

## Safety Features

**Confidence Guardrail** — No action executes unless the AI's combined confidence score exceeds the threshold. Prevents false-positive healing loops ("Automated Chaos").

**Dry-Run Mode** — Set `dry_run: true` in any metric payload. The system detects and logs anomalies but does not execute healing actions. Allows human operators to audit AI decisions before enabling full autonomy.

**LLM Safety Check** — The `/insights/safety-check` endpoint evaluates a proposed healing action for blast radius and risk before it runs.

**Audit Trail** — Every action is permanently logged with timestamp, metric snapshot, anomaly type, healing action, confidence score, and dry-run status.

---

## Impact

| Metric | Target |
|--------|--------|
| **Uptime** | 98.99% — eliminates human response delay |
| **Detection Speed** | Sub-second anomaly identification |
| **Cloud Cost Reduction** | Up to 30% via autonomous resource de-allocation |
| **Alert Fatigue** | Eliminated — system acts, engineers innovate |
| **Security** | Instant quarantine of anomalous traffic patterns |

---

## References

- CNCF (2025) — *Autonomous Infrastructure: Transitioning from Intent to Self-Operating Cloud Systems*
- IJRTI (2025) — *Causal Inference AI Models for Root Cause Analysis in DevOps*
- eunomia.dev (2025) — *eBPF Ecosystem Progress: A Technical Deep Dive into Zero-Overhead Monitoring*
- ArXiv (2024) — *AIOps Solutions for Incident Management: A Comprehensive Literature Review*
- Google SRE (2024) — *The Site Reliability Engineering Handbook: Automation and Distributed Systems*
- IJSRM (2024) — *Agentic AI in Predictive AIOps: Enhancing IT Autonomy*

---
## Team Details
### Team Name: OutLawz
Members:
|Name |
|------|
|Sanchit Pimpalkar|
|Ved Rokde|
|Om Salunke|
|Ruturaj Raut|

