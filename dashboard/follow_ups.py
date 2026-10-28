import os
from datetime import date

import requests
import streamlit as st


st.set_page_config(
    page_title="Follow-ups | Job Outreach Dashboard",
    page_icon="⏰",
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


def submit_follow_up_action(
    action_url,
    api_key,
    action,
    opportunity_key,
    follow_up_draft,
):
    response = requests.post(
        action_url,
        headers={
            "X-Dashboard-Key": api_key,
        },
        json={
            "action": action,
            "opportunity_key": opportunity_key,
            "follow_up_draft": follow_up_draft,
        },
        timeout=60,
    )

    try:
        result = response.json()
    except ValueError:
        result = {}

    if not isinstance(result, dict):
        raise RuntimeError(
            "The follow-up API returned an unexpected "
            f"response: {result!r}"
        )

    if (
        response.status_code >= 400
        or not result.get("success")
    ):
        message = clean(
            result.get("message")
        ) or (
            "The follow-up action failed "
            f"with HTTP {response.status_code}."
        )

        reasons = result.get(
            "blocking_reasons",
            [],
        )

        if isinstance(reasons, list) and reasons:
            message += " " + " ".join(
                clean(reason)
                for reason in reasons
                if clean(reason)
            )

        raise RuntimeError(message)

    return result


def parse_follow_up_date(value):
    text_value = clean(value)

    if not text_value:
        return None

    try:
        return date.fromisoformat(
            text_value[:10]
        )

    except ValueError:
        return None


def display_follow_up(
    due_date,
    opportunity,
    today,
):
    company = (
        clean(
            opportunity.get("company_name")
        )
        or "Unknown company"
    )

    position = (
        clean(
            opportunity.get("position_title")
        )
        or "Unknown position"
    )

    contact_name = clean(
        opportunity.get("contact_name")
    )

    contact_email = clean(
        opportunity.get("contact_email")
    )

    sent_at = clean(
        opportunity.get("sent_at")
    )

    response_status = (
        clean(
            opportunity.get("response_status")
        ).upper()
        or "NO_RESPONSE"
    )

    gmail_thread_id = clean(
        opportunity.get("gmail_thread_id")
    )

    days_difference = (
        due_date - today
    ).days

    if days_difference < 0:
        overdue_days = abs(
            days_difference
        )

        timing_text = (
            f"{overdue_days} day"
            f"{'s' if overdue_days != 1 else ''} "
            "overdue"
        )

    elif days_difference == 0:
        timing_text = "Due today"

    else:
        timing_text = (
            f"Due in {days_difference} day"
            f"{'s' if days_difference != 1 else ''}"
        )

    with st.container(border=True):
        st.markdown(
            f"### {company}"
        )

        st.write(
            f"**Context opportunity:** {position}"
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
                "Contact: "
                + " · ".join(contact_parts)
            )

        st.write(
            f"Follow-up date: "
            f"**{due_date.isoformat()}**"
        )

        if days_difference <= 0:
            st.warning(timing_text)

        else:
            st.info(timing_text)

        if sent_at:
            st.caption(
                "Original email sent: "
                + sent_at
            )

        st.caption(
            "Response status: "
            + response_status
        )

        follow_up_status = (
            clean(
                opportunity.get(
                    "follow_up_status"
                )
            ).upper()
            or "NOT_STARTED"
        )

        follow_up_approval = (
            clean(
                opportunity.get(
                    "follow_up_approval"
                )
            ).upper()
            or "PENDING"
        )

        follow_up_draft = clean(
            opportunity.get(
                "follow_up_draft"
            )
        )

        follow_up_generated_at = clean(
            opportunity.get(
                "follow_up_generated_at"
            )
        )

        follow_up_sent_at = clean(
            opportunity.get(
                "follow_up_sent_at"
            )
        )

        reply_detected_at = clean(
            opportunity.get(
                "reply_detected_at"
            )
        )

        opportunity_key = clean(
            opportunity.get(
                "opportunity_key"
            )
        )

        sent_session_key = (
            "follow_up_sent_"
            + opportunity_key
        )

        sent_in_session = bool(
            st.session_state.get(
                sent_session_key
            )
        )

        effectively_sent = (
            bool(follow_up_sent_at)
            or follow_up_status == "SENT"
            or sent_in_session
        )

        st.caption(
            "Follow-up status: "
            f"{follow_up_status} · "
            "Approval: "
            f"{follow_up_approval}"
        )

        if effectively_sent:
            st.success(
                "The follow-up has been sent."
                + (
                    " Sent at: "
                    + follow_up_sent_at
                    if follow_up_sent_at
                    else ""
                )
            )

        elif follow_up_draft:
            edited_follow_up = st.text_area(
                "Follow-up draft",
                value=follow_up_draft,
                height=240,
                key=(
                    "follow_up_editor_"
                    + opportunity_key
                ),
            )

            if follow_up_generated_at:
                st.caption(
                    "Draft generated: "
                    + follow_up_generated_at
                )

            save_allowed = bool(
                edited_follow_up.strip()
                and follow_up_status
                == "DRAFT_READY"
                and response_status
                == "NO_RESPONSE"
                and not reply_detected_at
            )

            send_problems = []

            if (
                follow_up_status
                != "DRAFT_READY"
            ):
                send_problems.append(
                    "The follow-up draft is not ready."
                )

            if (
                response_status
                != "NO_RESPONSE"
                or reply_detected_at
            ):
                send_problems.append(
                    "A reply has already been detected."
                )

            if due_date > today:
                send_problems.append(
                    "The scheduled follow-up date "
                    "has not arrived yet."
                )

            if not gmail_thread_id:
                send_problems.append(
                    "The Gmail thread ID is missing."
                )

            if not edited_follow_up.strip():
                send_problems.append(
                    "The follow-up draft is empty."
                )

            send_allowed = (
                not send_problems
            )

            save_column, send_column = (
                st.columns(2)
            )

            if save_column.button(
                "Save follow-up draft",
                key=(
                    "save_follow_up_"
                    + opportunity_key
                ),
                disabled=not save_allowed,
                use_container_width=True,
            ):
                try:
                    result = (
                        submit_follow_up_action(
                            FOLLOW_UP_ACTION_URL,
                            API_KEY,
                            "save_follow_up_draft",
                            opportunity_key,
                            edited_follow_up,
                        )
                    )

                except (
                    requests.exceptions.RequestException,
                    RuntimeError,
                ) as error:
                    st.error(str(error))

                else:
                    st.success(
                        clean(
                            result.get("message")
                        )
                        or (
                            "Follow-up draft "
                            "saved successfully."
                        )
                    )

                    st.cache_data.clear()

            if send_column.button(
                "Approve and send follow-up",
                key=(
                    "approve_follow_up_"
                    + opportunity_key
                ),
                disabled=not send_allowed,
                type="primary",
                use_container_width=True,
            ):
                st.session_state[
                    "pending_follow_up_send"
                ] = {
                    "opportunity_key":
                        opportunity_key,

                    "company_name":
                        company,

                    "contact_email":
                        contact_email,

                    "follow_up_draft":
                        edited_follow_up,
                }

            if send_problems:
                with st.expander(
                    "Why sending is currently disabled"
                ):
                    for problem in send_problems:
                        st.write(
                            f"• {problem}"
                        )

            pending_send = (
                st.session_state.get(
                    "pending_follow_up_send",
                    {},
                )
            )

            if (
                pending_send.get(
                    "opportunity_key"
                )
                == opportunity_key
            ):
                st.warning(
                    "This will send the follow-up "
                    "inside the existing Gmail thread "
                    f"to **{contact_email}**. "
                    "This action cannot be undone."
                )

                confirm_column, cancel_column = (
                    st.columns(2)
                )

                if confirm_column.button(
                    "Confirm and send follow-up",
                    key=(
                        "confirm_follow_up_"
                        + opportunity_key
                    ),
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        result = (
                            submit_follow_up_action(
                                FOLLOW_UP_ACTION_URL,
                                API_KEY,
                                (
                                    "approve_and_send_"
                                    "follow_up"
                                ),
                                opportunity_key,
                                pending_send.get(
                                    "follow_up_draft",
                                    edited_follow_up,
                                ),
                            )
                        )

                    except (
                        requests.exceptions.RequestException,
                        RuntimeError,
                    ) as error:
                        st.error(str(error))

                    else:
                        st.session_state[
                            sent_session_key
                        ] = True

                        st.session_state.pop(
                            "pending_follow_up_send",
                            None,
                        )

                        st.cache_data.clear()

                        st.success(
                            clean(
                                result.get("message")
                            )
                            or (
                                "Follow-up sent "
                                "successfully."
                            )
                        )

                if cancel_column.button(
                    "Cancel",
                    key=(
                        "cancel_follow_up_"
                        + opportunity_key
                    ),
                    use_container_width=True,
                ):
                    st.session_state.pop(
                        "pending_follow_up_send",
                        None,
                    )

                    st.info(
                        "Follow-up sending cancelled."
                    )

        elif days_difference <= 0:
            st.warning(
                "This follow-up is due, but no "
                "draft has been generated yet."
            )

        if gmail_thread_id:
            with st.expander(
                "Tracking details"
            ):
                st.code(
                    gmail_thread_id,
                    language=None,
                )


API_URL = clean(
    os.environ.get("N8N_API_URL")
)

FOLLOW_UP_ACTION_URL = clean(
    os.environ.get("N8N_FOLLOWUP_URL")
)

API_KEY = clean(
    os.environ.get("DASHBOARD_API_KEY")
)


st.title("Follow-ups")

st.caption(
    "Track company outreach that is waiting "
    "for a reply or follow-up."
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


if not FOLLOW_UP_ACTION_URL:
    st.error(
        "N8N_FOLLOWUP_URL is missing from the "
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
        "The Follow-ups page could not connect "
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

today = date.today()

follow_up_items = []

for opportunity in opportunities:
    outreach_status = clean(
        opportunity.get("outreach_status")
    ).upper()

    response_status = (
        clean(
            opportunity.get("response_status")
        ).upper()
        or "NO_RESPONSE"
    )

    follow_up_date = parse_follow_up_date(
        opportunity.get("follow_up_date")
    )

    if outreach_status != "SENT":
        continue

    if response_status != "NO_RESPONSE":
        continue

    if follow_up_date is None:
        continue

    follow_up_items.append(
        (
            follow_up_date,
            opportunity,
        )
    )


follow_up_items.sort(
    key=lambda entry: entry[0]
)

due_follow_ups = [
    entry
    for entry in follow_up_items
    if entry[0] <= today
]

upcoming_follow_ups = [
    entry
    for entry in follow_up_items
    if entry[0] > today
]


metric_1, metric_2, metric_3 = st.columns(3)

metric_1.metric(
    "Due or overdue",
    len(due_follow_ups),
)

metric_2.metric(
    "Upcoming",
    len(upcoming_follow_ups),
)

metric_3.metric(
    "Waiting for reply",
    len(follow_up_items),
)


st.divider()


if not follow_up_items:
    st.success(
        "There are currently no sent outreach "
        "emails waiting for a follow-up."
    )

else:
    st.subheader(
        f"Due or overdue ({len(due_follow_ups)})"
    )

    if not due_follow_ups:
        st.info(
            "No follow-ups are due today."
        )

    for due_date, opportunity in due_follow_ups:
        display_follow_up(
            due_date,
            opportunity,
            today,
        )

    st.subheader(
        f"Upcoming ({len(upcoming_follow_ups)})"
    )

    if not upcoming_follow_ups:
        st.info(
            "No upcoming follow-ups are scheduled."
        )

    for due_date, opportunity in upcoming_follow_ups:
        display_follow_up(
            due_date,
            opportunity,
            today,
        )
