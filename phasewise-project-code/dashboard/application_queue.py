"""The open queue, in the order the connections team works it."""

import pandas as pd
import streamlit as st

from config import config
from dashboard.api_client import apply_page_style, call_service, page_heading, stat_card

SELECTED_KEY = "selected_application"


def render_application_queue_page():
    """Counts along the top, a technology filter and the ranked table."""
    apply_page_style()
    page_heading(config.PAGE_QUEUE, "Every open application, heat pumps on failed heating first.")
    everything = call_service("GET", "/queue", query={"technology": config.QUEUE_TECHNOLOGY_ALL})
    heating_failed = sum(
        1
        for row in everything
        if row["technology"] == config.HEAT_PUMP and row["urgency"] == config.URGENCY_HEATING_FAILED
    )
    cards = st.columns(2 + len(config.DECISIONS))
    with cards[0]:
        stat_card("◎", "Open applications", len(everything), "In working order", "green")
    with cards[1]:
        stat_card("♨", "Heating failed", heating_failed, "Moved to the front of the queue", "red")
    for position, decision in enumerate(config.DECISIONS, start=2):
        with cards[position]:
            stat_card(
                "◆",
                decision.title(),
                sum(1 for row in everything if row["assessment"] == decision),
                "Assessed by the screening",
                config.DECISION_BADGE_COLOURS[decision],
            )
    st.write("")
    technology = st.selectbox(
        "Technology",
        config.QUEUE_TECHNOLOGY_OPTIONS,
        format_func=lambda option: config.QUEUE_TECHNOLOGY_LABELS[option],
    )
    rows = call_service("GET", "/queue", query={"technology": technology})
    if not rows:
        st.info("No open application of this technology.")
        return
    table = pd.DataFrame(
        [
            {
                "Position": row["queue_position"],
                "Reference": row["application_reference"],
                "Technology": row["technology_label"],
                "Premises": row["premises_type"],
                "Portal": row["source_portal"],
                "Urgency": row["urgency"],
                "Assessment": row["assessment"],
                "Met": row["requirements_met_count"],
                "Not met": row["requirements_not_met_count"],
                "Not documented": row["requirements_not_documented_count"],
                "Rating stated": "Yes" if row["rating_stated"] else "No",
                "Triggers": row["network_trigger_count"],
                "Likelihood": f"{row['network_work_likelihood']:.{config.LIKELIHOOD_DECIMALS}f}",
                "Expected days": row["expected_working_days"],
                "Delay": {True: "Delay", False: "On plan", None: "No plan"}[row["delay_expected"]],
                "Flags": row["disagreement_count"],
                "Statements": row["document_count"],
            }
            for row in rows
        ]
    )
    picked = st.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
    )
    selected_rows = picked.selection.rows if picked is not None else []
    if selected_rows:
        st.session_state[SELECTED_KEY] = table.iloc[selected_rows[0]]["Reference"]
        st.success(
            f"{st.session_state[SELECTED_KEY]} selected - open {config.PAGE_DETAIL} to see it."
        )
