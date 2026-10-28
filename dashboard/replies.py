import os

import requests
import streamlit as st


st.set_page_config(
    page_title="Replies | Job Outreach Dashboard",
    page_icon="📨",
    layout="wide",
)


def clean(value):
    return str(value or "").strip()


@st.cache_data(
    ttl=30,
    show_spinner=False,
)
def load_opportunities(
    api_url,
    api_key,
):
    response = requests.get(
        api_url,
        headers={
            "X-Dashboard-Key": api_key,
        },
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    if not payload.get("success"):
        raise RuntimeError(
            "The dashboard API returned an "
            "unsuccessful response."
        )

    return payload


API_URL = clean(
    os.environ.get("N8N_API_URL")
)

API_KEY = clean(
    os.environ.get("DASHBOARD_API_KEY")
)


st.title("Replies")

st.caption(
    "Replies detected automatically from monitored "
    "Gmail outreach threads."
)


refresh_column, spacer_column = st.columns(
    [1, 5]
)

with refresh_column:
    if st.button(
        "Refresh",
        use_container_width=True,
    ):
        st.cache_data.clear()
        st.rerun()


if not API_URL:
    st.error(
        "N8N_API_URL is missing from the "
        "container environment."
    )
    st.stop()


if not API_KEY:
    st.error(
        "DASHBOARD_API_KEY is missing from the "
        "container environment."
    )
    st.stop()


try:
    data = load_opportunities(
        API_URL,
        API_KEY,
    )

except requests.exceptions.RequestException as error:
    st.error(
        "The Replies page could not connect "
        "to the n8n API."
    )

    st.code(str(error))
    st.stop()

except (
    ValueError,
    RuntimeError,
) as error:
    st.error(
        "The n8n API returned an invalid response."
    )

    st.code(str(error))
    st.stop()


opportunities = data.get(
    "opportunities",
    [],
)


replied_campaigns = [
    opportunity
    for opportunity in opportunities
    if (
        clean(
            opportunity.get("response_status")
        ).upper()
        == "REPLIED"
        or clean(
            opportunity.get("reply_detected_at")
        )
    )
]


replied_campaigns.sort(
    key=lambda opportunity: clean(
        opportunity.get("reply_detected_at")
    ),
    reverse=True,
)


company_count = len(
    {
        clean(
            opportunity.get("company_domain")
        ).lower()
        or clean(
            opportunity.get("company_name")
        ).lower()
        for opportunity in replied_campaigns
        if (
            clean(
                opportunity.get("company_domain")
            )
            or clean(
                opportunity.get("company_name")
            )
        )
    }
)


metric_1, metric_2 = st.columns(2)

metric_1.metric(
    "Replies detected",
    len(replied_campaigns),
)

metric_2.metric(
    "Companies",
    company_count,
)


st.divider()


if not replied_campaigns:
    st.info(
        "No outreach replies have been detected yet."
    )


for opportunity in replied_campaigns:
    company_name = (
        clean(
            opportunity.get("company_name")
        )
        or "Unknown company"
    )

    position_title = (
        clean(
            opportunity.get("position_title")
        )
        or "General company outreach"
    )

    contact_name = clean(
        opportunity.get("contact_name")
    )

    contact_email = clean(
        opportunity.get("contact_email")
    )

    reply_from = clean(
        opportunity.get("reply_from")
    )

    reply_subject = clean(
        opportunity.get("reply_subject")
    )

    reply_snippet = clean(
        opportunity.get("reply_snippet")
    )

    reply_detected_at = clean(
        opportunity.get("reply_detected_at")
    )

    gmail_thread_id = clean(
        opportunity.get("gmail_thread_id")
    )


    with st.container(border=True):
        st.markdown(
            f"### {company_name}"
        )

        st.write(
            f"**Outreach context:** {position_title}"
        )

        contact_parts = [
            part
            for part in [
                contact_name,
                contact_email,
            ]
            if part
        ]

        if contact_parts:
            st.caption(
                "Original contact: "
                + " · ".join(contact_parts)
            )

        if reply_from:
            st.write(
                f"**Reply from:** {reply_from}"
            )

        if reply_subject:
            st.write(
                f"**Subject:** {reply_subject}"
            )

        if reply_snippet:
            st.info(
                reply_snippet
            )

        if reply_detected_at:
            st.caption(
                "Detected at: "
                + reply_detected_at
            )

        if gmail_thread_id:
            gmail_url = (
                "https://mail.google.com/mail/u/0/"
                f"#all/{gmail_thread_id}"
            )

            st.link_button(
                "Open Gmail thread",
                gmail_url,
                use_container_width=True,
            )
