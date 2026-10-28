from __future__ import annotations

import hashlib
import os
from typing import Any

import requests
from datetime import date, datetime
from urllib.parse import urlsplit, urlunsplit

import streamlit as st


st.set_page_config(
    page_title="Job Outreach Dashboard",
    page_icon="🎯",
    layout="wide",
)


API_URL = os.getenv("N8N_API_URL", "").strip()
ACTION_URL = os.getenv("N8N_ACTION_URL", "").strip()
OUTREACH_ACTION_URL = os.getenv(
    "N8N_OUTREACH_URL",
    "",
).strip()
API_KEY = os.getenv("DASHBOARD_API_KEY", "").strip()


def derive_discovery_url(action_url: str) -> str:
    """Build the discovery webhook URL from the existing n8n host."""
    if not action_url:
        return ""

    parsed = urlsplit(action_url)

    if not parsed.scheme or not parsed.netloc:
        return ""

    return urlunsplit((
        parsed.scheme,
        parsed.netloc,
        "/webhook/dashboard-discovery",
        "",
        "",
    ))


DISCOVERY_URL = (
    os.getenv("N8N_DISCOVERY_URL", "").strip()
    or derive_discovery_url(ACTION_URL)
)


def clean(value: Any) -> str:
    return str(value or "").strip()


def display_status(status: str) -> str:
    labels = {
        "TO_REVIEW": "🟡 To review",
        "APPLY": "🟠 Ready to apply",
        "APPLIED": "🔵 Applied",
        "SKIPPED": "⚫ Skipped",
        "SENT": "🟢 Sent",
    }

    return labels.get(status, status or "Unknown")



def display_research_status(status: str) -> str:
    labels = {
        "NOT_STARTED": "⚪ Not started",
        "IN_PROGRESS": "🟠 Researching",
        "COMPLETED": "🟢 Completed",
        "NOT_FOUND": "🟣 Manual contact needed",
        "FAILED": "🔴 Failed",
    }

    return labels.get(
        status,
        status or "⚪ Not started",
    )


def widget_key(prefix: str, value: str) -> str:
    digest = hashlib.sha1(
        value.encode("utf-8")
    ).hexdigest()[:12]

    return f"{prefix}_{digest}"


@st.cache_data(ttl=30, show_spinner=False)
def load_opportunities(
    api_url: str,
    api_key: str,
) -> dict[str, Any]:
    response = requests.get(
        api_url,
        headers={
            "X-Dashboard-Key": api_key,
        },
        timeout=30,
    )

    response.raise_for_status()
    payload = response.json()

    # Accept either an object or a one-item array from n8n.
    if isinstance(payload, list):
        if (
            len(payload) != 1
            or not isinstance(payload[0], dict)
        ):
            raise ValueError(
                "The n8n API returned an unexpected array."
            )

        payload = payload[0]

    if not isinstance(payload, dict):
        raise ValueError(
            "The n8n API returned an unexpected response."
        )

    return payload
def submit_opportunity_action(
    action_url: str,
    api_key: str,
    action: str,
    opportunity_key: str,
) -> dict[str, Any]:
    """Send a protected opportunity action to n8n."""

    response = requests.post(
        action_url,
        headers={
            "X-Dashboard-Key": api_key,
        },
        json={
            "action": action,
            "opportunity_key": opportunity_key,
        },
        timeout=30,
    )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.status_code >= 400:
        message = clean(
            payload.get("message")
        ) or (
            f"The action failed with HTTP "
            f"{response.status_code}."
        )

        raise RuntimeError(message)

    if not payload.get("success"):
        raise RuntimeError(
            clean(payload.get("message"))
            or "The action was not completed."
        )

    return payload


def submit_discovery_action(
    discovery_url: str,
    api_key: str,
) -> dict[str, Any]:
    """Start the discovery pipeline through the protected n8n API."""

    response = requests.post(
        discovery_url,
        headers={
            "X-Dashboard-Key": api_key,
        },
        json={
            "action": "start_discovery",
            "trigger_source": "DASHBOARD",
        },
        timeout=20,
    )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.status_code >= 400:
        message = clean(payload.get("message")) or (
            f"Discovery could not be started "
            f"(HTTP {response.status_code})."
        )
        raise RuntimeError(message)

    if payload and payload.get("success") is False:
        raise RuntimeError(
            clean(payload.get("message"))
            or "Discovery could not be started."
        )

    return payload


