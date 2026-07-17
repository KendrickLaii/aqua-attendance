"""Payroll status transition rules."""

from app.models.payroll_record import PayrollStatus

# Allowed next statuses from each current status.
ALLOWED_PAYROLL_TRANSITIONS: dict[str, set[str]] = {
    PayrollStatus.draft.value: {
        PayrollStatus.calculated.value,
        PayrollStatus.approved.value,
        PayrollStatus.cancelled.value,
    },
    PayrollStatus.calculated.value: {
        PayrollStatus.approved.value,
        PayrollStatus.cancelled.value,
    },
    PayrollStatus.approved.value: {
        PayrollStatus.paid.value,
        PayrollStatus.cancelled.value,
    },
    PayrollStatus.paid.value: set(),
    PayrollStatus.cancelled.value: set(),
}


def can_transition_payroll_status(current: str, new_status: str) -> bool:
    if current == new_status:
        return True
    return new_status in ALLOWED_PAYROLL_TRANSITIONS.get(current, set())
