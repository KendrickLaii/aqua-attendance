import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.deps import AdminOnly, CurrentUser, DB
from app.models.notification import Notification
from app.schemas.notification import NotificationCreate, NotificationOut, NotificationUpdate

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    user: CurrentUser,
    db: DB,
    response: Response,
    is_read: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> list[NotificationOut]:
    """List notifications for the current user."""
    q = select(Notification).where(
        (Notification.user_id == user.id) | (Notification.user_id.is_(None))
    )
    count_q = select(func.count()).select_from(Notification).where(
        (Notification.user_id == user.id) | (Notification.user_id.is_(None))
    )

    if is_read is not None:
        q = q.where(Notification.is_read == is_read)
        count_q = count_q.where(Notification.is_read == is_read)

    total = (await db.execute(count_q)).scalar_one()
    q = (
        q.order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    response.headers["X-Total-Count"] = str(total)
    return list(result.scalars().all())


@router.post("", response_model=NotificationOut, status_code=status.HTTP_201_CREATED)
async def create_notification(
    body: NotificationCreate, _admin: AdminOnly, db: DB
) -> NotificationOut:
    """Create a notification (admin only)."""
    notification = Notification(**body.model_dump())
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return NotificationOut.model_validate(notification)


@router.patch("/{notification_id}", response_model=NotificationOut)
async def update_notification(
    notification_id: uuid.UUID, body: NotificationUpdate, user: CurrentUser, db: DB
) -> NotificationOut:
    """Mark a notification as read/unread."""
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Users can only update their own notifications (or global ones)
    if notification.user_id and notification.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your notification")

    update_data = body.model_dump(exclude_unset=True)
    if "is_read" in update_data and update_data["is_read"]:
        update_data["read_at"] = datetime.now(timezone.utc)
    elif "is_read" in update_data and not update_data["is_read"]:
        update_data["read_at"] = None

    for field, value in update_data.items():
        setattr(notification, field, value)
    await db.commit()
    await db.refresh(notification)
    return NotificationOut.model_validate(notification)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(notification_id: uuid.UUID, _admin: AdminOnly, db: DB) -> None:
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.delete(notification)
    await db.commit()
