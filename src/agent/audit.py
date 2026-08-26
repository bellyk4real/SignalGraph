from sqlalchemy.orm import Session

from src.agent.models import AuditLog


def record_access(
    session: Session,
    *,
    action: str,
    subject_type: str,
    subject_id=None,
    requested_sensitivity: str,
    resource_sensitivity: str,
    decision: str,
    detail: str = "",
) -> AuditLog:
    entry = AuditLog(
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        requested_sensitivity=requested_sensitivity,
        resource_sensitivity=resource_sensitivity,
        decision=decision,
        detail=detail,
    )
    session.add(entry)
    session.flush()
    return entry
