from backend.app.storage.models import EmailMessageRecord, ProcessingEventRecord

PROCESSING_STATUSES = frozenset({"NEW","QUEUED","CLASSIFYING","CLASSIFIED","AWAITING_DOCUMENTS","RETRIEVING_ATTACHMENTS","EXTRACTING","COMPARING","COMPLETED","BLOCKED","FAILED"})

def transition(session, email: EmailMessageRecord, target_status: str, reason_code: str) -> bool:
    if target_status not in PROCESSING_STATUSES:
        raise ValueError(f"Invalid processing status: {target_status}")
    if email.processing_status == target_status:
        return False
    old_status = email.processing_status
    email.processing_status = target_status
    session.add(ProcessingEventRecord(email_id=email.id, old_status=old_status, new_status=target_status, reason_code=reason_code))
    session.flush()
    return True