def submit_outreach_action(
    outreach_url: str,
    api_key: str,
    action: str,
    opportunity_key: str,
    email_subject: str,
    email_draft: str,
    linkedin_connection_note: str,
    linkedin_message: str,
) -> dict[str, Any]:
    """Save or approve outreach through the protected n8n API."""

    response = requests.post(
        outreach_url,
        headers={
            "X-Dashboard-Key": api_key,
        },
        json={
            "action": action,
            "opportunity_key": opportunity_key,
            "email_subject": email_subject,
            "email_draft": email_draft,
            "linkedin_connection_note": (
                linkedin_connection_note
            ),
            "linkedin_message": linkedin_message,
        },
        timeout=120,
    )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if response.status_code >= 400:
        message = clean(
            payload.get("message")
        ) or (
            f"The outreach action failed with HTTP "
            f"{response.status_code}."
        )

        reasons = payload.get(
            "blocking_reasons",
            payload.get(
                "send_gate_blocking_reasons",
                [],
            ),
        )

        if isinstance(reasons, list) and reasons:
            message += " " + " ".join(
                str(reason)
                for reason in reasons
            )

        raise RuntimeError(message)

    if not payload.get("success"):
        raise RuntimeError(
            clean(payload.get("message"))
            or "The outreach action was not completed."
        )

    return payload


st.title("🎯 Active Opportunities")

st.caption(
    "Review new opportunities and finish any applications or outreach "
    "that still need your attention."
)
flash_success = st.session_state.pop(
    "flash_success",
    None,
)

flash_error = st.session_state.pop(
    "flash_error",
    None,
)

if flash_success:
    st.success(flash_success)

if flash_error:
    st.error(flash_error)

if not API_URL:
    st.error(
        "N8N_API_URL is missing from the container environment."
    )
    st.stop()

if not ACTION_URL:
    st.error(
        "N8N_ACTION_URL is missing from the container environment."
    )
    st.stop()

if not OUTREACH_ACTION_URL:
    st.error(
        "N8N_OUTREACH_URL is missing from "
        "the container environment."
    )
    st.stop()


if not API_KEY:
    st.error(
        "DASHBOARD_API_KEY is missing from the container environment."
    )
    st.stop()


top_spacer, discovery_column, refresh_column = st.columns([4, 1.5, 1])

with discovery_column:
    if st.button(
        "Find new opportunities",
        use_container_width=True,
        disabled=not bool(DISCOVERY_URL),
        help=(
            "Start the startup discovery, company qualification, and "
            "application queue workflows in n8n."
        ),
    ):
        try:
            result = submit_discovery_action(
                DISCOVERY_URL,
                API_KEY,
            )

        except (
            requests.exceptions.RequestException,
            RuntimeError,
        ) as error:
            st.session_state["flash_error"] = str(error)

        else:
            st.session_state["flash_success"] = (
                clean(result.get("message"))
                or "Opportunity discovery started. Refresh this page after the workflows finish."
            )

        st.rerun()

with refresh_column:
    if st.button(
        "Refresh",
        use_container_width=True,
    ):
        st.cache_data.clear()
        st.rerun()

if not DISCOVERY_URL:
    st.caption(
        "The discovery button is disabled because the discovery webhook URL "
        "could not be derived from N8N_ACTION_URL."
    )


try:
    data = load_opportunities(
        API_URL,
        API_KEY,
    )

except requests.exceptions.RequestException as error:
    st.error(
        "The dashboard could not connect to the n8n API."
    )

    st.code(str(error))
    st.stop()

except (ValueError, KeyError) as error:
    st.error(
        "The n8n API returned an invalid response."
    )

    st.code(str(error))
    st.stop()


if not data.get("success"):
    st.error(
        "The n8n API returned an unsuccessful response."
    )
    st.stop()


summary = data.get("summary", {})
all_opportunities = data.get("opportunities", [])


def is_processed_opportunity(opportunity: dict[str, Any]) -> bool:
    """Return True once an item no longer needs work on this page."""
    application_status = clean(
        opportunity.get("application_status")
    ).upper()

    outreach_status = clean(
        opportunity.get("outreach_status")
    ).upper()

    response_status = clean(
        opportunity.get("response_status")
    ).upper()

    return bool(
        clean(opportunity.get("sent_at"))
        or outreach_status in {"SENT", "REPLIED"}
        or response_status == "REPLIED"
        or application_status == "SKIPPED"
    )


def needs_manual_contact(
    opportunity: dict[str, Any],
) -> bool:
    """
    Keep an opportunity on Manual Outreach
    until its manually supplied contact has
    produced a fresh draft.
    """
    manual_status = clean(
        opportunity.get(
            "manual_contact_status"
        )
    ).upper()

    has_draft = bool(
        opportunity.get("has_draft")
    )

    if manual_status == "NEEDS_CONTACT":
        return True

    if (
        manual_status == "CONTACT_ADDED"
        and not has_draft
    ):
        return True

    return False


opportunities = [
    opportunity
    for opportunity in all_opportunities
    if (
        not is_processed_opportunity(opportunity)
        and not needs_manual_contact(opportunity)
    )
]


