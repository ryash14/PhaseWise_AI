"""Every request the dashboard sends goes through call_service; the shared look lives here too.

No page holds an address, a timeout or a session token.
"""

import html

import httpx
import streamlit as st

from config import config

SESSION_USER_KEY = "signed_in_user"
SESSION_ENDED_KEY = "session_ended"

BADGE_STYLES = {
    "green": ("#E7F4EC", "#1E6B3A"),
    "orange": ("#FDF0E1", "#9A5B13"),
    "violet": ("#F0EBFB", "#5B3BA8"),
    "blue": ("#E6F0FB", "#1F5FA8"),
    "red": ("#FCE9E8", "#A3302A"),
    "yellow": ("#FBF5DC", "#7D6510"),
    "gray": ("#EFEFEC", "#55554F"),
    "primary": ("#E8EEFB", "#2E4FA0"),
}

PAGE_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea, select {
  font-family: 'Archivo', 'Archivo Fallback', system-ui, sans-serif;
}
.stApp { background: #F7F6F2; }
.block-container { padding-top: 2rem; max-width: 1280px; }
.pw-card { background: #FFFFFF; border: 1px solid #E7E5DF; border-radius: 14px;
  padding: 18px 20px; height: 100%; }
.pw-card-head { display: flex; align-items: center; gap: 10px; color: #4B4A45;
  font-size: 0.95rem; font-weight: 500; }
.pw-chip { width: 30px; height: 30px; border-radius: 8px; display: inline-flex;
  align-items: center; justify-content: center; font-size: 15px; }
.pw-value { font-size: 2rem; font-weight: 700; color: #1C1B18; margin: 10px 0 4px; }
.pw-caption { color: #6B6A63; font-size: 0.88rem; line-height: 1.35; }
.pw-badge { display: inline-block; padding: 2px 10px; border-radius: 999px;
  font-size: 0.78rem; font-weight: 600; margin: 0 6px 6px 0; letter-spacing: 0.01em; }
.pw-title { font-size: 1.6rem; font-weight: 700; color: #1C1B18; margin-bottom: 0; }
.pw-sub { color: #6B6A63; margin-top: 2px; margin-bottom: 18px; }
.pw-row { background: #FFFFFF; border: 1px solid #E7E5DF; border-radius: 12px;
  padding: 12px 16px; margin-bottom: 8px; }
.pw-flag { background: #FCE9E8; border-left: 3px solid #A3302A; }
</style>
"""


def apply_page_style():
    """The dashboard's shared look, drawn once per page."""
    st.markdown(PAGE_STYLE, unsafe_allow_html=True)


def badge_html(text, colour):
    background, foreground = BADGE_STYLES.get(colour, BADGE_STYLES["gray"])
    return (
        f'<span class="pw-badge" style="background:{background};color:{foreground}">'
        f"{html.escape(str(text))}</span>"
    )


def show_badges(pairs):
    """Draw a row of (text, colour) badges."""
    st.markdown("".join(badge_html(text, colour) for text, colour in pairs), unsafe_allow_html=True)


def stat_card(icon, label, value, caption, colour="gray"):
    """One white card: an icon chip, a label, a big figure and a caption."""
    background, foreground = BADGE_STYLES.get(colour, BADGE_STYLES["gray"])
    st.markdown(
        f'<div class="pw-card"><div class="pw-card-head"><span class="pw-chip" '
        f'style="background:{background};color:{foreground}">{icon}</span>'
        f"{html.escape(str(label))}</div><div class=\"pw-value\">{html.escape(str(value))}</div>"
        f'<div class="pw-caption">{html.escape(str(caption))}</div></div>',
        unsafe_allow_html=True,
    )


def page_heading(title, subtitle):
    st.markdown(
        f'<div class="pw-title">{html.escape(title)}</div>'
        f'<div class="pw-sub">{html.escape(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def signed_in_user():
    """The signed-in person's sign-in reply, or None."""
    return st.session_state.get(SESSION_USER_KEY)


def _end_session():
    st.session_state.pop(SESSION_USER_KEY, None)
    st.session_state[SESSION_ENDED_KEY] = True


def _send(method, path, query, payload, headers):
    with httpx.Client(
        base_url=config.API_BASE_URL, timeout=config.API_REQUEST_TIMEOUT_SECONDS
    ) as client:
        return client.request(method, path, params=query, json=payload, headers=headers)


def call_service(method, path, query=None, payload=None, waiting_message=None):
    """Make one call to the service and give the page back its reply."""
    headers = {}
    user = signed_in_user()
    if user is not None:
        headers[config.SESSION_TOKEN_HEADER] = user["session_token"]
    if waiting_message:
        try:
            spinner = st.spinner(waiting_message, show_time=True)
        except TypeError:
            spinner = st.spinner(waiting_message)
        with spinner:
            reply = _send(method, path, query, payload, headers)
    else:
        reply = _send(method, path, query, payload, headers)
    if reply.status_code == 401 and user is not None:
        _end_session()
        st.rerun()
    if reply.status_code >= 400:
        try:
            detail = reply.json().get("detail")
        except ValueError:
            detail = None
        if isinstance(detail, list):
            detail = "; ".join(str(item.get("msg", item)) for item in detail)
        st.error(detail if detail else f"{reply.status_code}: {reply.text}")
        st.stop()
    return reply.json()
