from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.documents.models import DocumentType
from backend.app.documents.readers.composite import CompositeDocumentReader
from backend.app.documents.readers.ocr_reader import OcrReader, OcrSharedState
from backend.app.documents.role_validation import DocumentRoleValidator, RoleValidationOutcome
from backend.app.extraction.extractor import DeterministicDocumentExtractor
from backend.app.extraction.models import CanonicalField, FieldStatus


@pytest.mark.req("DOC-07b")
@pytest.mark.req("DOC-12")
def test_injected_ocr_text_flows_through_role_validation_and_extraction():
    reader = OcrReader(
        engine=lambda _content, _filename: (
            "SHIPPING INSTRUCTION\nShipper: Alpha Trading\n"
            "Port of Loading: Port Klang\nGross Weight: 22,000 KG"
        ),
        timeout_seconds=0.1,
        max_calls=2,
        max_concurrent_calls=1,
    )

    document = reader.read(b"synthetic image", "scan.png", "fixture/scan.png")
    validation = DocumentRoleValidator().validate(document)
    document.document_type = validation.document_type
    result = DeterministicDocumentExtractor().extract(document)

    assert document.extraction_status == "EXTRACTED"
    assert document.metadata["ocr_engine"] == "injected"
    assert validation.outcome == RoleValidationOutcome.VALID
    assert validation.document_type == DocumentType.SI
    assert result.fields[CanonicalField.SHIPPER].canonical_value == "Alpha Trading"
    assert result.fields[CanonicalField.GROSS_WEIGHT_KG].canonical_value == 22000


def test_unavailable_and_garbage_ocr_remain_cleanly_unresolved():
    unavailable = OcrReader(tesseract_cmd=None, auto_detect_tesseract=False)
    result = unavailable.read(b"image", "scan.png", "fixture/no-ocr.png")
    assert result.extraction_status == "FAILED"
    assert result.metadata["ocr_available"] is False

    garbage = OcrReader(engine=lambda *_args: "unstructured pixels only")
    document = garbage.read(b"other", "scan.png", "fixture/garbage.png")
    assert DocumentRoleValidator().validate(document).outcome == RoleValidationOutcome.INCONCLUSIVE
    document.document_type = DocumentType.UNKNOWN
    fields = DeterministicDocumentExtractor().extract(document).fields
    assert all(field.status == FieldStatus.MISSING for field in fields.values())


@pytest.mark.req("PRF-03")
def test_ocr_timeout_and_budget_are_bounded_without_vision_fabrication():
    reader = OcrReader(
        engine=lambda *_args: (time.sleep(0.2), "late text")[1],
        timeout_seconds=0.01,
        max_calls=1,
        max_concurrent_calls=1,
    )
    composite = CompositeDocumentReader(ocr_reader=reader)

    timed_out = composite.read(b"image-one", "one.png", "fixture/one.png")
    exhausted = composite.read(b"image-two", "two.png", "fixture/two.png")

    assert timed_out.extraction_status == "UNREADABLE"
    assert "timed out" in (timed_out.error_message or "").casefold()
    assert exhausted.extraction_status == "UNREADABLE"
    assert exhausted.metadata["reason_code"] == "OCR_CALL_BUDGET_EXHAUSTED"
    assert reader.provider_calls == 1
    assert exhausted.reader_used == "OcrReader"


@pytest.mark.req("PRF-02")
def test_ocr_concurrency_limit_and_content_cache_are_enforced():
    lock = threading.Lock()
    active = 0
    peak = 0

    def engine(_content, _filename):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return "SHIPPING INSTRUCTION\nShipper: Alpha"

    reader = OcrReader(
        engine=engine,
        timeout_seconds=0.2,
        max_calls=3,
        max_concurrent_calls=1,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda item: reader.read(item[0], item[1], item[1]),
            [(b"one", "one.png"), (b"two", "two.png")],
        ))
    cached = reader.read(b"one", "one.png", "different/reference.png")

    assert all(result.extraction_status == "EXTRACTED" for result in results)
    assert peak == 1
    assert reader.provider_calls == 2
    assert reader.cache_hits == 1
    assert cached.raw_text == results[0].raw_text


def test_ocr_limit_and_cache_are_shared_across_worker_readers():
    lock = threading.Lock()
    active = 0
    peak = 0

    def engine(_content, _filename):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return "SHIPPING INSTRUCTION\nShipper: Alpha"

    state = OcrSharedState(max_calls=3, max_concurrent_calls=1)
    readers = [
        OcrReader(engine=engine, timeout_seconds=0.2, shared_state=state),
        OcrReader(engine=engine, timeout_seconds=0.2, shared_state=state),
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            pool.submit(readers[0].read, b"one", "one.png", "one"),
            pool.submit(readers[1].read, b"two", "two.png", "two"),
        ]
        assert all(future.result(timeout=2).extraction_status == "EXTRACTED" for future in results)
    cached = readers[1].read(b"one", "one.png", "other")

    assert peak == 1
    assert state.provider_calls == 2
    assert state.cache_hits == 1
    assert cached.extraction_status == "EXTRACTED"
