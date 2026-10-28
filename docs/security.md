# Security and Privacy

## Overview

This project automates parts of a job-search and outreach workflow, which means it interacts with potentially sensitive data such as:

- contact names and professional profiles,
- email addresses,
- application status,
- generated outreach drafts,
- Gmail thread identifiers,
- resume metadata,
- API credentials,
- and private deployment configuration.

The public repository is therefore designed around a simple principle:

> **Business logic can be public; production credentials, runtime state, and real personal data must remain private.**

The repository contains sanitized workflow exports, source code, configuration templates, synthetic sample data, and documentation. It intentionally excludes production secrets and private runtime artifacts.

---

# 1. Secret Management

## Environment Variables

The Streamlit dashboard reads runtime configuration from environment variables.

Examples include:

```text
N8N_API_URL
N8N_ACTION_URL
N8N_OUTREACH_URL
N8N_FOLLOWUP_URL
N8N_DISCOVERY_URL
DASHBOARD_API_KEY
```

The public repository contains:

```text
.env.example
```

with placeholder values only.

A real local or production deployment should use:

```text
.env
```

which is excluded by `.gitignore`.

The real `.env` file must never be committed.

## n8n Credentials

External integrations are configured using n8n's credential system rather than hard-coded secrets in workflow logic.

Examples include credentials for:

- Google Sheets,
- Google Drive,
- Gmail,
- Brave Search,
- Hunter,
- Vertex AI / Google Cloud,
- dashboard webhook authentication.

The public workflow exports have credential bindings removed or generalized.

Anyone importing the workflows must configure their own credentials.

---

# 2. Protected Dashboard API

The Streamlit dashboard does not directly modify Google Sheets or bypass workflow validation.

Instead, mutations are sent to dedicated n8n webhook workflows such as:

```text
Dashboard API - Opportunity Action
Dashboard API - Outreach Action
Dashboard API - Follow-up Action
Dashboard API - Discovery Action
```

These endpoints use header-based authentication.

The dashboard sends a shared API key using the configured authentication header.

This prevents unauthenticated requests from being treated as trusted dashboard actions.

---

# 3. Separation of Interface and Business Logic

The dashboard is intentionally kept separate from workflow state-management logic.

Streamlit is responsible for:

- displaying opportunities,
- showing contacts,
- presenting drafts,
- collecting user decisions.

n8n is responsible for:

- validating actions,
- applying state transitions,
- performing external API calls,
- enforcing sending rules,
- persisting state.

This separation reduces the risk of UI code accidentally bypassing important workflow checks.

---

# 4. Human Approval Before External Communication

The platform is not designed as a fully autonomous mass-outreach system.

Generated content is not automatically sent.

Initial outreach requires an explicit user action:

```text
approve_and_send
```

Follow-up outreach requires:

```text
approve_and_send_follow_up
```

Before approval, the user can:

- review the selected contact,
- edit the email subject,
- edit the email body,
- edit LinkedIn drafts,
- save the draft without sending,
- replace an automatically researched contact with a manual contact.

This keeps the user responsible for external communication.

---

# 5. Defense-in-Depth Sending Controls

The platform validates send eligibility in more than one place.

The dashboard API checks whether the opportunity is ready for sending.

The `Approved Outreach Sender` then independently reloads the current tracker state and verifies the conditions again.

A send operation is blocked unless the required conditions are satisfied.

Typical checks include:

```text
outreach_approval = APPROVED
outreach_status = DRAFT_READY
draft_final_status = READY
```

and additional checks for:

- outreach eligibility,
- valid recipient email,
- acceptable email-confidence level,
- resume metadata,
- resume attachment availability,
- previous send state,
- duplicate campaign state.

This prevents a single UI or API mistake from immediately becoming an outbound email.

---

# 6. Email Confidence Controls

Automatically discovered email addresses are not all treated equally.

The system uses confidence states such as:

```text
HIGH
MEDIUM
USER_VERIFIED
```

Only accepted confidence states can pass the email-sending gate.

A manually supplied address can be marked:

```text
USER_VERIFIED
```

