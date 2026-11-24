import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from app.deps import DB, OfficeOnly
from app.models.invoice_job_option import InvoiceJobOption
from app.schemas.invoice_job import InvoiceJobCreate, InvoiceJobOut
from app.services.team_access import require_team, team_filter, assigned_team_ids

router = APIRouter(prefix="/invoice-jobs", tags=["invoices"])


@router.get("", response_model=list[InvoiceJobOut])
async def list_invoice_jobs(
    actor: OfficeOnly,
    db: DB,
    location_id: uuid.UUID | None = None,
) -> list[InvoiceJobOption]:
    if location_id is not None:
        await require_team(db, actor, location_id)
    query = select(InvoiceJobOption).order_by(InvoiceJobOption.name)
    if location_id is not None:
        query = query.where(InvoiceJobOption.location_id == location_id)
    else:
        clause = team_filter(InvoiceJobOption.location_id, await assigned_team_ids(db, actor))
        if clause is not None:
            query = query.where(clause)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=InvoiceJobOut)
async def create_invoice_job(payload: InvoiceJobCreate, actor: OfficeOnly, db: DB) -> InvoiceJobOption:
    await require_team(db, actor, payload.location_id)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Enter a job name.")

    existing = await db.scalar(
        select(InvoiceJobOption).where(
            InvoiceJobOption.location_id == payload.location_id,
            func.lower(InvoiceJobOption.name) == name.lower(),
        )
    )
    if existing is not None:
        return existing

    row = InvoiceJobOption(location_id=payload.location_id, name=name)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice_job(job_id: uuid.UUID, actor: OfficeOnly, db: DB) -> Response:
    row = await db.get(InvoiceJobOption, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    await require_team(db, actor, row.location_id)
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
