import enum
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class PayrollStatus(str, enum.Enum):
    draft = "draft"
    calculated = "calculated"
    approved = "approved"
    paid = "paid"
    cancelled = "cancelled"


class PayrollRecordCreate(BaseModel):
    product_id: uuid.UUID
    payroll_period_start: date
    payroll_period_end: date
    total_regular_hours: float = Field(default=0.0, ge=0)
    total_overtime_hours: float = Field(default=0.0, ge=0)
    total_holiday_hours: float = Field(default=0.0, ge=0)
    total_work_days: int = Field(default=0, ge=0)
    total_leave_days: int = Field(default=0, ge=0)
    regular_slots: int = Field(default=0, ge=0)
    ot_slots: int = Field(default=0, ge=0)
    hourly_rate_snapshot: float | None = Field(default=None, ge=0)
    ot_multiplier_snapshot: float | None = Field(default=None, ge=0)
    base_salary: float = Field(default=0.0, ge=0)
    overtime_pay: float = Field(default=0.0, ge=0)
    holiday_pay: float = Field(default=0.0, ge=0)
    allowance: float = Field(default=0.0, ge=0)
    deduction: float = Field(default=0.0, ge=0)
    bonus: float = Field(default=0.0, ge=0)
    adjustment_1: float = Field(default=0.0)
    adjustment_2: float = Field(default=0.0)
    adjustment_1_remark: str | None = None
    adjustment_2_remark: str | None = None
    gross_pay: float = Field(default=0.0, ge=0)
    net_pay: float = Field(default=0.0, ge=0)
    status: str = Field(default=PayrollStatus.draft.value)
    payroll_notes: str | None = None
    calculation_method: str = Field(default="standard", max_length=50)
    approved_by_user_id: uuid.UUID | None = None


class PayrollRecordUpdate(BaseModel):
    status: str | None = None
    approval_date: datetime | None = None
    payment_date: datetime | None = None
    payroll_notes: str | None = None
    approved_by_user_id: uuid.UUID | None = None
    adjustment_1: float | None = None
    adjustment_2: float | None = None
    adjustment_1_remark: str | None = None
    adjustment_2_remark: str | None = None
    gross_pay: float | None = None
    net_pay: float | None = None


class PayrollRecordOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    product_code: str | None = None
    payroll_period_start: date
    payroll_period_end: date
    total_regular_hours: float
    total_overtime_hours: float
    total_holiday_hours: float
    total_work_days: int
    total_leave_days: int
    regular_slots: int = 0
    ot_slots: int = 0
    hourly_rate_snapshot: float | None = None
    ot_multiplier_snapshot: float | None = None
    base_salary: float
    overtime_pay: float
    holiday_pay: float
    allowance: float
    deduction: float
    bonus: float
    adjustment_1: float = 0.0
    adjustment_2: float = 0.0
    adjustment_1_remark: str | None = None
    adjustment_2_remark: str | None = None
    gross_pay: float
    net_pay: float
    status: str
    calculation_date: datetime
    approval_date: datetime | None = None
    payment_date: datetime | None = None
    payroll_notes: str | None = None
    calculation_method: str
    approved_by_user_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
