"""
Vision-module DB entities.

Tables:
  inspection_reviews — engineer feedback on static inspection results.
    Stores the reviewer identity, verdict, comment, and an immutable
    snapshot of the original AI output for audit history.

Design rules:
  - inspection_snapshot is set at review creation and never modified.
  - is_training_label is always False — server-enforced, never from client.
  - No automatic E1 conflict adjudication is performed here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InspectionReview(Base):
    __tablename__ = "inspection_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # inspection_id from StaticInspectionResult (UUID, stateless — not a FK)
    inspection_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # reviewer identity (FK to users; denormalized fields for audit trail)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    reviewer_username: Mapped[str] = mapped_column(String(200), nullable=False)
    reviewer_role: Mapped[str] = mapped_column(String(80), nullable=False)

    # engineer judgement
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)

    # original AI output at review time — immutable audit snapshot
    inspection_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    # Hard guard: never used as a training label — enforced server-side
    is_training_label: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    reviewer: Mapped["User"] = relationship("User", foreign_keys=[reviewer_id])  # type: ignore[name-defined]
