import uuid
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import AdminOnly, DB
from app.models.location import Location
from app.models.shift import Shift, ShiftTemplate
from app.models.unit import Unit
from app.schemas.shift import (
    ShiftCopyWeek,
    ShiftCopyWeekResult,
    ShiftCreate,
    ShiftOut,
    ShiftTemplateCreate,
    ShiftTemplateOut,
    ShiftTemplateUpdate,
    ShiftUpdate,
)
from app.services import audit_log as audit_log_svc

MAX_RANGE_DAYS = 62

templates_router = APIRouter(prefix="/shift-templates", tags=["shifts"])
router = APIRouter(prefix="/shifts", tags=["shifts"])


def _assert_times(start, end) -> None:
    if end <= start:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")


async def _get_template(db: DB, template_id: uuid.UUID) -> ShiftTemplate:
    template = await db.get(ShiftTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Shift template not found")
    return template


async def _get_shift(db: DB, shift_id: uuid.UUID) -> Shift:
    shift = await db.get(Shift, shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return shift


async def _assert_refs(
    db: DB, unit_id: uuid.UUID, location_id: uuid.UUID, template_id: uuid.UUID | None
) -> None:
    unit_type = await db.scalar(select(Unit.unit_type).where(Unit.id == unit_id))
    if unit_type != "staff":
        raise HTTPException(status_code=422, detail="unit_id does not reference an existing staff member")
    if not await db.scalar(select(Location.id).where(Location.id == location_id)):
        raise HTTPException(status_code=422, detail="location_id does not reference an existing location")
    if template_id and not await db.scalar(select(ShiftTemplate.id).where(ShiftTemplate.id == template_id)):
        raise HTTPException(status_code=422, detail="template_id does not reference an existing shift template")


# ---- Templates ----


@templates_router.get("", response_model=list[ShiftTemplateOut])
async def list_shift_templates(_admin: AdminOnly, db: DB) -> list[ShiftTemplate]:
    result = await db.execute(
        select(ShiftTemplate).order_by(ShiftTemplate.sort_order, ShiftTemplate.start_time, ShiftTemplate.name)
    )
    return list(result.scalars().all())


@templates_router.post("", response_model=ShiftTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_shift_template(body: ShiftTemplateCreate, _admin: AdminOnly, db: DB) -> ShiftTemplate:
    template = ShiftTemplate(**body.model_dump())
    db.add(template)
    await db.commit()
    await db.refresh(template)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="CREATE",
        table_name="shift_templates",
        record_id=template.id,
        new_values=body.model_dump(),
        description=f"Created shift template {template.name or template.id}",
    )
    return template


@templates_router.patch("/{template_id}", response_model=ShiftTemplateOut)
async def update_shift_template(
    template_id: uuid.UUID, body: ShiftTemplateUpdate, _admin: AdminOnly, db: DB
) -> ShiftTemplate:
    template = await _get_template(db, template_id)
    update_data = body.model_dump(exclude_unset=True)
    old_values = {field: getattr(template, field) for field in update_data}
    for field, value in update_data.items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        setattr(template, field, value)
    _assert_times(template.start_time, template.end_time)
    await db.commit()
    await db.refresh(template)
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="UPDATE",
        table_name="shift_templates",
        record_id=template_id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated shift template {template.name or template_id}",
    )
    return template


@templates_router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift_template(template_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    template = await _get_template(db, template_id)
    await db.delete(template)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="DELETE",
        table_name="shift_templates",
        record_id=template_id,
        description=f"Deleted shift template {template.name or template_id}",
    )


# ---- Shifts ----


@router.get("", response_model=list[ShiftOut])
async def list_shifts(
    _admin: AdminOnly,
    db: DB,
    start: date = Query(description="First day (inclusive)"),
    end: date = Query(description="Last day (inclusive)"),
    location_id: uuid.UUID | None = None,
    unit_id: uuid.UUID | None = None,
) -> list[Shift]:
    if end < start:
        raise HTTPException(status_code=422, detail="end must be on or after start")
    if (end - start).days >= MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail=f"Date range cannot exceed {MAX_RANGE_DAYS} days")

    q = select(Shift).where(Shift.shift_date >= start, Shift.shift_date <= end)
    if location_id:
        q = q.where(Shift.location_id == location_id)
    if unit_id:
        q = q.where(Shift.unit_id == unit_id)
    result = await db.execute(q.order_by(Shift.shift_date, Shift.start_time))
    return list(result.scalars().all())


