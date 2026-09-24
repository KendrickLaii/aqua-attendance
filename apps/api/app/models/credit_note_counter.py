import uuid

from sqlalchemy import ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CreditNoteCounter(Base):
    """Per-location counter for printed credit-note numbers (RF0001…)."""

    __tablename__ = "credit_note_counters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("locations.id", ondelete="CASCADE"), nullable=True, unique=True, index=True
    )
    next_no: Mapped[int] = mapped_column(Integer, nullable=False)

    location = relationship("Location")