after the user explicitly provides it.

Low-confidence or unresolved contact information should not automatically become outbound communication.

---

# 7. Contact Evidence

Contact research is designed to preserve evidence rather than only storing a selected name.

Candidate contact records can include:

- source URLs,
- role information,
- company confirmation,
- email verification status,
- confidence values,
- relevance scores,
- selection status.

This makes the contact-selection process auditable.

If automatic research fails to find a reliable contact, the system represents that failure explicitly rather than inventing one.

For example:

```text
contact_research_status = NOT_FOUND
manual_contact_status = NEEDS_CONTACT
```

The user can then continue through manual outreach.

---

# 8. Evidence-Grounded AI Use

LLMs are used for tasks such as:

- company interpretation,
- structured extraction,
- personalization,
- outreach drafting,
- follow-up drafting.

They are not treated as the source of truth for identity, workflow state, or sending authorization.

Deterministic code remains responsible for:

- deduplication,
- state transitions,
- business keys,
- eligibility,
- approval gates,
- sending,
- persistence.

Prompt instructions also prohibit unsupported assumptions such as:

- inventing company technologies,
- inventing vacancies,
- assuming visa sponsorship,
- assuming hiring plans,
- overstating candidate-company fit,
- fabricating personalization evidence.

---

# 9. Duplicate-Campaign Protection

The platform includes logic to reduce accidental duplicate outreach.

Campaign identity can be compared using signals such as:

- normalized company domain,
- contact email,
- LinkedIn URL,
- company name.

When another opportunity already owns an active campaign for the same company/contact identity, a second outreach attempt can be blocked.

This helps prevent multiple messages being sent to the same contact from different opportunity records.

---

# 10. Duplicate Send Prevention

A sent campaign stores state such as:

```text
sent_at
gmail_message_id
gmail_thread_id
```

A populated `sent_at` prevents the initial email from being sent again.

Follow-up workflows similarly track fields such as:

```text
follow_up_sent_at
follow_up_message_id
```

to reduce duplicate follow-up sending.

---

# 11. Reply-Aware Follow-Up Protection

The Gmail reply monitor tracks incoming messages using Gmail thread identifiers.

When a reply is detected, the tracker can update:

```text
response_status = REPLIED
reply_detected_at
```

Follow-up generation and sending workflows exclude campaigns where a reply has already been detected.

This helps prevent automated follow-up behavior after the recipient has already responded.

---

# 12. Private Runtime State

The n8n runtime directory is intentionally excluded from the public repository.

A production backup may contain files such as:

```text
database.sqlite
database.sqlite-wal
database.sqlite-shm
config
storage/
nodes/
n8nEventLog*.log
```

These files can contain:

- encrypted credential records,
- workflow execution data,
- user/account metadata,
- internal configuration,
- runtime logs,
- binary data,
- instance-specific state.

They should be treated as private backup material and never published.

---

# 13. Docker Runtime Metadata

Raw Docker inspection output is also excluded.

Files such as:

```text
*.inspect.json
docker-ps.txt
docker-images.txt
*-image-history.txt
```

may contain:

- environment variables,
- container IDs,
- internal network details,
- image metadata,
- deployment paths,
- mounted volumes,
- runtime secrets.

During project sanitization, a production dashboard API key was found in raw Docker inspection metadata.

For this reason, Docker runtime inspection files are treated as private operational artifacts rather than portfolio material.

---

# 14. Private Infrastructure Identifiers

The public repository does not include production-specific values such as:

- real GCP project identifiers,
- production VM addresses,
- Tailscale hostnames,
- internal instance IDs,
- real workflow IDs where avoidable,
- production Google Sheet IDs,
- production webhook identifiers,
- service-account files.

Public workflow exports use placeholders where deployment-specific configuration is required.

---

# 15. Real Contact and Application Data

Production application data is intentionally excluded from GitHub.

The repository does not publish:

- real recruiter or employee email addresses,
- real contact candidate lists,
- real LinkedIn research records,
- real application-tracking rows,
- real Gmail message/thread data,
- private notes.

Instead, the `samples/` directory contains synthetic records using fictional companies and contacts.

