"""Ask the connection assistant, and see your own conversation."""

import streamlit as st

from config import config
from dashboard.api_client import apply_page_style, call_service, page_heading, show_badges


def render_connection_chat_page():
    """The signed-in person's own conversation, oldest at the top, and the question box."""
    apply_page_style()
    page_heading(config.PAGE_CHAT, "Answers come from Merrowdale's documents and records only.")
    turns = call_service("GET", "/chat/turns", query={"turn_limit": config.CHAT_PAGE_TURN_LIMIT})
    for turn in reversed(turns):
        with st.chat_message("user"):
            st.markdown(turn["question_text"])
        with st.chat_message("assistant"):
            show_badges([(turn["question_type"],
                          config.CHAT_TYPE_BADGE_COLOURS.get(turn["question_type"], "gray"))])
            st.markdown(turn["answer_text"])
            if turn["source_documents"]:
                st.caption("Sources: " + ", ".join(turn["source_documents"]))
    question = st.chat_input(
        "Ask about a standard, the rules, a statement guide or an application",
        max_chars=config.CHAT_QUESTION_MAXIMUM_CHARACTERS,
    )
    if question is not None:
        if len(question.strip()) < config.CHAT_QUESTION_MINIMUM_CHARACTERS:
            st.warning(f"Ask with at least {config.CHAT_QUESTION_MINIMUM_CHARACTERS} characters.")
            return
        call_service(
            "POST", "/chat/ask", payload={"question": question},
            waiting_message="The connection assistant is reading the documents",
        )
        st.rerun()
