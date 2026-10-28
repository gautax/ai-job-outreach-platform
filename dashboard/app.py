import streamlit as st


st.set_page_config(
    page_title="Job Outreach Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)


opportunities_page = st.Page(
    "opportunities.py",
    title="Active Opportunities",
    icon="💼",
    default=True,
)

manual_outreach_page = st.Page(
    "manual_outreach.py",
    title="Manual Outreach",
    icon="🧭",
)

processed_page = st.Page(
    "processed.py",
    title="Processed",
    icon="✅",
)

follow_ups_page = st.Page(
    "follow_ups.py",
    title="Follow-ups",
    icon="⏰",
)

replies_page = st.Page(
    "replies.py",
    title="Replies",
    icon="📨",
)


navigation = st.navigation(
    [
        opportunities_page,
        manual_outreach_page,
        processed_page,
        follow_ups_page,
        replies_page,
    ],
    position="sidebar",
)

navigation.run()
