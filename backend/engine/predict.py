from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple
import time
import numpy as np

_SLOPE_EPS = 1e-6  # treat absolute slopes below this as flat
_ETA_CAP_MULTIPLIER = 10.0  # cap ETA at 10x horizon in summarize

# Simple rolling history structure to store (timestamp_sec, value)
@dataclass
class MetricHistory:
    maxlen: int = 120  # keep ~4 minutes at 2s intervals, adjustable
    samples: Deque[Tuple[float, float]] = None  # (t, v)

    def __post_init__(self):
        if self.samples is None:
            self.samples = deque(maxlen=self.maxlen)

    def add(self, value: float, timestamp: Optional[float] = None) -> None:
        t = timestamp if timestamp is not None else time.time()
        self.samples.append((t, float(value)))

    def values(self) -> List[float]:
        return [v for _, v in self.samples]

    def times(self) -> List[float]:
        return [t for t, _ in self.samples]

    def has_enough_points(self, min_points: int = 6) -> bool:
        return len(self.samples) >= min_points


def _fit_linear_trend(times_s: List[float], values: List[float]) -> Tuple[float, float]:
    """
    Fit y = m*x + b using numpy.polyfit.
    Returns (slope_per_second, intercept).
    """
    if len(times_s) < 2:
        return 0.0, float(values[-1]) if values else 0.0
    x = np.array(times_s, dtype=float)
    y = np.array(values, dtype=float)
    # Shift time origin to improve numerical stability
    x0 = x[0]
    m, b = np.polyfit(x - x0, y, 1)
    # Convert intercept back to original time basis
    b = b - m * (-x0)
    return float(m), float(b)


def _fit_log_linear_trend(times_s: List[float], values: List[float]) -> Tuple[float, float]:
    """
    Fit ln(y) = a*x + c  ->  y = exp(a*x + c)
    Returns (a_per_second, c).
    Values are clamped to small epsilon to avoid log(0).
    """
    if len(times_s) < 2:
        return 0.0, float(np.log(max(values[-1], 1e-6))) if values else 0.0
    x = np.array(times_s, dtype=float)
    y = np.array(values, dtype=float)
    y = np.clip(y, 1e-6, None)
    x0 = x[0]
    a, c = np.polyfit(x - x0, np.log(y), 1)
    # Convert intercept back to original time basis
    c = c - a * (-x0)
    return float(a), float(c)


def _r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot == 0:
        return 1.0
    r2 = float(1 - ss_res / ss_tot)
    # Clamp to a sensible range to avoid confusing large negative numbers
    return max(-1.0, min(1.0, r2))


def _best_trend_model(times_s: List[float], values: List[float]) -> Dict[str, float | str]:
    """
    Fit linear and exponential (log-linear) models; return the one with better R^2.
    Output keys:
      - model_used: 'linear' | 'exponential'
      - slope_or_a_per_s
      - intercept_or_c
      - r2
    """
    x = np.array(times_s, dtype=float)
    y = np.array(values, dtype=float)
    # Linear fit
    m, b = _fit_linear_trend(times_s, values)
    y_lin = m * x + b
    r2_lin = _r2_score(y, y_lin)
    # Exponential fit
    a, c = _fit_log_linear_trend(times_s, values)
    y_exp = np.exp(a * x + c)
    r2_exp = _r2_score(y, y_exp)
    if r2_exp > r2_lin and a > 0:
        return {
            "model_used": "exponential",
            "slope_or_a_per_s": float(a),
            "intercept_or_c": float(c),
            "r2": float(round(r2_exp, 4)),
        }
    return {
        "model_used": "linear",
        "slope_or_a_per_s": float(m),
        "intercept_or_c": float(b),
        "r2": float(round(r2_lin, 4)),
    }


