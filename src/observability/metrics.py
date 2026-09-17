from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

REGISTRY = CollectorRegistry()

http_errors_total = Counter(
    "changeguard_http_errors_total",
    "Total unhandled/HTTP error responses",
    ["status_code"],
    registry=REGISTRY,
)

evaluation_duration_seconds = Histogram(
    "changeguard_evaluation_duration_seconds",
    "Duration of the full change evaluation pipeline",
    registry=REGISTRY,
)

decisions_total = Counter(
    "changeguard_decisions_total",
    "Routing decisions issued",
    ["decision"],
    registry=REGISTRY,
)

risk_levels_total = Counter(
    "changeguard_risk_levels_total",
    "Deterministic risk levels assigned",
    ["level"],
    registry=REGISTRY,
)

gate_failures_total = Counter(
    "changeguard_gate_failures_total",
    "AI assurance gate failures by gate",
    ["gate"],
    registry=REGISTRY,
)

ai_provider_failures_total = Counter(
    "changeguard_ai_provider_failures_total",
    "AI provider failures/fallbacks",
    ["provider", "reason"],
    registry=REGISTRY,
)

cab_queue_size = Gauge(
    "changeguard_cab_queue_size",
    "Current number of tickets awaiting CAB decision",
    registry=REGISTRY,
)


def render_latest() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
