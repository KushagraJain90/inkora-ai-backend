
from typing import Literal

from pydantic import BaseModel, Field


class EvaluationFeedback(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    missing_or_weak_points: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    ways_to_gain_more_marks: list[str] = Field(default_factory=list)


class EvaluationCriterion(BaseModel):
    criterion: str = Field(min_length=1)
    marks_awarded: float = Field(ge=0)
    marks_possible: float
    comment: str = Field(min_length=1)


class EvaluationResponse(BaseModel):
    evaluation_status: Literal["evaluated", "needs_clarification"]
    marks_awarded: float | None
    total_marks: float | None
    score_rationale: str
    feedback_summary: str
    clarification_needed: str | None
    scoring_breakdown: list[EvaluationCriterion] = Field(default_factory=list)
    feedback: EvaluationFeedback


class EvaluationOcrPage(BaseModel):
    page_number: int = Field(ge=1)
    transcription: str


class EvaluationOcrResponse(BaseModel):
    pages: list[EvaluationOcrPage]
