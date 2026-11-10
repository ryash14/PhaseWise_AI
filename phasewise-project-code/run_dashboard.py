"""Entry point 6: the dashboard's front door - the service check, signing in and navigation.

Run from the Project folder:  python -m streamlit run run_dashboard.py   (port 8080)
"""

import httpx
import streamlit as st

from config import config
from dashboard.api_client import SESSION_USER_KEY, call_service, signed_in_user
from dashboard.application_detail import render_application_detail_page
from dashboard.application_queue import render_application_queue_page
from dashboard.audit_trail import render_audit_trail_page
from dashboard.connection_chat import render_connection_chat_page
from dashboard.decision_queue import render_decision_queue_page
from dashboard.sign_in import render_sign_in_page

PAGE_RENDERERS = {
    config.PAGE_QUEUE: render_application_queue_page,
    config.PAGE_DETAIL: render_application_detail_page,
    config.PAGE_DECISION: render_decision_queue_page,
    config.PAGE_AUDIT: render_audit_trail_page,
    config.PAGE_CHAT: render_connection_chat_page,
}
PAGE_ICONS = {
    config.PAGE_QUEUE: ":material/format_list_numbered:",
    config.PAGE_DETAIL: ":material/description:",
    config.PAGE_DECISION: ":material/gavel:",
    config.PAGE_AUDIT: ":material/history:",
    config.PAGE_CHAT: ":material/forum:",
}
PAGE_URL_PATHS = {
    config.PAGE_QUEUE: "queue",
    config.PAGE_DETAIL: "detail",
    config.PAGE_DECISION: "decisions",
    config.PAGE_AUDIT: "audit",
    config.PAGE_CHAT: "chat",
}


def _service_answers():
    try:
        httpx.get(config.API_BASE_URL + "/docs", timeout=5)
        return True
    except httpx.HTTPError:
        return False


def main():
    """Draw only the pages the signed-in person's role is offered."""
    st.set_page_config(page_title=config.DASHBOARD_TITLE, layout="wide")
    st.markdown(config.DASHBOARD_PAGE_STYLE, unsafe_allow_html=True)
    if not _service_answers():
        st.error(
            f"The service is not answering at {config.API_BASE_URL}. Start it from the Project "
            "folder with: python run_api_service.py"
        )
        return
    user = signed_in_user()
    if user is None:
        render_sign_in_page()
        return
    with st.sidebar:
        st.markdown(f"**{user['display_name']}**  \n{user['role']}")
        if st.button("Sign out", use_container_width=True):
            call_service("POST", "/auth/signout")
            st.session_state.pop(SESSION_USER_KEY, None)
            st.rerun()
    pages = [
        st.Page(
            PAGE_RENDERERS[name],
            title=name,
            icon=PAGE_ICONS[name],
            url_path=PAGE_URL_PATHS[name],
            default=(position == 0),
        )
        for position, name in enumerate(user["pages"])
    ]
    st.navigation(pages).run()


if __name__ == "__main__":
    main()
