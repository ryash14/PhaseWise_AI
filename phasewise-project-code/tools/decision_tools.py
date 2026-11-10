"""Why a decision may not be recorded, worked out before any language model call is spent."""

from config import config


def find_review_conflict(review_status, pending_decision, review_decision,
                         application_reference):
    """Whether the review's state allows a decision at all."""
    if review_status in config.DECIDED_REVIEW_STATUSES:
        return config.ALREADY_DECIDED_MESSAGE.format(application_reference=application_reference)
    if pending_decision:
        differs = any(
            pending_decision.get(field) != review_decision.get(field)
            for field in config.DECISION_RECORD_FIELDS
        )
        if differs:
            return config.DECISION_IN_PROGRESS_MESSAGE.format(
                pending_decided_by=pending_decision.get("decided_by"),
                pending_decision=pending_decision.get("decision"),
                application_reference=application_reference,
            )
    return None


def find_decision_refusal(review_decision, screening, opened_by):
    """The first reason this decision may not be recorded on this review, or None."""
    application_reference = screening.get("application_reference")
    missing = [
        field
        for field in config.DECISION_RECORD_FIELDS
        if not isinstance(review_decision.get(field), str) or not review_decision[field].strip()
    ]
    if missing:
        return config.DECISION_FIELDS_MISSING_MESSAGE.format(
            application_reference=application_reference, fields=", ".join(missing)
        )
    decision = review_decision["decision"]
    if decision not in config.DECISIONS:
        return config.UNKNOWN_DECISION_MESSAGE.format(
            decision=decision,
            application_reference=application_reference,
            decisions=", ".join(config.DECISIONS),
        )
    role = review_decision["decided_by_role"]
    if role != config.ROLE_CONNECTIONS_ENGINEER:
        return config.DECIDING_ROLE_MESSAGE.format(
            role=role,
            application_reference=application_reference,
            engineer_role=config.ROLE_CONNECTIONS_ENGINEER,
        )
    if review_decision["decided_by"] == opened_by:
        return config.OWN_REVIEW_MESSAGE.format(
            decided_by=review_decision["decided_by"],
            application_reference=application_reference,
        )
    if decision not in screening.get("decisions_open", []):
        return config.DECISION_NOT_OPEN_MESSAGE.format(
            decision=decision,
            application_reference=application_reference,
            reason=config.APPROVE_CLOSED_REASONS.get(screening.get("assessment"), ""),
        )
    return None
