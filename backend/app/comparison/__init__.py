"""Pure, in-memory comparison primitives for extracted SI and draft BL fields."""

from backend.app.comparison.l1 import FieldSpecificL1Comparator, PortAliasRegistry
from backend.app.comparison.models import (
    ComparisonBatchResult,
    ComparisonLayer,
    FieldComparisonResult,
    FieldComparisonStatus,
    LayerDecision,
    LayerResolution,
    SemanticResolution,
)
from backend.app.comparison.service import COMPARISON_VERSION, ComparisonService

__all__ = [
    "ComparisonBatchResult",
    "ComparisonLayer",
    "ComparisonService",
    "COMPARISON_VERSION",
    "FieldSpecificL1Comparator",
    "FieldComparisonResult",
    "FieldComparisonStatus",
    "LayerDecision",
    "LayerResolution",
    "PortAliasRegistry",
    "SemanticResolution",
]