def normalize_domain(value):
    domain = clean(value).lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain.rstrip("/")


def normalize_email(value):
    return clean(value).lower()


def normalize_linkedin(value):
    return clean(value).lower().rstrip("/")


def normalize_company_name(value):
    return " ".join(
        clean(value).lower().split()
    )


def campaign_rank(opportunity):
    """
    Higher values represent a more advanced
    company-outreach campaign.
    """
    outreach_status = clean(
        opportunity.get("outreach_status")
    ).upper()

    research_status = clean(
        opportunity.get("contact_research_status")
    ).upper()

    sent_at = clean(
        opportunity.get("sent_at")
    )

    if (
        sent_at
        or outreach_status
        in {
            "SENT",
            "REPLIED",
            "FOLLOW_UP_DUE",
        }
    ):
        return 500

    if outreach_status == "APPROVED":
        return 400

    if outreach_status == "DRAFT_READY":
        return 300

    if research_status == "COMPLETED":
        return 200

    if research_status == "IN_PROGRESS":
        return 100

    return 0


def shares_campaign_identity(
    first,
    second,
):
    first_domain = normalize_domain(
        first.get("company_domain")
    )

    second_domain = normalize_domain(
        second.get("company_domain")
    )

    if (
        first_domain
        and second_domain
        and first_domain == second_domain
    ):
        return True

    first_email = normalize_email(
        first.get("contact_email")
    )

    second_email = normalize_email(
        second.get("contact_email")
    )

    if (
        first_email
        and second_email
        and first_email == second_email
    ):
        return True

    first_linkedin = normalize_linkedin(
        first.get("contact_linkedin_url")
    )

    second_linkedin = normalize_linkedin(
        second.get("contact_linkedin_url")
    )

    if (
        first_linkedin
        and second_linkedin
        and first_linkedin == second_linkedin
    ):
        return True

    # Use the displayed company name only as a fallback
    # when neither row has a company domain.
    if not first_domain and not second_domain:
        first_company = normalize_company_name(
            first.get("company_name")
        )

        second_company = normalize_company_name(
            second.get("company_name")
        )

        if (
            first_company
            and second_company
            and first_company == second_company
        ):
            return True

    return False


def build_campaign_coverage(items):
    """
    Group opportunities that share a company domain,
    contact email, or LinkedIn profile.

    The most advanced outreach in each group becomes
    the canonical company campaign.
    """
    count = len(items)
    parents = list(range(count))


    def find(index):
        while parents[index] != index:
            parents[index] = parents[
                parents[index]
            ]

            index = parents[index]

        return index


    def union(first_index, second_index):
        first_root = find(first_index)
        second_root = find(second_index)

        if first_root != second_root:
            parents[second_root] = first_root


    for first_index in range(count):
        for second_index in range(
            first_index + 1,
            count,
        ):
            if shares_campaign_identity(
                items[first_index],
                items[second_index],
            ):
                union(
                    first_index,
                    second_index,
                )


    grouped_indexes = {}

    for index in range(count):
        root = find(index)

        grouped_indexes.setdefault(
            root,
            [],
        ).append(index)


    coverage = {}

    for indexes in grouped_indexes.values():
        active_indexes = [
            index
            for index in indexes
            if campaign_rank(items[index]) > 0
        ]

        if not active_indexes:
            continue

        canonical_index = max(
            active_indexes,
            key=lambda index: (
                campaign_rank(items[index]),
                clean(
                    items[index].get("sent_at")
                ),
                clean(
                    items[index].get(
                        "opportunity_key"
                    )
                ),
            ),
        )

        canonical = items[canonical_index]

        canonical_key = clean(
            canonical.get("opportunity_key")
        )

        if not canonical_key:
            continue

        for index in indexes:
            if index == canonical_index:
                continue

            current_key = clean(
                items[index].get(
                    "opportunity_key"
                )
            )

            if not current_key:
                continue

            coverage[current_key] = {
                "opportunity_key":
                    canonical_key,

                "company_name":
                    clean(
                        canonical.get(
                            "company_name"
                        )
                    ),

                "position_title":
                    clean(
                        canonical.get(
                            "position_title"
                        )
                    ),

                "contact_name":
                    clean(
                        canonical.get(
                            "contact_name"
                        )
                    ),

                "contact_email":
                    clean(
                        canonical.get(
                            "contact_email"
                        )
                    ),

                "contact_linkedin_url":
                    clean(
                        canonical.get(
                            "contact_linkedin_url"
                        )
                    ),

                "outreach_status":
                    clean(
                        canonical.get(
                            "outreach_status"
                        )
                    ).upper(),

                "sent_at":
                    clean(
                        canonical.get(
                            "sent_at"
                        )
                    ),
            }

    return coverage


