"""
Типы и константы для Autopilot Ramp-up.
Отдельный модуль — доп. функция умной раскатки по ступеням трафика.
"""

from typing import Any

DATA_SUFFICIENCY_KEYS = (
    "min_total_impressions",
    "min_impressions_per_variant",
    "min_minutes_on_step",
)

GATE_SAFETY_KEYS = (
    "use_guardrails",
    "error_rate_threshold",
    "latency_p95_ms",
)

GATE_DATA_HEALTH_KEYS = (
    "require_no_srm",
    "require_no_mass_rejected",
)

SAFETY_TRIGGER_TYPES = (
    "guardrail_triggered",
    "error_rate_high",
    "latency_high",
    "data_quality_critical",
)

SAFETY_ACTIONS = ("pause", "rollback_to_control", "step_back")

RAMP_MODES = ("autopilot", "manual", "paused")

DECISION_ACTIONS = (
    "start",
    "resume",
    "step_up",
    "step_back",
    "pause",
    "rollback",
    "override",
    "no_change",
)


def gate_data_sufficiency_defaults() -> dict[str, Any]:
    return {
        "min_total_impressions": 1000,
        "min_impressions_per_variant": 200,
        "min_minutes_on_step": 60,
    }


def gate_safety_defaults() -> dict[str, Any]:
    return {
        "use_guardrails": True,
        "error_rate_threshold": 0.01,
        "latency_p95_ms": 500,
    }


def gate_data_health_defaults() -> dict[str, Any]:
    return {
        "require_no_srm": True,
        "require_no_mass_rejected": True,
    }
