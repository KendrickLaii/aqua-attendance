import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class AuditAction(str, enum.Enum):
    create = "CREATE"
    update = "UPDATE"
    delete = "DELETE"
    login = "LOGIN"
    logout = "LOGOUT"
    password_change = "PASSWORD_CHANGE"
    role_change = "ROLE_CHANGE"
    manual_correction = "MANUAL_CORRECTION"
    data_export = "DATA_EXPORT"
    system_config = "SYSTEM_CONFIG"


class AuditLog(Base):
    """Comprehensive audit logging for all data changes and system operations."""
    
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    
    # Who performed the action
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # What was done
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # CREATE, UPDATE, DELETE, etc.
    table_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # Table that was affected
    record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)  # Primary key of affected record
    
    # What changed
    old_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Previous state (for UPDATE/DELETE)
    new_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # New state (for CREATE/UPDATE)
    
    # Context
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # Human-readable description
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max length
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)  # Browser/client info
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Session identifier
    
    # Additional metadata
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # For request tracing
    batch_operation: Mapped[bool] = mapped_column(default=False)  # Part of bulk operation?
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
