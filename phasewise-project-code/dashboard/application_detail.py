"""Everything established about one application, and the form that opens its review."""

import streamlit as st

from config import config
from dashboard.api_client import (
    apply_page_style,
    badge_html,
    call_service,
    page_heading,
    show_badges,
    stat_card,
)
from dashboard.application_queue import SELECTED_KEY


def _label(column_name):
    return config.FORM_ANSWER_LABELS.get(column_name, column_name.replace("_", " "))


def _value(value):
    return config.NOT_GIVEN_TEXT if value is None else value


def _screening_tab(screening):
    for requirement in screening["requirements"]:
        colour = config.REQUIREMENT_RESULT_BADGE_COLOURS[requirement["result"]]
        blanks = ""
        if requirement["blank_answers"]:
            blanks = "<br><small>Left blank: " + ", ".join(
                _label(column) for column in requirement["blank_answers"]
            ) + "</small>"
        st.markdown(
            f'<div class="pw-row">{badge_html(requirement["result"], colour)}'
            f"<b>{requirement['requirement_name']}</b><br>"
            f"<small>{requirement['requirement_sentence']}</small>{blanks}</div>",
            unsafe_allow_html=True,
        )
    if not screening["rating_stated"]:
        rating_column = config.RATING_COLUMNS[screening["technology"]]
        st.warning(f"The {config.RATING_TERMS[rating_column]} is blank.")
    st.markdown("**Decisions open**")
    show_badges(
        [(decision, config.DECISION_BADGE_COLOURS[decision]) for decision in screening["decisions_open"]]
    )
    st.markdown("**Network triggers**")
    if screening["network_triggers"]:
        show_badges([(trigger, "violet") for trigger in screening["network_triggers"]])
    else:
        st.caption("No network trigger applies.")


def _evidence_tab(detail):
    if not detail["application_documents"]:
        st.info("No statement is attached.")
        return
    flags = {flag["sentence"]: flag for flag in detail["disagreements"]}
    current = None
    for finding in detail["evidence_findings"]:
        if finding["document_id"] != current:
            current = finding["document_id"]
            st.markdown(f"#### {current} · {finding['document_type']}")
        borne = ", ".join(finding["requirements_borne_on"]) or "none"
        flag = flags.get(finding["sentence"])
        extra = ""
        css = "pw-row"
        if flag is not None:
            css += " pw-flag"
            stated = ", ".join(f"{amps:.{config.AMPS_DECIMALS}f}" for amps in flag["stated_amps"])
            form = ", ".join(
                f"{amps:.{config.AMPS_DECIMALS}f}" for amps in flag["form_rating_amps"]
            ) or "none"
            extra = (
                f"<br>{badge_html(flag['flag'], config.DELAY_COLOUR)}"
                f"<small>States {stated} A per phase; the form's ratings: {form}</small>"
            )
        st.markdown(
            f'<div class="{css}">{badge_html(finding["sentence_type"], config.SENTENCE_TYPE_BADGE_COLOUR)}'
            f"{finding['sentence']}<br><small>Bears on: {borne}</small>{extra}</div>",
            unsafe_allow_html=True,
        )


def _form_tab(detail):
    application = detail["application"]
    screening = detail["screening"]
    technology = screening["technology"]
    shown = []
    rows = []
    for requirement in screening["requirements"]:
        for column in config.REQUIREMENT_ANSWER_COLUMNS[requirement["requirement_kind"]]:
            if column not in shown:
                shown.append(column)
                rows.append((_label(column), _value(application.get(column)),
                             requirement["requirement_name"]))
    rating_column = config.RATING_COLUMNS[technology]
    if rating_column not in shown:
        shown.append(rating_column)
        rows.append((_label(rating_column), _value(application.get(rating_column)), "The rating"))
    trigger_columns = list(config.SUPPLY_TRIGGER_ANSWER_COLUMNS)
    if technology in config.GENERATING_TECHNOLOGIES:
        trigger_columns += config.GENERATION_TRIGGER_ANSWER_COLUMNS
    for column in trigger_columns:
        if column not in shown:
            shown.append(column)
            rows.append((_label(column), _value(application.get(column)), "Network triggers"))
    st.dataframe(
        [{"Answer": label, "On the form": str(value), "Used for": use} for label, value, use in rows],
        hide_index=True,
        use_container_width=True,
    )


