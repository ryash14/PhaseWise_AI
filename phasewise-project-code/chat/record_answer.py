"""Answers from the records, never from a model, within what the asker's role allows."""

from config import config
from persistence.models import ApplicationReview
from persistence.repository import fetch_review_records
from tools.application_data_tools import describe_record


def _advisor_status(review, technology, application_reference):
    status_text = (
        config.CHAT_AWAITING_REVIEW_TEXT
        if review is None
        else config.REVIEW_STATUS_PHRASES[review["status"]]
    )
    line = config.CHAT_ADVISOR_STATUS_TEMPLATE.format(
        application_reference=application_reference,
        technology_application=config.TECHNOLOGY_APPLICATION_PHRASES[technology],
        status=status_text,
    )
    if review is None or review["status"] != config.REVIEW_STATUS_APPROVED:
        return line
    details = review.get("notice_details") or {}
    described = describe_record(details)
    conditions = [
        template.format(
            equipment_name=config.EQUIPMENT_NAMES[technology], value=described[column_name]
        )
        for column_name, template in config.HOUSEHOLD_CONDITION_TEMPLATES.items()
        if details.get(column_name) is not None
    ]
    return line + " " + (" ".join(conditions) if conditions else config.CHAT_NO_CONDITIONS_TEXT)


def _team_lines(review):
    requirements = "; ".join(
        f"{requirement['requirement_name']} {requirement['result']}"
        for requirement in review["requirements"]
    )
    type_counts = {}
    for finding in review["evidence"]:
        type_counts[finding["sentence_type"]] = type_counts.get(finding["sentence_type"], 0) + 1
    sentence_types = (
        ", ".join(f"{name} {count}" for name, count in sorted(type_counts.items()))
        or config.CHAT_NO_STATEMENTS_TEXT
    )
    lines = [
        config.CHAT_REVIEW_TEMPLATE.format(
            review_id=review["review_id"],
            application_reference=review["application_reference"],
            technology_label=config.TECHNOLOGY_LABELS[review["technology"]],
            standard_document=review["standard_document"],
            coordinator_id=review["coordinator_id"],
            status=config.REVIEW_STATUS_LABELS[review["status"]],
        ),
        config.CHAT_SCREENING_TEMPLATE.format(
            assessment=review["assessment"],
            requirements=requirements,
            rating_stated=config.BOOLEAN_YES if review["rating_stated"] else config.BOOLEAN_NO,
            triggers="; ".join(review["network_triggers"]) or config.CHAT_NO_TRIGGERS_TEXT,
            decisions_open=", ".join(review["decisions_open"]),
        ),
        config.CHAT_FIGURES_TEMPLATE.format(
            network_work_likelihood=format(
                review["network_work_likelihood"], "." + str(config.LIKELIHOOD_DECIMALS) + "f"
            ),
            likelihood_band=review["likelihood_band"],
            expected_working_days=review["duration_text"],
        ),
        config.CHAT_EVIDENCE_TEMPLATE.format(
            sentence_count=len(review["evidence"]),
            sentence_types=sentence_types,
            flag_count=len(review["disagreements"]),
        ),
    ]
    if review.get("decision") is None:
        lines.append(
            config.CHAT_AWAITING_DECISION_TEMPLATE.format(
                recommended_decision=review["recommended_decision"]
            )
        )
    else:
        lines.append(
            config.CHAT_DECIDED_TEMPLATE.format(
                decided_by=review["decided_by"],
                decided_by_role=review["decided_by_role"],
                decision=review["decision"],
                decision_reason=review["decision_reason"],
            )
        )
    return lines


def answer_application_record(session, signed_in_user, open_applications, question_type,
                              application_reference):
    """A question about one application, answered from the review records by role."""
    role = signed_in_user.get("role")
    advisor = role == config.ROLE_CUSTOMER_SERVICE_ADVISOR
    if not advisor and role not in config.ROLES_SEEING_EVERY_REVIEW:
        raise ValueError(f"The role {role} may not hear about an application from the records")
    if advisor and question_type == config.CHAT_TYPE_OUTCOME_PREDICTION:
        return config.OUTCOME_NOT_PREDICTED_LINE
    if not application_reference:
        return config.CHAT_APPLICATION_NOT_NAMED_MESSAGE
    matching = open_applications[
        open_applications[config.APPLICATION_REFERENCE_COLUMN] == application_reference
    ]
    if len(matching) == 0:
        return config.CHAT_NO_APPLICATION_TEMPLATE.format(
            application_reference=application_reference
        )
    technology = matching.iloc[0][config.TECHNOLOGY_COLUMN]
    reviews = fetch_review_records(
        session, ApplicationReview.application_reference == application_reference
    )
    if advisor:
        return _advisor_status(reviews[-1] if reviews else None, technology, application_reference)
    if not reviews:
        return config.CHAT_NO_REVIEW_TEMPLATE.format(application_reference=application_reference)
    lines = []
    for review in reviews:
        lines.extend(_team_lines(review))
    return "\n".join(lines)


def answer_substation_figure(connection_history, substation_reference, technology):
    """A substation figure, given only where enough premises make it up."""
    if not substation_reference or not technology:
        return config.CHAT_SUBSTATION_NOT_NAMED_MESSAGE
    rows = connection_history[
        (connection_history[config.SUBSTATION_REFERENCE_COLUMN] == substation_reference)
        & (connection_history[config.TECHNOLOGY_COLUMN] == technology)
    ]
    premises_count = int(rows[config.PREMISES_REFERENCE_COLUMN].dropna().nunique())
    if premises_count < config.GROUP_SIZE_MINIMUM:
        return config.GROUP_SIZE_LINE
    return config.CHAT_SUBSTATION_FIGURE_TEMPLATE.format(
        technology_plural=config.TECHNOLOGY_PLURALS[technology],
        premises_count=premises_count,
        substation_reference=substation_reference,
    )
