import uuid
from pathlib import PurePath
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.config import settings
from app.deps import DB, SuperAdminOnly
from app.models.location import Location
from app.models.location_attachment import LocationAttachment
from app.schemas.location_attachment import AttachmentLimitsOut, LocationAttachmentOut
from app.services import audit_log as audit_log_svc
from app.services.attachments import (
    current_month,
    earliest_month,
    month_in_window,
    purge_expired_attachments,
)
from app.services.media_storage import (
    MediaStorageError,
    delete_attachment_file,
    resolve_attachment_path,
    save_attachment_bytes,
)

router = APIRouter(prefix="/locations/{location_id}/attachments", tags=["location-attachments"])


async def _get_location(db: DB, location_id: uuid.UUID) -> Location:
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


async def _get_attachment(db: DB, location_id: uuid.UUID, attachment_id: uuid.UUID) -> LocationAttachment:
    attachment = await db.get(LocationAttachment, attachment_id)
    if not attachment or attachment.location_id != location_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return attachment


@router.get("", response_model=AttachmentLimitsOut)
async def list_attachments(location_id: uuid.UUID, _admin: SuperAdminOnly, db: DB) -> AttachmentLimitsOut:
    await _get_location(db, location_id)
    await purge_expired_attachments(db)
    rows = (
        await db.execute(
            select(LocationAttachment)
            .where(LocationAttachment.location_id == location_id)
            .order_by(LocationAttachment.month.desc(), LocationAttachment.created_at.desc())
        )
    ).scalars().all()
    return AttachmentLimitsOut(
        earliest_month=earliest_month(),
        current_month=current_month(),
        per_month=settings.ATTACHMENTS_PER_MONTH,
        items=[LocationAttachmentOut.model_validate(r) for r in rows],
    )


@router.post("", response_model=LocationAttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    location_id: uuid.UUID,
    file: UploadFile,
    month: Annotated[str, Form()],
    admin: SuperAdminOnly,
    db: DB,
    caption: Annotated[str | None, Form(max_length=255)] = None,
) -> LocationAttachment:
    await _get_location(db, location_id)
    await purge_expired_attachments(db)
    if not month_in_window(month):
        raise HTTPException(
            status_code=400,
            detail=f"Month must be between {earliest_month()} and {current_month()}",
        )
    used = await db.scalar(
        select(func.count())
        .select_from(LocationAttachment)
        .where(LocationAttachment.location_id == location_id, LocationAttachment.month == month)
    )
    if (used or 0) >= settings.ATTACHMENTS_PER_MONTH:
        raise HTTPException(
            status_code=409,
            detail=f"Limit reached: at most {settings.ATTACHMENTS_PER_MONTH} attachments per month",
        )

    content = await file.read()
    try:
        saved = save_attachment_bytes(content)
    except MediaStorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    stem = PurePath(file.filename or "attachment").stem[:200] or "attachment"
    ext = PurePath(saved.key).suffix
    attachment = LocationAttachment(
        location_id=location_id,
        month=month,
        file_key=saved.key,
        original_name=f"{stem}{ext}",
        content_type=saved.content_type,
        size=saved.size,
        caption=(caption or "").strip() or None,
        uploaded_by_id=admin.id,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    await audit_log_svc.log_audit(
        db,
        user_id=admin.id,
        action="CREATE",
        table_name="location_attachments",
        record_id=attachment.id,
        new_values={
            "location_id": str(location_id),
            "month": month,
            "original_name": attachment.original_name,
            "size": attachment.size,
        },
        description=f"Uploaded attachment {attachment.original_name} for location {location_id}",
    )
    return attachment


@router.get("/{attachment_id}/download")
async def download_attachment(
    location_id: uuid.UUID, attachment_id: uuid.UUID, _admin: SuperAdminOnly, db: DB
) -> FileResponse:
    attachment = await _get_attachment(db, location_id, attachment_id)
    try:
        path = resolve_attachment_path(attachment.file_key)
    except (MediaStorageError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    return FileResponse(
        path,
        media_type=attachment.content_type,
        filename=attachment.original_name,
        headers={"Cache-Control": "private, no-store"},
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    location_id: uuid.UUID, attachment_id: uuid.UUID, _admin: SuperAdminOnly, db: DB
) -> Response:
    attachment = await _get_attachment(db, location_id, attachment_id)
    key = attachment.file_key
    await db.delete(attachment)
    await db.commit()
    await audit_log_svc.log_audit(
        db,
        user_id=_admin.id,
        action="DELETE",
        table_name="location_attachments",
        record_id=attachment_id,
        description=f"Deleted attachment {attachment.original_name} from location {location_id}",
    )
    delete_attachment_file(key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
