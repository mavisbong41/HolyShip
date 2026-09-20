"""Deterministic contracts for canonical shipment-field extraction."""

from backend.app.extraction.extractor import DeterministicDocumentExtractor
from backend.app.extraction.label_mapping import LabelMapper
from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    DocumentExtractionResult,
    ExtractedField,
    FieldStatus,
    LabelMappingContext,
    LabelMappingResult,
    MappingMethod,
    SourceLocation,
)

__all__ = [
    "CANONICAL_FIELDS",
    "CanonicalField",
    "DeterministicDocumentExtractor",
    "DocumentExtractionResult",
    "ExtractedField",
    "FieldStatus",
    "LabelMapper",
    "LabelMappingContext",
    "LabelMappingResult",
    "MappingMethod",
    "SourceLocation",
]
