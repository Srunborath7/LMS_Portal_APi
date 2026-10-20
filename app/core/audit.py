from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Uuid, event, func
from sqlalchemy.orm import Mapped, Session, mapped_column

# Set once per request by the auth dependency
current_user_id: ContextVar[UUID | None] = ContextVar("current_user_id", default=None)


class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)
    created_by_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True),ForeignKey("auths.id", ondelete="SET NULL"),nullable=True,index=True)
    updated_by_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True),ForeignKey("auths.id", ondelete="SET NULL"),nullable=True,index=True)

@event.listens_for(Session, "before_flush")
def _fill_audit_fields(session: Session, flush_context, instances) -> None:
    user_id = current_user_id.get()
    if user_id is None:  # scripts, seeds, background jobs
        return

    for obj in session.new:
        if isinstance(obj, AuditMixin):
            if obj.created_by_id is None:
                obj.created_by_id = user_id
            obj.updated_by_id = user_id

    for obj in session.dirty:
        if isinstance(obj, AuditMixin) and session.is_modified(obj, include_collections=False):
            obj.updated_by_id = user_id