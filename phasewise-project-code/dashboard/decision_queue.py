"""The reviews waiting at the gate, and the form a Connections Engineer decides with."""

import streamlit as st

from config import config
from dashboard.api_client import (
    apply_page_style,
    badge_html,
    call_service,
    page_heading,
    show_badges,
    signed_in_user,
    stat_card,
)

PENDING_KEY = "pending_decision"


def _label(column_name):
    return config.FORM_ANSWER_LABELS.get(column_name, column_name.replace("_", " "))


def _show_review(review):
    show_badges(
        [
            (f"Recommends {review['recommended_decision']}",
             config.DECISION_BADGE_COLOURS[review["recommended_decision"]]),
            (review["standard_document"], config.NEUTRAL_BADGE_COLOUR),
        ]
    )
    columns = st.columns(2)
    with columns[0]:
        stat_card("%", "Network work likelihood",
                  f"{review['network_work_likelihood']:.{config.LIKELIHOOD_DECIMALS}f}",
                  f"Band {review['likelihood_band']}",
                  config.LIKELIHOOD_BAND_BADGE_COLOURS[review["likelihood_band"]])
    with columns[1]:
        stat_card("⏱", "Expected working days", review["expected_working_days"],
                  review["duration_text"],
                  config.DELAY_COLOUR if review["delay_expected"] else config.NEUTRAL_BADGE_COLOUR)
    st.markdown("#### Recommendation")
    st.markdown(review["recommendation_text"])
    st.markdown("#### Requirements")
    for requirement in review["requirements"]:
        blanks = ""
        if requirement["blank_answers"]:
            blanks = " · left blank: " + ", ".join(_label(c) for c in requirement["blank_answers"])
        st.markdown(
            f'<div class="pw-row">{badge_html(requirement["result"], config.REQUIREMENT_RESULT_BADGE_COLOURS[requirement["result"]])}'
            f"<b>{requirement['requirement_name']}</b><small>{blanks}</small></div>",
            unsafe_allow_html=True,
        )
    if not review["rating_stated"]:
        st.warning("The rating is blank on the form.")
    st.markdown("#### Network triggers")
    if review["network_triggers"]:
        show_badges([(trigger, "violet") for trigger in review["network_triggers"]])
    else:
        st.caption("None applies.")
    st.markdown("#### Flagged sentences")
    if not review["disagreements"]:
        st.caption("No statement sentence is flagged.")
    for flag in review["disagreements"]:
        st.markdown(
            f'<div class="pw-row pw-flag">{badge_html(flag["flag"], config.DELAY_COLOUR)}'
            f"{flag['sentence']}<br><small>States "
            + ", ".join(f"{a:.{config.AMPS_DECIMALS}f}" for a in flag["stated_amps"])
            + " A; form: "
            + (", ".join(f"{a:.{config.AMPS_DECIMALS}f}" for a in flag["form_rating_amps"]) or "none")
            + "</small></div>",
            unsafe_allow_html=True,
        )
    with st.expander("What was asked, and each agent's write-up"):
        st.markdown(f"**Asked:** {review['coordinator_request']}")
        for title, key in [
            ("Plan", "review_plan_text"),
            ("Requirements", "requirements_analysis_text"),
            ("Evidence", "evidence_review_text"),
            ("Predictions", "prediction_analysis_text"),
        ]:
            st.markdown(f"**{title}**")
            st.text(review[key])


def render_decision_queue_page():
    """List the reviews awaiting a decision and record one."""
    apply_page_style()
    page_heading(config.PAGE_DECISION, "Reviews waiting at the gate for a Connections Engineer.")
    waiting = call_service(
        "GET", "/reviews", query={"status_value": [config.REVIEW_STATUS_AWAITING]}
    )
    if not waiting:
        st.info("Nothing is waiting for a decision.")
        return
    labels = {
        f"{review['application_reference']} · {config.TECHNOLOGY_LABELS[review['technology']]}": review
        for review in waiting
    }
    review = labels[st.selectbox("Review", list(labels))]
    _show_review(review)
    st.divider()
    user = signed_in_user()
    if review["coordinator_id"] == user["username"]:
        st.info(
            "You opened this review, so another Connections Engineer must decide it."
        )
        return
    pending = st.session_state.get(PENDING_KEY, {})
    remembered = pending if pending.get("review_id") == review["review_id"] else {}
    options = review["decisions_open"]
    with st.form("decision_form"):
        decision = st.radio(
            "Decision",
            options,
            index=options.index(remembered["decision"]) if remembered.get("decision") in options else 0,
        )
        reason = st.text_area(
            "Reason",
            value=remembered.get("decision_reason", ""),
            max_chars=config.DECISION_REASON_MAXIMUM_CHARACTERS,
        )
        submitted = st.form_submit_button("Record the decision", type="primary")
    if submitted:
        if len(reason.strip()) < config.DECISION_REASON_MINIMUM_CHARACTERS:
            st.warning(f"Give a reason of at least {config.DECISION_REASON_MINIMUM_CHARACTERS} characters.")
            return
        st.session_state[PENDING_KEY] = {
            "review_id": review["review_id"], "decision": decision, "decision_reason": reason
        }
        decided = call_service(
            "POST",
            f"/reviews/{review['review_id']}/decision",
            payload={"decision": decision, "decision_reason": reason},
            waiting_message=f"Recording {decision} for {review['application_reference']}",
        )
        st.session_state.pop(PENDING_KEY, None)
        st.success(
            f"{review['application_reference']} is {config.REVIEW_STATUS_PHRASES[decided['status']]}: "
            f"{config.DECISION_OUTCOME_TEXTS[decision]}."
        )
