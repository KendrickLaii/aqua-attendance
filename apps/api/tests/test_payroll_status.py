"""Payroll status transition rules."""

from app.services.payroll_status import can_transition_payroll_status


def test_allowed_happy_path() -> None:
    assert can_transition_payroll_status("draft", "approved")
    assert can_transition_payroll_status("calculated", "approved")
    assert can_transition_payroll_status("approved", "paid")
    assert can_transition_payroll_status("draft", "cancelled")


def test_same_status_is_noop() -> None:
    assert can_transition_payroll_status("paid", "paid")


def test_rejects_illegal_jumps() -> None:
    assert not can_transition_payroll_status("paid", "draft")
    assert not can_transition_payroll_status("paid", "approved")
    assert not can_transition_payroll_status("cancelled", "approved")
    assert not can_transition_payroll_status("approved", "draft")
