from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from backend.app.storage.models import (
    HumanReviewCaseRecord,
    HumanReviewFieldOverrideRecord,
    ExtractedFieldRecord,
    ComparisonResultRecord,
    EmailMessageRecord
)
from backend.app.api.product_schemas import HumanReviewAnalytics
from backend.app.api.review_helper import compute_affected_fields, compute_priority, compute_age_minutes
import json

def get_human_review_analytics(session: Session) -> HumanReviewAnalytics:
    now = datetime.now(timezone.utc)
    # Fetch all active cases
    cases = session.scalars(
        select(HumanReviewCaseRecord)
        .where(HumanReviewCaseRecord.case_origin == "ACTIVE")
    ).all()
    
    analytics = HumanReviewAnalytics()
    open_ages = []
    
    for c in cases:
        if c.status == "OPEN":
            analytics.open_count += 1
            open_ages.append(compute_age_minutes(c.created_at))
        elif c.status == "IN_REVIEW":
            analytics.in_review_count += 1
            open_ages.append(compute_age_minutes(c.created_at))
        elif c.status == "RESOLVED":
            analytics.resolved_count += 1
            if c.resolved_at and c.resolved_at.date() == now.date():
                analytics.resolved_today_count += 1
        elif c.status == "DISMISSED":
            analytics.dismissed_count += 1
            
        # priority & reason
        comp = None
        if c.source_comparison_id:
            comp = session.get(ComparisonResultRecord, c.source_comparison_id)
        if not comp:
            comp = session.scalar(select(ComparisonResultRecord).where(ComparisonResultRecord.email_id == c.email_id).order_by(ComparisonResultRecord.created_at.desc()))
            
        # we need ProductComparison schema or mock it.
        # compute_affected_fields expects ProductComparison or similar object with mismatched_fields and unresolved_fields.
        # The DB record ComparisonResultRecord has `mismatched_fields` and `unresolved_fields` directly as JSON lists!
        affected = compute_affected_fields(c, comp)
        prio = compute_priority(c, affected)
        
        analytics.priority_distribution[prio] = analytics.priority_distribution.get(prio, 0) + 1
        analytics.reason_distribution[c.reason_code] = analytics.reason_distribution.get(c.reason_code, 0) + 1
        
        for f in affected:
            analytics.most_reviewed_fields[f] = analytics.most_reviewed_fields.get(f, 0) + 1
            
    if open_ages:
        analytics.average_open_age_minutes = sum(open_ages) / len(open_ages)
        
    # Correction insights
    overrides = session.scalars(
        select(HumanReviewFieldOverrideRecord)
        .where(HumanReviewFieldOverrideRecord.active == True)
    ).all()
    
    for ov in overrides:
        f = ov.field_name
        analytics.most_corrected_fields[f] = analytics.most_corrected_fields.get(f, 0) + 1
        
        extracted = session.get(ExtractedFieldRecord, ov.original_field_id)
        reason = "Manual source confirmation"
        if extracted:
            if extracted.raw_value is None:
                reason = "Missing extraction"
            elif extracted.confidence is not None and extracted.confidence < 0.8:
                reason = "OCR ambiguity"
            elif extracted.raw_value == ov.corrected_value and extracted.canonical_value != ov.corrected_canonical_value:
                reason = "Value normalization"
            elif f in ["shipper", "consignee", "notify_party"]:
                reason = "Entity ambiguity"
        
        analytics.correction_reasons[reason] = analytics.correction_reasons.get(reason, 0) + 1
        
    return analytics
