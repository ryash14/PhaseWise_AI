"""What has been reviewed and decided, the record behind each review, and every chat turn."""

import streamlit as st

from config import config
from dashboard.api_client import apply_page_style, call_service, page_heading, show_badges


def _label(column_name):
    return config.FORM_ANSWER_LABELS.get(column_name, column_name.replace("_", " "))


def _reviews_tab():
    statuses = st.multiselect(
        "Statuses",
        config.REVIEW_STATUS_OPTIONS,
        default=config.DECIDED_REVIEW_STATUSES,
        format_func=lambda status: config.REVIEW_STATUS_LABELS[status],
    )
    if not statuses:
        st.info("Choose at least one status.")
        return
    reviews = call_service("GET", "/reviews", query={"status_value": statuses})
    if not reviews:
        st.info("No review has these statuses.")
        return
    st.dataframe(
        [
            {
                "Application": review["application_reference"],
                "Technology": config.TECHNOLOGY_LABELS[review["technology"]],
                "Status": config.REVIEW_STATUS_LABELS[review["status"]],
                "Opened by": review["coordinator_id"],
                "Decided by": review["decided_by"] or "-",
                "Model calls": review["llm_call_count"],
            }
            for review in reviews
        ],
        hide_index=True,
        use_container_width=True,
    )
    chosen = {review["review_id"]: review for review in reviews}
    review = chosen[
        st.selectbox(
            "Review",
            list(chosen),
            format_func=lambda review_id: f"{review_id} · {chosen[review_id]['application_reference']}",
        )
    ]
    show_badges(
        [
            (config.REVIEW_STATUS_LABELS[review["status"]], config.STATUS_BADGE_COLOURS[review["status"]]),
            (review["assessment"], config.DECISION_BADGE_COLOURS[review["assessment"]]),
            (review["standard_document"], config.NEUTRAL_BADGE_COLOUR),
        ]
    )
    st.markdown(f"**Recommendation:** {review['recommended_decision']}  \n{review['duration_text']}")
    if review["decision"]:
        st.markdown(
            f"**Decision:** {review['decision']} by {review['decided_by']} "
            f"({review['decided_by_role']}) - {review['decision_reason']}"
        )
    with st.expander("Each agent's write-up"):
        for key in ["review_plan_text", "requirements_analysis_text", "evidence_review_text",
                    "prediction_analysis_text", "recommendation_text"]:
            st.markdown(f"**{key.replace('_text', '').replace('_', ' ').title()}**")
            st.text(review[key])
    if review["installer_notice_text"]:
        kind = config.NOTICE_KINDS[review["decision"]]
        with st.expander(kind.capitalize(), expanded=True):
            st.text(review["installer_notice_text"])
    if review["household_notice_text"]:
        with st.expander("Household notice", expanded=True):
            st.text(review["household_notice_text"])
    if review["assessment_brief"]:
        brief = review["assessment_brief"]
        with st.expander("Assessment brief", expanded=True):
            st.dataframe(
                [{"Answer": _label(column), "On the form": str(brief.get(column))}
                 for column in config.ASSESSMENT_BRIEF_DETAIL_COLUMNS],
                hide_index=True, use_container_width=True,
            )
            st.json({key: brief[key] for key in ["requirements", "network_triggers",
                                                 "flagged_statements", "network_work_likelihood",
                                                 "likelihood_band", "expected_working_days",
                                                 "planned_working_days", "delay_expected"]})
    budget = call_service("GET", f"/reviews/{review['review_id']}/calls")
    seconds = budget["total_latency_milliseconds"] / config.MILLISECONDS_PER_SECOND
    st.markdown(
        f"**Call budget:** {budget['call_count']} of {budget['expected_call_count']} calls · "
        f"{budget['total_tokens']:,} tokens · {seconds:.{config.LATENCY_SECONDS_DECIMALS}f} s"
    )
    st.dataframe(budget["calls"], hide_index=True, use_container_width=True)


def _chat_tab():
    turns = call_service("GET", "/audit/chat-turns", query={"turn_limit": config.CHAT_AUDIT_MAX_ROWS})
    if not turns:
        st.info("Nobody has asked the chat anything yet.")
        return
    st.dataframe(
        [
            {
                "Asked by": turn["username"],
                "Role": turn["user_role"],
                "Type": turn["question_type"],
                "Application": turn["application_reference"] or "-",
                "Substation": turn["substation_reference"] or "-",
                "Refused": "Yes" if turn["was_refused"] else "No",
                "Question": turn["question_text"],
                "Answer": turn["answer_text"],
                "Sources": ", ".join(turn["source_documents"]),
            }
            for turn in turns
        ],
        hide_index=True,
        use_container_width=True,
    )


def render_audit_trail_page():
    """Reviews by status with their record and cost, and the recent chat turns."""
    apply_page_style()
    page_heading(config.PAGE_AUDIT, "Every review, decision, model call and chat turn on record.")
    reviews_tab, chat_tab = st.tabs(["Reviews", "Chat turns"])
    with reviews_tab:
        _reviews_tab()
    with chat_tab:
        _chat_tab()
