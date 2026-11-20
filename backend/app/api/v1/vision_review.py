"""
POST /api/v1/vision/static/inspect/{inspection_id}/review
GET  /api/v1/vision/static/inspect/{inspection_id}/reviews

Engineer review workflow for static inspection results.

ACCESS POLICY:
  POST — requires weld:write (DEMO_USER, PROCESS_ENGINEER, MANUFACTURING_ENGINEER,
         QUALITY_ENGINEER, SYSTEM_ADMIN).
  GET  — requires weld:read (all roles except none).

HARD RULES:
  - is_training_label is always False — enforced here, never from client input.
  - No automatic E1 conflict adjudication is triggered.
  - inspection_snapshot is set at creation and never modified.
  - Original inference outputs are preserved unchanged.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.db.session import get_db
from app.models.entities import User
from app.models.vision_entities import InspectionReview
from app.schemas.vision_review import InspectionReviewCreate, InspectionReviewOut

router = APIRouter(prefix="/vision/static", tags=["Vision - Engineer Review"])

_MAX_REVIEWS_PER_INSPECTION = 500


@router.post(
    "/inspect/{inspection_id}/review",
    response_model=InspectionReviewOut,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    inspection_id: str,
    payload: InspectionReviewCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("weld:write")),
) -> InspectionReviewOut:
    """
    Submit an engineer review for a static inspection result.

    The ``inspection_snapshot`` field must contain the full ``StaticInspectionResult``
    JSON returned by ``POST /vision/static/inspect``. It is stored verbatim and
    never modified — it forms the immutable audit record of the original AI output.

    ``is_training_label`` is always ``false`` regardless of what the client sends.
    No E1 conflict adjudication is triggered by submitting a review.
    """
    # Soft cap: guard against unbounded growth on a single inspection_id
    count = db.scalar(
        select(InspectionReview).where(
            InspectionReview.inspection_id == inspection_id
        ).with_only_columns(InspectionReview.id)
    )
    # count is None when no rows exist; use len of a fresh query to be safe
    existing_count = len(
        db.scalars(
            select(InspectionReview.id).where(
                InspectionReview.inspection_id == inspection_id
            )
        ).all()
    )
    if existing_count >= _MAX_REVIEWS_PER_INSPECTION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "REVIEW_LIMIT_EXCEEDED",
                "message": (
                    f"This inspection already has {existing_count} reviews "
                    f"(limit {_MAX_REVIEWS_PER_INSPECTION})."
                ),
            },
        )

    review = InspectionReview(
        inspection_id=inspection_id,
        reviewer_id=user.id,
        reviewer_username=user.username,
        reviewer_role=str(user.role),
        verdict=payload.verdict,
        comment=payload.comment,
        inspection_snapshot=payload.inspection_snapshot,
        is_training_label=False,  # always False — never from client input
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return InspectionReviewOut.model_validate(review)


@router.get(
    "/inspect/{inspection_id}/reviews",
    response_model=List[InspectionReviewOut],
)
def list_reviews(
    inspection_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("weld:read")),
) -> List[InspectionReviewOut]:
    """Return all engineer reviews for one inspection, oldest first."""
    rows = db.scalars(
        select(InspectionReview)
        .where(InspectionReview.inspection_id == inspection_id)
        .order_by(InspectionReview.created_at.asc())
    ).all()
    return [InspectionReviewOut.model_validate(r) for r in rows]
