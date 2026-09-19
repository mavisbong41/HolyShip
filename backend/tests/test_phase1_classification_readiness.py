import pytest

from backend.app.classification.models import ClassificationInput
from backend.app.classification.pipeline import classify_email
from backend.app.classification.readiness import AWAITING_DOCUMENTS, READY_FOR_COMPARISON, UNRESOLVED
from backend.app.classification.signals import EmailCategory


def email(subject: str, body: str, attachments: list[str] | None = None) -> ClassificationInput:
    attachments = attachments or []
    return ClassificationInput("synthetic", subject, body, attachments, len(attachments))


@pytest.mark.req("CLS-01")
def test_final_classifier_has_exactly_five_categories_and_no_uncertain():
    samples = [
        email("check", "Please compare the attached SI and draft BL.", ["SI.txt", "BL.txt"]),
        email("SI", "Please prepare shipping instruction for this shipment."),
        email("invoice", "Please clarify this payment amount on the invoice."),
        email("update", "FYI operational update summary."),
        email("offer", "Congratulations you have won. Click here to claim."),
        email("", "."),
    ]
    allowed = {"document_comparison", "new_si_request", "invoice_query", "general_message", "spam"}
    assert {category.value for category in EmailCategory} == allowed
    assert set(EmailCategory.__members__) == {
        "DOCUMENT_COMPARISON",
        "NEW_SI_REQUEST",
        "INVOICE_QUERY",
        "GENERAL_MESSAGE",
        "SPAM",
    }
    assert "UNCERTAIN" not in EmailCategory.__members__
    assert "GENERAL_MAIL" not in EmailCategory.__members__
    assert {classify_email(item).category for item in samples} <= allowed


@pytest.mark.req("CLS-05")
@pytest.mark.req("CLS-08")
@pytest.mark.req("STA-02")
def test_pattern_a_is_comparison_awaiting_draft_bl():
    result = classify_email(email("Draft BL", "Please assist to send the draft BL for booking 42 for checking asap."))
    assert result.category == "document_comparison"
    assert result.comparison_readiness == AWAITING_DOCUMENTS


@pytest.mark.req("CLS-06")
@pytest.mark.req("CLS-07")
@pytest.mark.req("CLS-12")
def test_pattern_b_dense_si_request_is_not_awaiting_documents():
    result = classify_email(email("Shipping instruction", "Please prepare shipping instruction. Shipper: A. Consignee: B. Notify party: C. Port of loading: SG. Port of discharge: AU. Container: 2. Gross weight: 1000kg. Please revert with draft BL once available."))
    assert result.category == "new_si_request"
    assert result.comparison_readiness is None


@pytest.mark.req("CLS-05")
@pytest.mark.req("CLS-12")
@pytest.mark.req("STA-07")
def test_readiness_is_comparison_only_and_has_ready_unresolved_states():
    ready = classify_email(email("Compare", "Please compare the attached SI and draft BL.", ["SI.txt", "BL.txt"]))
    unresolved = classify_email(email("Check BL", "Please check draft BL details."))
    non_comparison = classify_email(email("Invoice", "Please clarify this payment amount on the invoice."))
    assert ready.comparison_readiness == READY_FOR_COMPARISON
    assert unresolved.comparison_readiness == UNRESOLVED
    assert non_comparison.comparison_readiness is None