company_campaign_coverage = (
    build_campaign_coverage(
        all_opportunities
    )
)


metric_columns = st.columns(5)

metric_columns[0].metric(
    "Active",
    len(opportunities),
)

metric_columns[1].metric(
    "To review",
    sum(
        clean(item.get("application_status")).upper() == "TO_REVIEW"
        for item in opportunities
    ),
)

metric_columns[2].metric(
    "Applied — outreach pending",
    sum(
        clean(item.get("application_status")).upper() == "APPLIED"
        for item in opportunities
    ),
)

metric_columns[3].metric(
    "Drafts ready",
    sum(bool(item.get("has_draft")) for item in opportunities),
)

metric_columns[4].metric(
    "Researching",
    sum(
        clean(item.get("contact_research_status")).upper() == "IN_PROGRESS"
        for item in opportunities
    ),
)


generated_at = clean(
    data.get("generated_at")
)

if generated_at:
    st.caption(
        f"Last API refresh: {generated_at}"
    )


st.divider()


filter_column_1, filter_column_2 = st.columns(2)

available_countries = sorted(
    {
        clean(item.get("country"))
        for item in opportunities
        if clean(item.get("country"))
    }
)

available_statuses = sorted(
    {
        clean(item.get("application_status"))
        for item in opportunities
        if clean(item.get("application_status"))
    }
)


selected_countries = filter_column_1.multiselect(
    "Countries",
    options=available_countries,
    default=available_countries,
)

selected_statuses = filter_column_2.multiselect(
    "Application status",
    options=available_statuses,
    default=available_statuses,
)


filtered_opportunities = [
    item
    for item in opportunities
    if (
        clean(item.get("country"))
        in selected_countries
        and clean(
            item.get("application_status")
        )
        in selected_statuses
    )
]


st.subheader(
    f"Active opportunities ({len(filtered_opportunities)})"
)


if not filtered_opportunities:
    st.info(
        "No opportunities match the selected filters."
    )