@router.post("", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
async def create_shift(body: ShiftCreate, admin: AdminOnly, db: DB) -> Shift:
    await _assert_refs(db, body.unit_id, body.location_id, body.template_id)
    shift = Shift(**body.model_dump(), created_by_id=admin.id, updated_by_id=admin.id)
    db.add(shift)
    await db.commit()
    await db.refresh(shift)
    await audit_log_svc.log_audit(
        db,
        user_id=admin.id,
        action="CREATE",
        table_name="shifts",
        record_id=shift.id,
        new_values=body.model_dump(),
        description=f"Created shift for unit {body.unit_id} on {body.shift_date}",
    )
    return shift


@router.post("/copy-week", response_model=ShiftCopyWeekResult)
async def copy_week(body: ShiftCopyWeek, admin: AdminOnly, db: DB) -> ShiftCopyWeekResult:
    offset = body.target_week_start - body.source_week_start
    source_end = body.source_week_start + timedelta(days=6)
    target_end = body.target_week_start + timedelta(days=6)

    source_q = (
        select(Shift, Unit.is_active)
        .join(Unit, Unit.id == Shift.unit_id)
        .where(Shift.shift_date >= body.source_week_start, Shift.shift_date <= source_end)
    )
    target_q = select(Shift).where(Shift.shift_date >= body.target_week_start, Shift.shift_date <= target_end)
    if body.location_id:
        source_q = source_q.where(Shift.location_id == body.location_id)
        target_q = target_q.where(Shift.location_id == body.location_id)

    existing = {
        (s.unit_id, s.location_id, s.shift_date, s.start_time, s.end_time)
        for s in (await db.execute(target_q)).scalars().all()
    }

    created = skipped = 0
    for src, unit_active in (await db.execute(source_q)).all():
        new_date = src.shift_date + offset
        key = (src.unit_id, src.location_id, new_date, src.start_time, src.end_time)
        if not unit_active or key in existing:
            skipped += 1
            continue
        existing.add(key)
        db.add(
            Shift(
                unit_id=src.unit_id,
                location_id=src.location_id,
                shift_date=new_date,
                start_time=src.start_time,
                end_time=src.end_time,
                title=src.title,
                color=src.color,
                notes=src.notes,
                template_id=src.template_id,
                created_by_id=admin.id,
                updated_by_id=admin.id,
            )
        )
        created += 1

    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=admin.id,
        action="DATA_EXPORT",
        table_name="shifts",
        batch_operation=True,
        description=f"Copied week {body.source_week_start} -> {body.target_week_start}: {created} created, {skipped} skipped",
    )
    return ShiftCopyWeekResult(created=created, skipped=skipped)


@router.patch("/{shift_id}", response_model=ShiftOut)
async def update_shift(shift_id: uuid.UUID, body: ShiftUpdate, admin: AdminOnly, db: DB) -> Shift:
    shift = await _get_shift(db, shift_id)
    nullable = {"title", "notes", "template_id"}
    update_data = body.model_dump(exclude_unset=True)
    old_values = {field: getattr(shift, field) for field in update_data}
    for field, value in update_data.items():
        if value is None and field not in nullable:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        setattr(shift, field, value)
    _assert_times(shift.start_time, shift.end_time)
    await _assert_refs(db, shift.unit_id, shift.location_id, shift.template_id)
    shift.updated_by_id = admin.id
    await db.commit()
    await db.refresh(shift)
    await audit_log_svc.log_audit(
        db,
        user_id=admin.id,
        action="UPDATE",
        table_name="shifts",
        record_id=shift_id,
        old_values=old_values,
        new_values=update_data,
        description=f"Updated shift {shift_id} on {shift.shift_date}",
    )
    return shift


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift(shift_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    shift = await _get_shift(db, shift_id)
    await db.delete(shift)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="DELETE",
        table_name="shifts",
        record_id=shift_id,
        description=f"Deleted shift {shift_id} on {shift.shift_date}",
    )
