"""The sign-in page."""

import httpx
import streamlit as st

from config import config
from dashboard.api_client import (
    SESSION_ENDED_KEY,
    SESSION_USER_KEY,
    apply_page_style,
)


def render_sign_in_page():
    """Let a person sign in; the service decides who they are and what they may reach."""
    apply_page_style()
    _, middle, _ = st.columns([1, 1.2, 1])
    with middle:
        st.markdown(
            f'<div style="margin-top:8vh" class="pw-title">{config.DASHBOARD_TITLE}</div>'
            f'<div class="pw-sub">{config.DASHBOARD_SUBTITLE}</div>',
            unsafe_allow_html=True,
        )
        if st.session_state.pop(SESSION_ENDED_KEY, False):
            st.warning(config.SESSION_ENDED_MESSAGE)
        with st.form("sign_in_form", border=True):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            try:
                with httpx.Client(
                    base_url=config.API_BASE_URL, timeout=config.API_REQUEST_TIMEOUT_SECONDS
                ) as client:
                    reply = client.post(
                        "/auth/signin",
                        json={"username": username.strip(), "password": password},
                    )
            except httpx.HTTPError:
                st.error(
                    f"The service is not answering at {config.API_BASE_URL}. Start it with: "
                    "python run_api_service.py"
                )
                return
            if reply.status_code == 200:
                st.session_state[SESSION_USER_KEY] = reply.json()
                st.rerun()
            else:
                try:
                    st.error(reply.json().get("detail"))
                except ValueError:
                    st.error(f"{reply.status_code}: {reply.text}")