for opportunity in filtered_opportunities:
    opportunity_key = clean(
        opportunity.get("opportunity_key")
    )

    covered_by_campaign = (
        company_campaign_coverage.get(
            opportunity_key
        )
    )

    outreach_covered = bool(
        covered_by_campaign
    )

    company_name = clean(
        opportunity.get("company_name")
    )

    position_title = clean(
        opportunity.get("position_title")
    )

    country = clean(
        opportunity.get("country")
    )

    application_status = clean(
        opportunity.get("application_status")
    )

    opportunity_type = clean(
        opportunity.get("opportunity_type")
    ).upper() or "DIRECT_APPLICATION"

    is_speculative = (
        opportunity_type == "SPECULATIVE_OUTREACH"
        or opportunity_key.lower().endswith("::speculative")
    )

    qualification_score = opportunity.get(
        "qualification_score",
        0,
    )

    vacancy_url = clean(
        opportunity.get("vacancy_url")
    )

    contact_research_status = clean(
        opportunity.get("contact_research_status")
    ) or "NOT_STARTED"

    has_contact = bool(
        opportunity.get("has_contact")
    )

    has_draft = bool(
        opportunity.get("has_draft")
    )

    with st.container(border=True):
        if outreach_covered:
            canonical_company = (
                covered_by_campaign.get(
                    "company_name"
                )
                or company_name
            )

            canonical_position = (
                covered_by_campaign.get(
                    "position_title"
                )
                or "another opportunity"
            )

            canonical_status = (
                covered_by_campaign.get(
                    "outreach_status"
                )
                or "ACTIVE"
            )

            canonical_contact = (
                covered_by_campaign.get(
                    "contact_name"
                )
                or covered_by_campaign.get(
                    "contact_email"
                )
                or "saved company contact"
            )

            st.warning(
                "Covered by existing company outreach"
            )

            st.write(
                f"**{canonical_company}** already has "
                "one active outreach campaign."
            )

            st.caption(
                "Canonical campaign: "
                f"{canonical_position} · "
                f"Contact: {canonical_contact} · "
                f"Status: {canonical_status}"
            )

            st.caption(
                "A second email or LinkedIn outreach "
                "will not be created for this vacancy."
            )
        title_column, score_column = st.columns(
            [5, 1]
        )

        with title_column:
            st.subheader(company_name)
            st.write(f"**{position_title}**")
            st.caption(
                f"{country} · "
                f"{display_status(application_status)}"
            )

            progress_parts = [
                "Contact research: "
                + display_research_status(
                    contact_research_status
                )
            ]

            if has_contact:
                progress_parts.append(
                    "👤 Contact found"
                )

            if has_draft:
                progress_parts.append(
                    "✉️ Draft ready"
                )

            st.caption(
                " · ".join(progress_parts)
            )

        with score_column:
            st.metric(
                "Fit score",
                qualification_score,
            )

        action_columns = st.columns(
            2 if is_speculative else 3
        )

        open_label = (
            "Open company / careers page"
            if is_speculative
            else "Open vacancy"
        )

        if vacancy_url:
            action_columns[0].link_button(
                open_label,
                vacancy_url,
                use_container_width=True,
            )
        else:
            action_columns[0].button(
                (
                    "No company link"
                    if is_speculative
                    else "No vacancy link"
                ),
                disabled=True,
                use_container_width=True,
                key=widget_key(
                    "no_url",
                    opportunity_key,
                ),
            )

        mark_applied_disabled = (
            application_status == "APPLIED"
        )

        skip_disabled = (
            application_status
            in {"APPLIED", "SKIPPED"}
        )

        if not is_speculative:
            if action_columns[1].button(
                "Mark applied",
                key=widget_key(
                    "apply",
                    opportunity_key,
                ),
                disabled=mark_applied_disabled,
                use_container_width=True,
                help=(
                    "Use this only after you have submitted "
                    "the application through the official site."
                ),
            ):
                st.session_state["pending_action"] = {
                    "action": "mark_applied",
                    "opportunity_key": opportunity_key,
                    "company_name": company_name,
                    "position_title": position_title,
                }

                st.rerun()

        skip_column = (
            action_columns[1]
            if is_speculative
            else action_columns[2]
        )

        if skip_column.button(
            "Skip",
            key=widget_key(
                "skip",
                opportunity_key,
            ),
            disabled=skip_disabled,
            use_container_width=True,
        ):
            st.session_state["pending_action"] = {
                "action": "skip",
                "opportunity_key": opportunity_key,
                "company_name": company_name,
                "position_title": position_title,
            }

            st.rerun()


        pending_action = st.session_state.get(
            "pending_action",
            {},
        )


        if (
            pending_action.get("opportunity_key")
            == opportunity_key
        ):
            pending_type = pending_action.get(
                "action",
                "",
            )

            if pending_type == "mark_applied":
                confirmation_message = (
                    "Confirm that you already submitted "
                    f"your application for **{position_title}** "
                    f"at **{company_name}**."
                )

                confirmation_label = (
                    "Yes, mark as applied"
                )

            else:
                confirmation_message = (
                    "Confirm that you want to skip "
                    f"**{position_title}** at "
                    f"**{company_name}**."
                )

                confirmation_label = "Yes, skip"


            st.warning(confirmation_message)

            confirm_column, cancel_column = st.columns(2)


            if confirm_column.button(
                confirmation_label,
                key=widget_key(
                    "confirm_action",
                    opportunity_key,
                ),
                type="primary",
                use_container_width=True,
            ):
                try:
                    result = submit_opportunity_action(
                        ACTION_URL,
                        API_KEY,
                        pending_type,
                        opportunity_key,
                    )

                except (
                    requests.exceptions.RequestException,
                    RuntimeError,
                ) as error:
                    st.session_state[
                        "flash_error"
                    ] = str(error)

                else:
                    st.session_state[
                        "flash_success"
                    ] = clean(
                        result.get("message")
                    ) or "Opportunity updated."

                finally:
                    st.session_state.pop(
                        "pending_action",
                        None,
                    )

                    st.cache_data.clear()
                    st.rerun()


            if cancel_column.button(
                "Cancel",
                key=widget_key(
                    "cancel_action",
                    opportunity_key,
                ),
                use_container_width=True,
            ):
                st.session_state.pop(
                    "pending_action",
                    None,
                )

                st.rerun()

        outreach_mode = clean(
            opportunity.get("outreach_mode")
        ).upper()

        research_status = clean(
            opportunity.get(
                "contact_research_status"
            )
        ).upper() or "NOT_STARTED"

        current_outreach_status = clean(
            opportunity.get("outreach_status")
        ).upper()

        current_sent_at = clean(
            opportunity.get("sent_at")
        )

        research_action_disabled = (
            outreach_covered
            or application_status
            in {
                "APPLIED",
                "SKIPPED",
            }
            or outreach_mode
            in {
                "ADJACENT_ROLE",
                "SPECULATIVE",
            }
            or research_status
            in {
                "IN_PROGRESS",
                "COMPLETED",
            }
            or current_outreach_status == "SENT"
            or bool(current_sent_at)
        )

        if is_speculative:
            if outreach_mode == "SPECULATIVE":
                st.caption(
                    "Outreach strategy: "
                    "🔎 Exploring speculative opportunities"
                )

            if st.button(
                "Explore speculative opportunities",
                key=widget_key(
                    "explore_speculative",
                    opportunity_key,
                ),
                disabled=research_action_disabled,
                use_container_width=True,
            ):
                st.session_state[
                    "pending_speculative"
                ] = {
                    "opportunity_key":
                        opportunity_key,
                    "company_name":
                        company_name,
                    "position_title":
                        position_title,
                }

                st.rerun()

            pending_speculative = st.session_state.get(
                "pending_speculative",
                {},
            )

            if (
                pending_speculative.get(
                    "opportunity_key"
                )
                == opportunity_key
            ):
                st.warning(
                    "No matching public vacancy is being "
                    "treated as an application here. This "
                    "will research a suitable contact and "
                    "generate a message asking about current, "
                    "upcoming, or unadvertised opportunities "
                    f"at **{company_name}**."
                )

                confirm_speculative, cancel_speculative = (
                    st.columns(2)
                )

                if confirm_speculative.button(
                    "Confirm speculative exploration",
                    key=widget_key(
                        "confirm_speculative",
                        opportunity_key,
                    ),
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        result = submit_opportunity_action(
                            ACTION_URL,
                            API_KEY,
                            "explore_speculative",
                            opportunity_key,
                        )

                    except (
                        requests.exceptions.RequestException,
                        RuntimeError,
                    ) as error:
                        st.session_state[
                            "flash_error"
                        ] = str(error)

                    else:
                        st.session_state[
                            "flash_success"
                        ] = clean(
                            result.get("message")
                        ) or (
                            "Speculative contact research "
                            "started."
                        )

                    finally:
                        st.session_state.pop(
                            "pending_speculative",
                            None,
                        )

                        st.cache_data.clear()
                        st.rerun()

                if cancel_speculative.button(
                    "Cancel",
                    key=widget_key(
                        "cancel_speculative",
                        opportunity_key,
                    ),
                    use_container_width=True,
                ):
                    st.session_state.pop(
                        "pending_speculative",
                        None,
                    )

                    st.rerun()

        else:
            if outreach_mode == "ADJACENT_ROLE":
                st.caption(
                    "Outreach strategy: "
                    "🔎 Exploring an adjacent role"
                )

            if st.button(
                "Explore adjacent opportunities",
                key=widget_key(
                    "explore_adjacent",
                    opportunity_key,
                ),
                disabled=research_action_disabled,
                use_container_width=True,
            ):
                st.session_state[
                    "pending_adjacent"
                ] = {
                    "opportunity_key":
                        opportunity_key,
                    "company_name":
                        company_name,
                    "position_title":
                        position_title,
                }

                st.rerun()

            pending_adjacent = st.session_state.get(
                "pending_adjacent",
                {},
            )

            if (
                pending_adjacent.get(
                    "opportunity_key"
                )
                == opportunity_key
            ):
                st.warning(
                    "This does not mark the vacancy as "
                    "applied. It will research a suitable "
                    "contact and generate a message asking "
                    f"about a better-fitting opportunity "
                    f"at **{company_name}**."
                )

                confirm_adjacent, cancel_adjacent = (
                    st.columns(2)
                )

                if confirm_adjacent.button(
                    "Confirm exploration",
                    key=widget_key(
                        "confirm_adjacent",
                        opportunity_key,
                    ),
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        result = submit_opportunity_action(
                            ACTION_URL,
                            API_KEY,
                            "explore_adjacent",
                            opportunity_key,
                        )

                    except (
                        requests.exceptions.RequestException,
                        RuntimeError,
                    ) as error:
                        st.session_state[
                            "flash_error"
                        ] = str(error)

                    else:
                        st.session_state[
                            "flash_success"
                        ] = clean(
                            result.get("message")
                        ) or (
                            "Adjacent-role contact "
                            "research started."
                        )

                    finally:
                        st.session_state.pop(
                            "pending_adjacent",
                            None,
                        )

                        st.cache_data.clear()
                        st.rerun()

                if cancel_adjacent.button(
                    "Cancel",
                    key=widget_key(
                        "cancel_adjacent",
                        opportunity_key,
                    ),
                    use_container_width=True,
                ):
                    st.session_state.pop(
                        "pending_adjacent",
                        None,
                    )

                    st.rerun()

        # Manual-contact override. This is useful when automatic research
        # found a person, but the contact details are not trustworthy enough
        # (for example an email with LOW/NONE confidence), or when the user
        # simply prefers to find a different contact manually.
        manual_contact_status = clean(
            opportunity.get("manual_contact_status")
        ).upper()

        email_confidence_for_override = clean(
            opportunity.get("contact_email_confidence")
        ).upper()

        manual_override_available = (
            not outreach_covered
            and manual_contact_status != "NEEDS_CONTACT"
            and outreach_mode in {"ADJACENT_ROLE", "SPECULATIVE", "POST_APPLICATION"}
            and research_status not in {"NOT_STARTED", "IN_PROGRESS"}
            and current_outreach_status != "SENT"
            and not current_sent_at
            and (
                has_contact
                or email_confidence_for_override in {"LOW", "NONE"}
            )
        )

        if manual_override_available:
            weak_email = (
                email_confidence_for_override
                and email_confidence_for_override
                not in {"HIGH", "MEDIUM", "USER_VERIFIED"}
            )

            if weak_email:
                st.info(
                    "The automatic search found a contact, but the saved "
                    f"email confidence is {email_confidence_for_override}. "
                    "You can move this opportunity to Manual Outreach and "
                    "replace the contact with one you verify yourself."
                )

            if st.button(
                "Search for a contact manually instead",
                key=widget_key(
                    "move_manual",
                    opportunity_key,
                ),
                use_container_width=True,
            ):
                try:
                    result = submit_opportunity_action(
                        ACTION_URL,
                        API_KEY,
                        "move_to_manual_outreach",
                        opportunity_key,
                    )
                except (
                    requests.exceptions.RequestException,
                    RuntimeError,
                ) as error:
                    st.session_state["flash_error"] = str(error)
                else:
                    st.session_state["flash_success"] = (
                        clean(result.get("message"))
                        or "Opportunity moved to Manual Outreach."
                    )
                finally:
                    st.cache_data.clear()
                    st.rerun()

        with st.expander(
            (
                "Why this company was selected"
                if is_speculative
                else "Why this opportunity was selected"
            )
        ):
            st.write(
                clean(
                    opportunity.get(
                        "qualification_reason"
                    )
                )
                or (
                    "No qualification explanation "
                    "is available."
                )
            )

            st.write(
                "**Visa or relocation status:**",
                clean(
                    opportunity.get(
                        "visa_support_status"
                    )
                )
                or "Unknown",
            )

        if has_draft:
            with st.expander(
                "Review and manage outreach"
            ):
                contact_name = clean(
                    opportunity.get("contact_name")
                )

                contact_role = clean(
                    opportunity.get("contact_role")
                )

                contact_email = clean(
                    opportunity.get("contact_email")
                )

                email_confidence = clean(
                    opportunity.get(
                        "contact_email_confidence"
                    )
                ).upper()

                sent_at = clean(
                    opportunity.get("sent_at")
                )

                current_outreach_status = clean(
                    opportunity.get(
                        "outreach_status"
                    )
                ).upper()

                st.markdown("#### Contact")

                if contact_name or contact_email:
                    contact_parts = [
                        part
                        for part in [
                            contact_name,
                            contact_role,
                            contact_email,
                        ]
                        if part
                    ]

                    st.write(" · ".join(contact_parts))

                    if email_confidence:
                        st.caption(
                            "Email confidence: "
                            f"{email_confidence}"
                        )
                else:
                    st.info(
                        "No verified contact has been "
                        "saved for this opportunity yet."
                    )

                st.markdown("#### Editable email")

                edited_subject = st.text_input(
                    "Email subject",
                    value=clean(
                        opportunity.get(
                            "email_subject"
                        )
                    ),
                    key=widget_key(
                        "edit_subject",
                        opportunity_key,
                    ),
                )

                edited_email = st.text_area(
                    "Email draft",
                    value=clean(
                        opportunity.get(
                            "email_draft"
                        )
                    ),
                    height=340,
                    key=widget_key(
                        "edit_email",
                        opportunity_key,
                    ),
                )

                st.markdown(
                    "#### Editable LinkedIn outreach"
                )

                edited_connection_note = st.text_area(
                    "LinkedIn connection note",
                    value=clean(
                        opportunity.get(
                            "linkedin_connection_note"
                        )
                    ),
                    height=100,
                    key=widget_key(
                        "edit_connection",
                        opportunity_key,
                    ),
                )

                edited_linkedin_message = st.text_area(
                    "LinkedIn direct message",
                    value=clean(
                        opportunity.get(
                            "linkedin_message"
                        )
                    ),
                    height=180,
                    key=widget_key(
                        "edit_linkedin",
                        opportunity_key,
                    ),
                )

                draft_fields_complete = bool(
                    edited_subject.strip()
                    and edited_email.strip()
                )

                current_outreach_mode = clean(
                    opportunity.get("outreach_mode")
                ).upper()

                eligible_for_outreach = (
                    application_status == "APPLIED"
                    or current_outreach_mode
                    in {
                        "ADJACENT_ROLE",
                        "SPECULATIVE",
                    }
                )

                save_allowed = (
                    not outreach_covered
                    and eligible_for_outreach
                    and not sent_at
                    and current_outreach_status != "SENT"
                    and draft_fields_complete
                )

                send_problems = []

                if outreach_covered:
                    send_problems.append(
                        "This opportunity is covered by "
                        "an existing company outreach campaign."
                    )

                if not eligible_for_outreach:
                    send_problems.append(
                        "Outreach requires either an applied "
                        "opportunity or an explicitly selected "
                        "adjacent/speculative outreach strategy."
                    )

                if contact_research_status != "COMPLETED":
                    send_problems.append(
                        "Contact research is not completed."
                    )

                if not contact_email:
                    send_problems.append(
                        "No contact email is available."
                    )

                if email_confidence not in {
                    "HIGH",
                    "MEDIUM",
                    "USER_VERIFIED",
                }:
                    send_problems.append(
                        "Email confidence is not HIGH, MEDIUM, or USER_VERIFIED."
                    )

                if not draft_fields_complete:
                    send_problems.append(
                        "Email subject or body is empty."
                    )

                if sent_at or current_outreach_status == "SENT":
                    send_problems.append(
                        "The outreach email was already sent."
                    )

                send_allowed = not send_problems

                save_column, send_column = st.columns(2)

                if save_column.button(
                    "Save draft",
                    key=widget_key(
                        "save_draft",
                        opportunity_key,
                    ),
                    disabled=not save_allowed,
                    use_container_width=True,
                ):
                    try:
                        result = submit_outreach_action(
                            OUTREACH_ACTION_URL,
                            API_KEY,
                            "save_draft",
                            opportunity_key,
                            edited_subject,
                            edited_email,
                            edited_connection_note,
                            edited_linkedin_message,
                        )

                    except (
                        requests.exceptions.RequestException,
                        RuntimeError,
                    ) as error:
                        st.error(
                            str(error)
                        )

                    else:
                        st.success(
                            clean(
                                result.get("message")
                            ) or (
                                "Outreach drafts saved."
                            )
                        )

                        # Ensure that the next natural rerun
                        # loads the latest data from n8n.
                        st.cache_data.clear()

                if send_column.button(
                    "Approve and send email",
                    key=widget_key(
                        "approve_send",
                        opportunity_key,
                    ),
                    disabled=not send_allowed,
                    type="primary",
                    use_container_width=True,
                ):
                    st.session_state[
                        "pending_send"
                    ] = {
                        "opportunity_key": opportunity_key,
                        "company_name": company_name,
                        "position_title": position_title,
                    }

                    # No explicit rerun is required here.
                    # The confirmation section below reads
                    # pending_send during this same execution.

                if send_problems and not sent_at:
                    with st.expander(
                        "Why sending is currently disabled"
                    ):
                        for problem in send_problems:
                            st.write(f"• {problem}")

                pending_send = st.session_state.get(
                    "pending_send",
                    {},
                )

                if (
                    pending_send.get(
                        "opportunity_key"
                    )
                    == opportunity_key
                ):
                    st.warning(
                        "This will send the approved email "
                        f"to **{contact_email}** with your "
                        "resume attached. This action cannot "
                        "be undone."
                    )

                    confirm_send, cancel_send = st.columns(2)

                    if confirm_send.button(
                        "Confirm and send",
                        key=widget_key(
                            "confirm_send",
                            opportunity_key,
                        ),
                        type="primary",
                        use_container_width=True,
                    ):
                        try:
                            result = submit_outreach_action(
                                OUTREACH_ACTION_URL,
                                API_KEY,
                                "approve_and_send",
                                opportunity_key,
                                edited_subject,
                                edited_email,
                                edited_connection_note,
                                edited_linkedin_message,
                            )

                        except (
                            requests.exceptions.RequestException,
                            RuntimeError,
                        ) as error:
                            st.session_state[
                                "flash_error"
                            ] = str(error)

                        else:
                            st.session_state[
                                "flash_success"
                            ] = clean(
                                result.get("message")
                            ) or (
                                "Approved outreach email sent."
                            )

                        finally:
                            st.session_state.pop(
                                "pending_send",
                                None,
                            )

                            st.cache_data.clear()
                            st.rerun()

                    if cancel_send.button(
                        "Cancel",
                        key=widget_key(
                            "cancel_send",
                            opportunity_key,
                        ),
                        use_container_width=True,
                    ):
                        st.session_state.pop(
                            "pending_send",
                            None,
                        )

                        st.rerun()

                if sent_at:
                    st.success(
                        "Email sent successfully on "
                        f"{sent_at}."
                    )

                linkedin_url = clean(
                    opportunity.get(
                        "contact_linkedin_url"
                    )
                )

                if linkedin_url:
                    st.link_button(
                        "Open contact on LinkedIn",
                        linkedin_url,
                        use_container_width=True,
                    )

