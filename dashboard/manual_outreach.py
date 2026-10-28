from __future__ import annotations

import hashlib
import os
import re
from typing import Any

import requests
import streamlit as st


st.set_page_config(
    page_title="Manual Outreach | Job Outreach Dashboard",
    page_icon="🧭",
    layout="wide",
)


API_URL = os.getenv("N8N_API_URL", "").strip()
ACTION_URL = os.getenv("N8N_ACTION_URL", "").strip()
API_KEY = os.getenv("DASHBOARD_API_KEY", "").strip()

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def clean(value: Any) -> str:
    return str(value or "").strip()


def upper(value: Any) -> str:
    return clean(value).upper()


def widget_key(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


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


def submit_manual_contact(
    action_url: str,
    api_key: str,
    opportunity_key: str,
    contact_name: str,
    contact_role: str,
    contact_email: str,
    contact_linkedin_url: str,
) -> dict[str, Any]:
    response = requests.post(
        action_url,
        headers={"X-Dashboard-Key": api_key},
        json={
            "action": "save_manual_contact",
            "opportunity_key": opportunity_key,
            "contact_name": contact_name,
            "contact_role": contact_role,
            "contact_email": contact_email,
            "contact_linkedin_url": contact_linkedin_url,
        },
        timeout=30,
    )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.status_code >= 400:
        message = clean(payload.get("message"))
        errors = payload.get("errors", [])
        if isinstance(errors, list) and errors:
            message = " ".join(str(error) for error in errors)
        raise RuntimeError(
            message or f"The action failed with HTTP {response.status_code}."
        )

    if not payload.get("success"):
        raise RuntimeError(
            clean(payload.get("message"))
            or "The manual contact was not saved."
        )

    return payload


def strategy_label(opportunity: dict[str, Any]) -> str:
    outreach_mode = upper(opportunity.get("outreach_mode"))
    if outreach_mode == "SPECULATIVE":
        return "Speculative outreach"
    if outreach_mode == "ADJACENT_ROLE":
        return "Adjacent-role outreach"
    if upper(opportunity.get("application_status")) == "APPLIED":
        return "Post-application outreach"
    return outreach_mode or "Outreach"


def is_processed(opportunity: dict[str, Any]) -> bool:
    return bool(
        clean(opportunity.get("sent_at"))
        or upper(opportunity.get("outreach_status")) in {"SENT", "REPLIED"}
        or upper(opportunity.get("response_status")) == "REPLIED"
        or upper(opportunity.get("application_status")) == "SKIPPED"
    )


st.title("🧭 Manual Outreach")
st.caption(
    "Plan B for opportunities where automatic contact research could not find "
    "a sufficiently supported person. Add a contact you found manually; the "
    "existing AI pipeline will then generate the personalized email and/or "
    "LinkedIn drafts using the saved company context."
)

flash_success = st.session_state.pop("manual_flash_success", None)
flash_error = st.session_state.pop("manual_flash_error", None)

if flash_success:
    st.success(flash_success)
if flash_error:
    st.error(flash_error)

refresh_column, spacer_column = st.columns([1, 5])
with refresh_column:
    if st.button("Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

if not API_URL:
    st.error("N8N_API_URL is missing from the container environment.")
    st.stop()
if not ACTION_URL:
    st.error("N8N_ACTION_URL is missing from the container environment.")
    st.stop()
if not API_KEY:
    st.error("DASHBOARD_API_KEY is missing from the container environment.")
    st.stop()

try:
    data = load_opportunities(API_URL, API_KEY)
except requests.exceptions.RequestException as error:
    st.error("The Manual Outreach page could not connect to the n8n API.")
    st.code(str(error))
    st.stop()
except ValueError as error:
    st.error("The n8n API returned an invalid response.")
    st.code(str(error))
    st.stop()

manual_items = [
    item
    for item in data.get("opportunities", [])
    if (
        (
            upper(
                item.get("manual_contact_status")
            ) == "NEEDS_CONTACT"
            or (
                upper(
                    item.get("manual_contact_status")
                ) == "CONTACT_ADDED"
                and not bool(
                    item.get("has_draft")
                )
            )
        )
        and not is_processed(item)
    )
]

available_countries = sorted(
    {
        clean(item.get("country"))
        for item in manual_items
        if clean(item.get("country"))
    }
)
available_strategies = sorted({strategy_label(item) for item in manual_items})

metric_columns = st.columns(3)
metric_columns[0].metric("Needs a contact", len(manual_items))
metric_columns[1].metric(
    "Speculative",
    sum(upper(item.get("outreach_mode")) == "SPECULATIVE" for item in manual_items),
)
metric_columns[2].metric(
    "Applied / adjacent",
    sum(upper(item.get("outreach_mode")) != "SPECULATIVE" for item in manual_items),
)

st.divider()

country_column, strategy_column = st.columns(2)
selected_countries = country_column.multiselect(
    "Countries",
    options=available_countries,
    default=available_countries,
)
selected_strategies = strategy_column.multiselect(
    "Outreach strategy",
    options=available_strategies,
    default=available_strategies,
)

filtered = [
    item
    for item in manual_items
    if clean(item.get("country")) in selected_countries
    and strategy_label(item) in selected_strategies
]

st.subheader(f"Manual contact queue ({len(filtered)})")

if not filtered:
    st.info(
        "No opportunities currently need a manual contact. New failed contact "
        "research runs will appear here automatically."
    )

for opportunity in filtered:
    opportunity_key = clean(opportunity.get("opportunity_key"))
    company_name = clean(opportunity.get("company_name")) or "Unknown company"
    position_title = (
        clean(opportunity.get("position_title")) or "Potential opportunity"
    )
    country = clean(opportunity.get("country"))
    destination_url = clean(opportunity.get("vacancy_url"))
    qualification_reason = clean(opportunity.get("qualification_reason"))
    outreach_angle = clean(opportunity.get("outreach_angle"))
    notes = clean(opportunity.get("notes"))
    strategy = strategy_label(opportunity)
    score = opportunity.get("qualification_score", 0)

    with st.container(border=True):
        title_column, score_column = st.columns([5, 1])
        with title_column:
            st.subheader(company_name)
            st.write(f"**{position_title}**")
            st.caption(" · ".join(part for part in [country, strategy] if part))
        with score_column:
            st.metric("Fit score", score)

        if destination_url:
            st.link_button(
                "Open company / vacancy page",
                destination_url,
                use_container_width=True,
            )

        with st.expander("Company and research context"):
            if qualification_reason:
                st.write("**Why it was selected**")
                st.write(qualification_reason)
            if outreach_angle:
                st.write("**Suggested outreach angle**")
                st.write(outreach_angle)
            if notes:
                st.write("**Automatic contact-research result**")
                st.write(notes)

            automated_contact_parts = [
                clean(opportunity.get("contact_name")),
                clean(opportunity.get("contact_role")),
                clean(opportunity.get("contact_email")),
            ]
            automated_contact_parts = [
                part for part in automated_contact_parts if part
            ]
            automated_linkedin = clean(
                opportunity.get("contact_linkedin_url")
            )
            automated_confidence = upper(
                opportunity.get("contact_email_confidence")
            )

            if automated_contact_parts or automated_linkedin:
                st.write("**Automatic contact found before manual routing**")
                if automated_contact_parts:
                    st.write(" · ".join(automated_contact_parts))
                if automated_confidence:
                    st.caption(
                        f"Email confidence: {automated_confidence}"
                    )
                if automated_linkedin:
                    st.link_button(
                        "Open automatically found LinkedIn profile",
                        automated_linkedin,
                        use_container_width=True,
                    )

        with st.form(
            key=widget_key("manual_contact_form", opportunity_key),
            clear_on_submit=False,
        ):
            st.markdown("#### Contact found manually")
            contact_name = st.text_input(
                "Contact name *",
                placeholder="e.g. Jane Smith",
            )
            contact_role = st.text_input(
                "Contact role",
                placeholder="e.g. CTO, recruiter, engineering manager",
            )
            contact_email = st.text_input(
                "Email address",
                placeholder="name@company.com",
            )
            contact_linkedin_url = st.text_input(
                "LinkedIn profile",
                placeholder="https://www.linkedin.com/in/...",
            )

            email_verified = st.checkbox(
                "I personally verified that this email belongs to this contact.",
                help=(
                    "Required when an email is entered. This is what allows the "
                    "system to classify it as USER_VERIFIED instead of treating "
                    "it as an automatically guessed address."
                ),
            )

            submitted = st.form_submit_button(
                "Save contact and generate drafts",
                type="primary",
                use_container_width=True,
            )

            if submitted:
                normalized_name = clean(contact_name)
                normalized_role = clean(contact_role)
                normalized_email = clean(contact_email).lower()
                normalized_linkedin = clean(contact_linkedin_url)

                validation_errors: list[str] = []
                if not normalized_name:
                    validation_errors.append("Enter the contact's name.")
                if not normalized_email and not normalized_linkedin:
                    validation_errors.append(
                        "Provide at least an email address or LinkedIn profile."
                    )
                if normalized_email and not EMAIL_PATTERN.match(normalized_email):
                    validation_errors.append("The email format is invalid.")
                if normalized_email and not email_verified:
                    validation_errors.append(
                        "Confirm that you personally verified the email address."
                    )
                if normalized_linkedin and "linkedin.com/" not in normalized_linkedin.lower():
                    validation_errors.append(
                        "The LinkedIn profile must be a linkedin.com URL."
                    )

                if validation_errors:
                    for error in validation_errors:
                        st.error(error)
                else:
                    try:
                        result = submit_manual_contact(
                            ACTION_URL,
                            API_KEY,
                            opportunity_key,
                            normalized_name,
                            normalized_role,
                            normalized_email,
                            normalized_linkedin,
                        )
                    except (
                        requests.exceptions.RequestException,
                        RuntimeError,
                    ) as error:
                        st.session_state["manual_flash_error"] = str(error)
                    else:
                        st.session_state["manual_flash_success"] = (
                            clean(result.get("message"))
                            or (
                                f"Manual contact saved for {company_name}. "
                                "Draft generation has started; refresh Active "
                                "Opportunities after it finishes."
                            )
                        )
                    finally:
                        st.cache_data.clear()
                        st.rerun()