def _review_tab(reference, reviews):
    if reviews:
        review = reviews[-1]
        show_badges(
            [
                (config.REVIEW_STATUS_LABELS[review["status"]],
                 config.STATUS_BADGE_COLOURS[review["status"]]),
                (review["recommended_decision"],
                 config.DECISION_BADGE_COLOURS[review["recommended_decision"]]),
            ]
        )
        st.markdown(review["recommendation_text"])
        return
    with st.form("open_review_form"):
        request_text = st.text_area(
            "What should the review look at?",
            max_chars=config.COORDINATOR_REQUEST_MAXIMUM_CHARACTERS,
            placeholder="Are the requirements met on the form, and does any statement disagree?",
        )
        submitted = st.form_submit_button("Open the review", type="primary")
    if submitted:
        if len(request_text.strip()) < config.COORDINATOR_REQUEST_MINIMUM_CHARACTERS:
            st.warning(
                f"Write at least {config.COORDINATOR_REQUEST_MINIMUM_CHARACTERS} characters."
            )
            return
        review = call_service(
            "POST",
            "/reviews",
            payload={"application_reference": reference, "coordinator_request": request_text},
            waiting_message=(
                f"{config.LLM_CALLS_BEFORE_DECISION} model calls are being made for {reference}"
            ),
        )
        st.success(
            f"The review of {reference} is waiting for a Connections Engineer. It recommends "
            f"{review['recommended_decision']}."
        )
        st.markdown(review["recommendation_text"])


def render_application_detail_page():
    """One application: headline, counts and the four tabs."""
    apply_page_style()
    queue = call_service("GET", "/queue", query={"technology": config.QUEUE_TECHNOLOGY_ALL})
    references = [row["application_reference"] for row in queue]
    if not references:
        st.info("The queue is empty.")
        return
    remembered = st.session_state.get(SELECTED_KEY)
    index = references.index(remembered) if remembered in references else 0
    reference = st.selectbox("Application", references, index=index)
    st.session_state[SELECTED_KEY] = reference
    detail = call_service("GET", f"/queue/{reference}")
    reviews = [
        review
        for review in call_service(
            "GET", "/reviews", query={"status_value": config.REVIEW_STATUS_OPTIONS}
        )
        if review["application_reference"] == reference
    ]
    application = detail["application"]
    screening = detail["screening"]
    technology = screening["technology"]
    page_heading(
        f"{reference} · {config.TECHNOLOGY_LABELS[technology]}",
        f"{_value(application.get(config.REGION_TYPE_COLUMN))} · substation "
        f"{_value(application.get(config.SUBSTATION_REFERENCE_COLUMN))} · "
        f"{_value(application.get(config.SOURCE_PORTAL_COLUMN))} · revision "
        f"{_value(application.get(config.REVISION_NUMBER_COLUMN))} · {screening['standard_document']}",
    )
    badges = []
    if technology == config.HEAT_PUMP and application.get(config.URGENCY_COLUMN) == config.URGENCY_HEATING_FAILED:
        badges.append((config.URGENCY_HEATING_FAILED, config.HEATING_FAILED_BADGE_COLOUR))
    badges.append((screening["assessment"], config.DECISION_BADGE_COLOURS[screening["assessment"]]))
    badges.append((f"Queue position {detail['queue_position']}", config.NEUTRAL_BADGE_COLOUR))
    if reviews:
        status = reviews[-1]["status"]
        badges.append((config.REVIEW_STATUS_LABELS[status], config.STATUS_BADGE_COLOURS[status]))
    show_badges(badges)
    total = len(screening["requirements"])
    columns = st.columns(4)
    with columns[0]:
        stat_card("✓", "Requirements met", f"{screening[config.REQUIREMENTS_MET_COUNT_COLUMN]} of {total}",
                  f"{screening[config.REQUIREMENTS_NOT_MET_COUNT_COLUMN]} not met, "
                  f"{screening[config.REQUIREMENTS_NOT_DOCUMENTED_COUNT_COLUMN]} not documented", "green")
    with columns[1]:
        stat_card("⚡", "Network triggers", len(screening["network_triggers"]),
                  ", ".join(screening["network_triggers"]) or "None applies", "violet")
    with columns[2]:
        likelihood = detail["likelihood"]
        stat_card("%", "Network work likelihood",
                  f"{likelihood['network_work_likelihood']:.{config.LIKELIHOOD_DECIMALS}f}",
                  f"Band {likelihood['likelihood_band']}",
                  config.LIKELIHOOD_BAND_BADGE_COLOURS[likelihood["likelihood_band"]])
    with columns[3]:
        duration = detail["duration"]
        planned = duration["planned_working_days"]
        stat_card("⏱", "Expected working days", duration["expected_working_days"],
                  "No plan given" if planned is None else f"Against {planned} planned",
                  config.DELAY_COLOUR if duration["delay_expected"] else config.NEUTRAL_BADGE_COLOUR)
    st.write("")
    screening_tab, evidence_tab, form_tab, review_tab = st.tabs(
        ["Screening", "Statement evidence", "Form", "Review"]
    )
    with screening_tab:
        _screening_tab(screening)
    with evidence_tab:
        _evidence_tab(detail)
    with form_tab:
        _form_tab(detail)
    with review_tab:
        _review_tab(reference, reviews)
