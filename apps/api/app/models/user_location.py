import uuid

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserLocation(Base):
    """Teams a store manager or staff web account may open.

    Superadmins are not listed here; they can open every team.
    """

    __tablename__ = "user_locations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True
    )
