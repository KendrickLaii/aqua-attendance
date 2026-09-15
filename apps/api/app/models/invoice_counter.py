import uuid

from sqlalchemy import ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvoiceCounter(Base):
    """Per-location counter for sequential printed invoice numbers (1-999999)."""

    __tablename__ = "invoice_counters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("locations.id", ondelete="CASCADE"), nullable=True, unique=True, index=True
    )
    next_no: Mapped[int] = mapped_column(Integer, nullable=False)

    location = relationship("Location")