These samples preserve the schema and workflow relationships without exposing real people or application history.

---

# 16. Synthetic Public Samples

The public sample datasets are:

```text
samples/companies.sample.csv
samples/company-qualification.sample.csv
samples/application-tracker.sample.csv
samples/contact-candidates.sample.csv
```

They reproduce the workflow-aligned column structure with fictional data.

Example domains use non-production values such as:

```text
novaforge-ai.test
cloudrail-systems.test
helio-robotics.test
```

These files are for understanding the data model only.

---

# 17. `.gitignore` Protection

The repository `.gitignore` excludes common sensitive and runtime artifacts.

Examples include:

```text
.env
*.pem
*.key
credentials*.json
service-account*.json

__pycache__/
.venv/

.n8n/
database.sqlite*
n8nEventLog*.log
storage/
nodes/

*.inspect.json
docker-ps.txt
docker-images.txt
*-image-history.txt
```

This reduces the risk of accidentally committing local secrets or production state.

`.gitignore` is not a substitute for careful review, so a final repository scan should still be performed before publication.

---

# 18. Original Deployment Boundary

The original deployment ran on a Google Cloud VM with Dockerized services.

Core services included:

```text
n8n
Streamlit dashboard
FastAPI scraper
```

Administrative access was intended to remain private.

Tailscale was used to access internal interfaces instead of intentionally exposing management interfaces directly to the public internet.

The architecture therefore separates:

```text
public external APIs
```

from:

```text
private administrative interfaces
```

where possible.

---

# 19. Public Repository Sanitization

The public n8n workflow exports were sanitized before publication.

Sanitization included removal or replacement of items such as:

- credential bindings,
- Google Sheet document IDs,
- GCP project IDs,
- instance IDs,
- workflow IDs,
- production webhook IDs,
- real test identities,
- personal deployment-specific URLs.

Workflow logic, branching, prompts, state transitions, and engineering decisions were preserved.

The goal was to make the repository useful for technical review without publishing production configuration.

---

# 20. Threat Model and Scope

This project is a portfolio-grade prototype and not a hardened multi-tenant SaaS platform.

The current security model assumes:

- one trusted operator;
- controlled access to the dashboard;
- private administrative infrastructure;
- separately managed third-party credentials;
- low-volume personal workflow usage.

The project does not currently attempt to solve all concerns required for a commercial multi-user product.

Examples of future production-hardening areas include:

- centralized secret management;
- role-based access control;
- stronger user authentication;
- webhook request signing;
- database-level authorization;
- encrypted application-level sensitive fields;
- centralized audit logging;
- automated secret scanning in CI;
- stricter network segmentation;
- database migration away from Google Sheets;
- formal data-retention policies.

---

# 21. Recommended Production Improvements

## Secret Manager

Move runtime secrets to a managed secret store such as:

```text
Google Cloud Secret Manager
```

instead of relying only on environment variables.

## Relational Database

Move operational state from Google Sheets to a database such as:

```text
PostgreSQL
```

with:

- unique constraints,
- transactional updates,
- schema migrations,
- access controls.

## Stronger API Authentication

Replace or supplement a shared dashboard header key with:

- signed requests,
- authenticated user sessions,
- short-lived tokens,
- or an identity-aware proxy.

## Centralized Logging

Use structured logs with explicit redaction of:

- API keys,
- email contents,
- contact details,
- authentication headers.

## Automated Secret Scanning

Add repository checks using tools such as:

```text
GitHub secret scanning
gitleaks
trufflehog
```

before deployment or publication.

---

# Security Principle Summary

The main security boundaries of the project are:

```text
Secrets stay outside source control
        ↓
Dashboard actions use authenticated webhooks
        ↓
n8n validates state transitions
        ↓
LLMs generate but do not authorize
        ↓
Human approves external communication
        ↓
Sender re-validates eligibility
        ↓
Gmail thread state prevents duplicate/incorrect follow-ups
```

The most important design principle is:

> **Automation may prepare an action, but sensitive external actions still require deterministic validation and explicit human authorization.**
