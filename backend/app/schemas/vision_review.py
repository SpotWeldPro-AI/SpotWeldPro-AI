from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field


class ReviewVerdict(str, Enum):
    AGREE          = "AGREE"
    DISAGREE       = "DISAGREE"
    FURTHER_REVIEW = "FURTHER_REVIEW"


class InspectionReviewCreate(BaseModel):
    verdict: ReviewVerdict
    comment: str = Field(..., min_length=10, max_length=2000,
                         description="Engineer comment (minimum 10 characters)")
    inspection_snapshot: Dict[str, Any] = Field(
        ...,
        description="Full StaticInspectionResult JSON at review time — immutable audit record",
    )


class InspectionReviewOut(BaseModel):
    id: int
    inspection_id: str
    reviewer_username: str
    reviewer_role: str
    verdict: ReviewVerdict
    comment: str
    created_at: datetime
    is_training_label: bool

    model_config = {"from_attributes": True}
