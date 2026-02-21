"""
Autopilot Ramp-up — умная автопилот-раскатка по ступеням трафика.

Доп. функция: план раскатки (ramp_plan) с gates и safety actions,
состояние (experiment_ramp_state), лог решений (experiment_ramp_decision_log).
Логика оценки и шагов описана в LOGIC.md.
"""

from autopilot_ramp.ramp_plan import (
    create_or_update_ramp_plan,
    delete_ramp_plan,
    get_ramp_plan_by_experiment_id,
)
from autopilot_ramp.ramp_state import (
    get_ramp_decision_log,
    get_ramp_state,
    log_autopilot_decision,
    override_step,
    set_ramp_mode,
    start_autopilot,
)
from autopilot_ramp.types import (
    DECISION_ACTIONS,
    RAMP_MODES,
    SAFETY_ACTIONS,
    SAFETY_TRIGGER_TYPES,
    gate_data_health_defaults,
    gate_data_sufficiency_defaults,
    gate_safety_defaults,
)

__all__ = [
    "create_or_update_ramp_plan",
    "get_ramp_plan_by_experiment_id",
    "delete_ramp_plan",
    "get_ramp_state",
    "start_autopilot",
    "set_ramp_mode",
    "override_step",
    "log_autopilot_decision",
    "get_ramp_decision_log",
    "SAFETY_ACTIONS",
    "SAFETY_TRIGGER_TYPES",
    "RAMP_MODES",
    "DECISION_ACTIONS",
    "gate_data_sufficiency_defaults",
    "gate_safety_defaults",
    "gate_data_health_defaults",
]
