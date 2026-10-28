from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st


st.set_page_config(
    page_title="Processed | Job Outreach Dashboard",
    page_icon="✅",
    layout="wide",
)


API_URL = os.getenv("N8N_API_URL", "").strip()
API_KEY = os.getenv("DASHBOARD_API_KEY", "").strip()


def clean(value: Any) -> str:
    return str(value or "").strip()


def upper(value: Any) -> str:
    return clean(value).upper()


@st.cache_data(ttl=30, show_spinner=False)
def load_opportunities(api_url: str, api_key: str) -> dict[str, Any]:
    response = requests.get(
        api_url,
        headers={"X-Dashboard-Key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, list):
        if len(payload) != 1 or not isinstance(payload[0], dict):
            raise ValueError("The n8n API returned an unexpected array.")
        payload = payload[0]

    if not isinstance(payload, dict) or not payload.get("success"):
        raise ValueError("The n8n API returned an unsuccessful response.")

    return payload


def is_processed(opportunity: dict[str, Any]) -> bool:
    return bool(
        clean(opportunity.get("sent_at"))
        or upper(opportunity.get("outreach_status")) in {"SENT", "REPLIED"}
        or upper(opportunity.get("response_status")) == "REPLIED"
        or upper(opportunity.get("application_status")) == "SKIPPED"
    )


def processed_label(opportunity: dict[str, Any]) -> str:
    if (
        upper(opportunity.get("response_status")) == "REPLIED"
        or clean(opportunity.get("reply_detected_at"))
    ):
        return "📨 Reply received"

    if clean(opportunity.get("sent_at")) or upper(
        opportunity.get("outreach_status")
    ) == "SENT":
        return "🟢 Outreach sent"

    if upper(opportunity.get("application_status")) == "SKIPPED":
        return "⚫ Skipped"

    return "✅ Processed"


def sort_timestamp(opportunity: dict[str, Any]) -> str:
    return (
        clean(opportunity.get("reply_detected_at"))
        or clean(opportunity.get("sent_at"))
        or clean(opportunity.get("last_updated"))
    )


st.title("✅ Processed Opportunities")
st.caption(
    "Items leave the Active Opportunities page after outreach is sent or "
    "after you skip them. The Google Sheets rows are not moved or deleted."
)

refresh_column, spacer_column = st.columns([1, 5])
with refresh_column:
    if st.button("Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

if not API_URL:
    st.error("N8N_API_URL is missing from the container environment.")
    st.stop()

if not API_KEY:
    st.error("DASHBOARD_API_KEY is missing from the container environment.")
    st.stop()

try:
    data = load_opportunities(API_URL, API_KEY)
except requests.exceptions.RequestException as error:
    st.error("The Processed page could not connect to the n8n API.")
    st.code(str(error))
    st.stop()
except ValueError as error:
    st.error("The n8n API returned an invalid response.")
    st.code(str(error))
    st.stop()

processed = [
    item
    for item in data.get("opportunities", [])
    if is_processed(item)
]
processed.sort(key=sort_timestamp, reverse=True)

sent_count = sum(
    bool(clean(item.get("sent_at")))
    or upper(item.get("outreach_status")) == "SENT"
    for item in processed
)
skipped_count = sum(
    upper(item.get("application_status")) == "SKIPPED"
    for item in processed
)
reply_count = sum(
    upper(item.get("response_status")) == "REPLIED"
    or bool(clean(item.get("reply_detected_at")))
    for item in processed
)

metric_columns = st.columns(4)
metric_columns[0].metric("Processed", len(processed))
metric_columns[1].metric("Outreach sent", sent_count)
metric_columns[2].metric("Skipped", skipped_count)
metric_columns[3].metric("Replies", reply_count)

st.divider()

available_countries = sorted(
    {
        clean(item.get("country"))
        for item in processed
        if clean(item.get("country"))
    }
)
available_results = sorted({processed_label(item) for item in processed})

country_column, result_column = st.columns(2)
selected_countries = country_column.multiselect(
    "Countries",
    options=available_countries,
    default=available_countries,
)
selected_results = result_column.multiselect(
    "Result",
    options=available_results,
    default=available_results,
)

filtered = [
    item
    for item in processed
    if clean(item.get("country")) in selected_countries
    and processed_label(item) in selected_results
]

st.subheader(f"Processed records ({len(filtered)})")

if not filtered:
    st.info("No processed opportunities match the selected filters.")

for opportunity in filtered:
    company = clean(opportunity.get("company_name")) or "Unknown company"
    position = clean(opportunity.get("position_title")) or "Unknown opportunity"
    country = clean(opportunity.get("country"))
    result = processed_label(opportunity)
    sent_at = clean(opportunity.get("sent_at"))
    contact_name = clean(opportunity.get("contact_name"))
    contact_email = clean(opportunity.get("contact_email"))
    destination_url = clean(opportunity.get("vacancy_url"))
    email_subject = clean(opportunity.get("email_subject"))
    email_draft = clean(opportunity.get("email_draft"))
    notes = clean(opportunity.get("notes"))
    opportunity_type = upper(opportunity.get("opportunity_type"))
    is_speculative = (
        opportunity_type == "SPECULATIVE_OUTREACH"
        or clean(opportunity.get("opportunity_key")).lower().endswith(
            "::speculative"
        )
    )

    with st.container(border=True):
        title_column, status_column = st.columns([5, 1])
        with title_column:
            st.subheader(company)
            st.write(f"**{position}**")
            st.caption(" · ".join(part for part in [country, result] if part))

        with status_column:
            st.metric("Fit score", opportunity.get("qualification_score", 0))

        detail_parts = []
        if sent_at:
            detail_parts.append(f"Sent: {sent_at}")
        if contact_name:
            detail_parts.append(f"Contact: {contact_name}")
        if contact_email:
            detail_parts.append(contact_email)

        if detail_parts:
            st.caption(" · ".join(detail_parts))

        if destination_url:
            st.link_button(
                "Open company / careers page" if is_speculative else "Open vacancy",
                destination_url,
                use_container_width=True,
            )

        if email_subject or email_draft or notes:
            with st.expander("Review saved details"):
                if email_subject:
                    st.write(f"**Email subject:** {email_subject}")
                if email_draft:
                    st.text_area(
                        "Email draft",
                        value=email_draft,
                        height=240,
                        disabled=True,
                        key=f"processed_email_{clean(opportunity.get('opportunity_key'))}",
                    )
                if notes:
                    st.write(f"**Notes:** {notes}")
