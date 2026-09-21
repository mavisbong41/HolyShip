from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

ALLOWED_REVIEW_FIELDS = (
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
)

ReviewFieldType = Literal[
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
]

ReviewDocumentSide = Literal["SI", "BL"]
ReviewMode = Literal["EXPLANATION_ONLY", "ACTIONABLE_SUGGESTION", "INSUFFICIENT_EVIDENCE"]


class AISuggestionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["FIELD_OVERRIDE"]
    document_side: ReviewDocumentSide
    field: ReviewFieldType
    current_value: str
    suggested_value: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence_refs: list[str] = Field(min_length=1)


class AIStructuredResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    mode: ReviewMode
    suggestion: AISuggestionPayload | None = None

    @model_validator(mode="after")
    def validate_suggestion_mode_agreement(self) -> AIStructuredResponse:
        if self.mode == "ACTIONABLE_SUGGESTION":
            if self.suggestion is None:
                raise ValueError("suggestion is required when mode is ACTIONABLE_SUGGESTION")
            if not self.suggestion.evidence_refs:
                raise ValueError("evidence_refs must be non-empty for ACTIONABLE_SUGGESTION")
        else:
            if self.suggestion is not None:
                raise ValueError(f"suggestion must be null/omitted when mode is {self.mode}")
        return self