def forecast_time_to_threshold(
    times_s: List[float],
    values: List[float],
    threshold: float,
) -> Optional[float]:
    """
    Estimate seconds until the trend crosses the given threshold,
    using a stable local formulation at the latest timestamp.
    Returns None if slope is flat/negative or cannot compute.
    """
    if len(times_s) < 2:
        return None
    best = _best_trend_model(times_s, values)
    model = str(best["model_used"])
    t_last = float(times_s[-1])
    y_last = float(values[-1])
    if model == "exponential":
        a = float(best["slope_or_a_per_s"])
        if a <= _SLOPE_EPS:
            return None
        # y(t) ≈ y_last * exp(a * (t - t_last))
        # Solve y_last * exp(a * dt) = threshold  =>  dt = ln(threshold / y_last) / a
        if threshold <= 0 or y_last <= 0:
            return None
        dt = (np.log(threshold) - np.log(y_last)) / a
        t_cross = t_last + dt
    else:
        m = float(best["slope_or_a_per_s"])
        if m <= _SLOPE_EPS:
            return None
        # y(t) ≈ y_last + m * (t - t_last)
        # Solve y_last + m*dt = threshold  =>  dt = (threshold - y_last) / m
        dt = (threshold - y_last) / m
        t_cross = t_last + dt
    now_s = time.time()
    eta_s = t_cross - now_s
    if eta_s <= 0:
        return 0.0
    return float(eta_s)


def summarize_forecast(
    history: MetricHistory,
    threshold: float,
    horizon_s: float = 300.0,  # 5 minutes default horizon
) -> Dict[str, float | int | str | None]:
    """
    Provide a compact summary for a single metric:
      - slope_per_min (linear) or approx_growth_rate_per_min (exponential)
      - eta_seconds_to_threshold (None if not rising or no crossing)
      - risk: low/medium/high based on time-to-threshold within horizon
      - model_used and r2 for transparency
    """
    if not history.has_enough_points():
        return {
            "slope_per_min": 0.0,
            "eta_seconds_to_threshold": None,
            "risk": "insufficient_data",
            "model_used": "unknown",
            "r2": 0.0,
        }
    ts = history.times()
    vs = history.values()
    best = _best_trend_model(ts, vs)
    model = str(best["model_used"])
    r2 = float(best["r2"])

    if model == "exponential":
        a = float(best["slope_or_a_per_s"])
        # Report approximate instantaneous growth rate per minute at the latest time
        # rate_per_min ≈ a * y(t_latest) * 60
        t_last = ts[-1]
        y_last = vs[-1]
        approx_rate_per_min = a * max(y_last, 0.0) * 60.0
        if abs(approx_rate_per_min) < (_SLOPE_EPS * 60.0):
            approx_rate_per_min = 0.0
        approx_rate_per_min = float(round(max(0.0, approx_rate_per_min), 3))
        slope_key = "approx_growth_rate_per_min"
        slope_val = approx_rate_per_min
    else:
        m_per_s = float(best["slope_or_a_per_s"])
        slope_pm = m_per_s * 60.0
        if abs(slope_pm) < (_SLOPE_EPS * 60.0):
            slope_pm = 0.0
        slope_key = "slope_per_min"
        slope_val = float(round(slope_pm, 3))

    eta = forecast_time_to_threshold(ts, vs, threshold)
    # Cap unrealistic ETAs to reduce confusion; treat as no imminent risk
    if eta is not None:
        max_eta = _ETA_CAP_MULTIPLIER * horizon_s
        if eta > max_eta:
            eta = None

    risk = "none"
    if eta is None:
        risk = "none"
    elif eta <= horizon_s / 3:
        risk = "high"
    elif eta <= (2 * horizon_s) / 3:
        risk = "medium"
    elif eta <= horizon_s:
        risk = "low"
    else:
        risk = "none"

    out: Dict[str, float | int | str | None] = {
        "current_value": float(vs[-1]),
        "eta_seconds_to_threshold": None if eta is None else float(round(eta, 1)),
        "risk": risk,
        "model_used": model,
        "r2": r2,
    }
    out[slope_key] = slope_val
    return out

