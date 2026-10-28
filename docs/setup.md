# Setup Guide

## Overview

This repository contains a sanitized reference implementation of the AI-Powered Job Discovery & Outreach Automation Platform.

The project is composed of three main runtime pieces:

- **n8n** — workflow orchestration and integrations
- **FastAPI scraper** — startup/article discovery service
- **Streamlit dashboard** — human review and control interface

Google Sheets is used as the operational state store, while external integrations provide AI analysis, contact research, email delivery, and reply monitoring.

> The public repository does not contain production credentials or production data. You must provide your own configuration before running the project.

---

# 1. Prerequisites

You will need:

- Python 3.10+ recommended
- n8n
- a Google account
- a Google Sheets workbook
- access to Google Drive and Gmail for the sender workflows
- a Google Cloud project with Vertex AI access
- Brave Search API credentials
- Hunter API credentials

Docker is recommended for reproducing the original service-oriented deployment, but the Python services can also be run directly during local development.

---

# 2. Repository Structure

Relevant runtime folders:

```text
ai-job-outreach-platform/
│
├── dashboard/
│   ├── app.py
│   ├── opportunities.py
│   ├── manual_outreach.py
│   ├── processed.py
│   ├── follow_ups.py
│   ├── replies.py
│   └── requirements.txt
│
├── scraper/
│   ├── app.py
│   └── requirements.txt
│
├── workflows/
│   ├── discovery/
│   ├── dashboard-api/
│   └── outreach/
│
├── samples/
├── docs/
├── .env.example
└── .gitignore
```

---

# 3. Create the Google Sheets Workbook

Create one Google Sheets workbook containing these four sheets:

```text
Companies
Company_Qualification
Application_Tracker
Contact_Candidates
```

The easiest way to reproduce the schemas is to use the synthetic files in:

```text
samples/
```

The files are:

```text
companies.sample.csv
company-qualification.sample.csv
application-tracker.sample.csv
contact-candidates.sample.csv
```

You can use the CSV headers to create the corresponding sheet columns.

The sample rows are fictional and can be deleted after the workbook structure has been created.

---

# 4. Configure Google Access

The workflows use Google integrations for:

- Google Sheets
- Google Drive
- Gmail

Configure the appropriate n8n credentials for your environment.

The original project used Google credentials configured inside n8n rather than embedding secrets in workflow code.

The public workflow exports intentionally contain no production credential bindings.

After importing the workflows, open each Google node and select your own credential.

---

# 5. Configure Vertex AI

Create or select a Google Cloud project with Vertex AI available.

The sanitized workflows contain the placeholder:

```text
REPLACE_WITH_GCP_PROJECT_ID
```

Replace it with your own Google Cloud project ID in the relevant Vertex AI nodes.

Also select the Google/Vertex credential configured for your n8n instance.

Do not commit service-account JSON files to the repository.

---

# 6. Configure Brave Search

The Contact Research workflow uses Brave Search for:

- contact discovery,
- company/contact evidence,
- personalization context.

Create your own Brave Search API credential.

In n8n, configure the HTTP Header Auth credential used by the Brave Search HTTP Request nodes.

The workflow logic should not require an API key to be written directly into a node body or committed to the repository.

---

# 7. Configure Hunter

Hunter is used during contact research for:

- domain/email discovery,
- email finding,
- email verification.

Configure your Hunter API credential in n8n.

Assign it to the corresponding Hunter HTTP Request nodes in the Contact Research workflow.

---

# 8. Import the n8n Workflows

Import all JSON files under:

```text
workflows/
```

The twelve workflows are grouped into:

```text
workflows/discovery/
workflows/dashboard-api/
workflows/outreach/
```

The public workflow exports are intentionally inactive after sanitization.

Keep them inactive until all credentials and dependencies have been configured.

---

# 9. Replace the Google Sheet ID

The sanitized workflows use:

```text
REPLACE_WITH_GOOGLE_SHEET_ID
```

Replace this value with the ID of the Google Sheets workbook you created.

The spreadsheet ID is the value in a Google Sheets URL between:

```text
/spreadsheets/d/
```

and:

```text
/edit
```

For example:

```text
https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
```

After replacing the workbook ID, reselect the appropriate named sheet in each Google Sheets node.

The expected sheet names are:

```text
Companies
Company_Qualification
Application_Tracker
Contact_Candidates
```

---

# 10. Re-Link Subworkflows

Sanitized workflow exports cannot preserve production workflow IDs.

They therefore contain placeholders such as:

```text
REPLACE_WITH_SCRAPER_CONNECTION_TEST_WORKFLOW_ID
REPLACE_WITH_COMPANY_QUALIFICATION_WORKFLOW_ID
REPLACE_WITH_APPLICATION_QUEUE_BUILDER_WORKFLOW_ID
REPLACE_WITH_CONTACT_RESEARCH_WORKFLOW_ID
REPLACE_WITH_APPROVED_OUTREACH_SENDER_WORKFLOW_ID
```

After importing all workflows, open each `Execute Workflow` node and select the corresponding imported workflow manually.

Important dependencies include:

```text
Dashboard API - Discovery Action
    ├── Scraper Connection Test
    ├── Company Qualification
    └── Application Queue Builder

Dashboard API - Opportunity Action
    └── Contact Research

Dashboard API - Outreach Action
    └── Approved Outreach Sender
```

---

# 11. Configure Dashboard Webhook Authentication

The dashboard mutation/read endpoints use n8n Header Auth.

Create a strong random secret for the dashboard API.

Example:

```text
DASHBOARD_API_KEY=<your-own-random-secret>
```

Create an n8n Header Auth credential using the same secret.

Assign that credential to the dashboard webhook workflows.

The same secret must be provided to the Streamlit dashboard through its environment.

Do not commit the real value.

---

# 12. Configure the Dashboard Environment

Copy:

```text
.env.example
```

to:

```text
.env
```

The real `.env` file is ignored by Git.

Example:

```env
N8N_API_URL=http://localhost:5678/webhook/job-dashboard/opportunities

N8N_ACTION_URL=http://localhost:5678/webhook/job-dashboard/opportunity-action

N8N_OUTREACH_URL=http://localhost:5678/webhook/job-dashboard/outreach-action

N8N_FOLLOWUP_URL=http://localhost:5678/webhook/job-dashboard/follow-up-action

N8N_DISCOVERY_URL=http://localhost:5678/webhook/dashboard-discovery

DASHBOARD_API_KEY=replace_with_your_real_secret
```

If the dashboard and n8n are on the same Docker network, replace `localhost` with the n8n service/container hostname.

For example:

```text
http://n8n:5678/...
```

The exact hostname depends on your deployment.

---

# 13. Install the Dashboard

Open a terminal in:

```text
dashboard/
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it.

### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

The dashboard currently depends on:

```text
streamlit>=1.35,<2.0
requests>=2.31,<3.0
```

---

# 14. Run the Dashboard

From the `dashboard/` directory:

```bash
streamlit run app.py
```

The application contains the following pages:

```text
Active Opportunities
Manual Outreach
Processed
Follow-ups
Replies
```

Streamlit normally starts a local web interface and prints the local URL in the terminal.

The original containerized deployment exposed the dashboard on port:

```text
8501
```

---

# 15. Install the Scraper

Open a separate terminal in:

```text
scraper/
```

Create another virtual environment:

```bash
python -m venv .venv
```

Activate it and install:

```bash
pip install -r requirements.txt
```

The scraper dependencies are:

```text
fastapi>=0.115,<1
uvicorn[standard]>=0.30,<1
scrapling[fetchers]==0.4.10
python-dateutil>=2.9,<3
```

---

# 16. Run the Scraper

From the `scraper/` directory:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

The service exposes:

```text
GET /health
GET /discover-test
GET /article-details
```

The production n8n discovery workflow originally reached the scraper through:

```text
http://startup-scraper:8000
```

That hostname assumes a Docker network with a service/container named:

```text
startup-scraper
```

If you run the scraper directly on your local machine, update the relevant n8n HTTP Request nodes to use an address reachable from the n8n runtime.

For example, depending on how n8n itself is running, that may be:

```text
http://localhost:8000
```

or another host address accessible from the n8n container.

---

# 17. Gmail OAuth

The following workflows require Gmail access:

```text
Approved Outreach Sender
Gmail Reply Monitor
Dashboard API - Follow-up Action
```

Create a Gmail OAuth2 credential in n8n and assign it to the Gmail nodes.

The sending workflow uses Gmail to send the initial approved email.

The reply monitor searches incoming messages.

The follow-up action replies in the original Gmail thread.

Use a test mailbox or send to yourself when validating the configuration for the first time.

---

# 18. Google Drive Resume Attachment

`Approved Outreach Sender` downloads the resume from Google Drive before sending.

The selected `Application_Tracker` row must contain:

```text
resume_file_id
resume_filename
```

The resume is expected to be a PDF.

The configured Google credential must have permission to read the corresponding Drive file.

For testing, use a non-sensitive sample PDF or your own test resume.

---

# 19. Candidate Profile Configuration

The public workflows contain generalized candidate/profile placeholders.

Before running the system for your own use, review the AI prompt nodes and replace values such as:

```text
YOUR_NAME
https://example.com/portfolio
https://github.com/your-username
https://linkedin.com/in/your-profile
```

Also review the candidate profile text used by:

- discovery analysis,
- contact research,
- personalization,
- outreach drafting,
- follow-up drafting.

Keep this information factual and current.

---

# 20. Recommended Activation Order

Do not activate every workflow immediately after import.

Configure and test them in this order.

## Step 1 — Scraper

Verify:

```text
GET /health
```

and then test:

```text
GET /discover-test
```

## Step 2 — Scraper Connection Test

Run the workflow manually.

Verify:

- scraper connectivity;
- article discovery;
- Google Sheets access;
- Vertex AI access;
- new rows in `Companies`.

## Step 3 — Company Qualification

Run manually.

Verify:

- company website scanning;
- careers-page discovery;
- `Company_Qualification` records.

## Step 4 — Application Queue Builder

Run manually.

Verify:

- direct opportunity creation;
- speculative opportunity creation;
- duplicate protection;
- new `Application_Tracker` rows.

## Step 5 — Dashboard API - List Opportunities

Test the authenticated webhook and confirm that the dashboard receives opportunity data.

## Step 6 — Streamlit Dashboard

Run the dashboard and verify:

- opportunities load;
- filters work;
- cards render correctly.

## Step 7 — Opportunity Actions

Test with synthetic or controlled records.

Verify actions such as:

```text
mark_applied
skip
explore_adjacent
explore_speculative
```

## Step 8 — Contact Research

Test with one opportunity.

Verify:

- Brave Search;
- Hunter;
- contact candidate persistence;
- selected contact;
- draft generation.

## Step 9 — Outreach Save

Use:

```text
save_draft
```

before testing real sending.

Verify that edited drafts are stored correctly.

## Step 10 — Email Sending

Only after the previous stages work, test:

```text
approve_and_send
```

using a safe test recipient.

Verify:

- resume attachment;
- Gmail send result;
- `sent_at`;
- Gmail message ID;
- Gmail thread ID.

## Step 11 — Reply Monitor

Send a reply to the test thread and manually execute the monitor.

Verify:

```text
response_status = REPLIED
```

## Step 12 — Follow-Up

For a controlled test record, verify:

- due-date detection;
- draft generation;
- save action;
- approval;
- threaded Gmail reply.

Only activate the scheduled workflows after successful manual testing.

---

# 21. Scheduled Workflows

Two workflows are designed for periodic execution:

```text
Gmail Reply Monitor
Follow-up Draft Generator
```

The public exports contain their scheduling logic.

Before enabling them:

- confirm Gmail credentials;
- confirm Google Sheets access;
- confirm test campaigns behave correctly;
- confirm follow-up dates and reply detection;
- ensure no production records should be contacted unexpectedly.

---

# 22. Docker Deployment

The original deployment ran the Python services and n8n as separate Docker containers.

A simplified architecture is:

```text
Docker network
│
├── n8n
├── startup-scraper
└── job-outreach-dashboard
```

The scraper originally listened on:

```text
8000
```

The Streamlit dashboard originally listened on:

```text
8501
```

More deployment context is available in:

```text
docs/deployment.md
```

The repository does not currently provide a production-ready Docker Compose file because the original deployment configuration contained instance-specific runtime information and was intentionally not published.

---

# 23. Security Notes

Before activating the project:

- use your own secrets;
- never commit `.env`;
- never publish n8n runtime databases;
- never publish Docker inspect output from a live environment;
- keep administrative interfaces private;
- verify webhook authentication;
- test sending with your own account first;
- review AI-generated content before approval.

See:

```text
docs/security.md
```

for the security model and public-repository boundaries.

---

# 24. Public Sample Data

The files under:

```text
samples/
```

are synthetic.

They are intended to explain the data model and provide safe example records.

They do not represent production contacts or applications.

If you create a real deployment, keep your production workbook outside the repository.

---

# 25. Troubleshooting

## Dashboard reports a missing environment variable

Check that the relevant variable exists in the environment where Streamlit is running.

Required values include:

```text
N8N_API_URL
N8N_ACTION_URL
N8N_OUTREACH_URL
N8N_FOLLOWUP_URL
DASHBOARD_API_KEY
```

`N8N_DISCOVERY_URL` can be configured explicitly.

---

## Dashboard cannot reach n8n

Verify that:

- n8n is running;
- the webhook workflow is active;
- the URL is correct;
- the dashboard API key matches the n8n Header Auth credential;
- the hostname is reachable from the dashboard process/container.

---

## n8n cannot reach the scraper

The public discovery workflow retains the original Docker-network hostname:

```text
http://startup-scraper:8000
```

If your environment uses another hostname, edit the scraper HTTP Request nodes.

---

## Google Sheets nodes fail

Verify:

- the workbook ID;
- the selected sheet name;
- credential permissions;
- sheet headers.

Use the sample CSV headers as a reference.

---

## Execute Workflow node cannot find its target

Re-open the node and manually select the imported dependent workflow.

The production workflow IDs were intentionally removed from the public exports.

---

## Gmail sending is blocked

This may be expected.

The sender intentionally checks multiple conditions, including:

```text
outreach_approval = APPROVED
outreach_status = DRAFT_READY
draft_final_status = READY
```

It also checks:

- contact email;
- email confidence;
- resume availability;
- previous send state;
- campaign duplication.

See:

```text
docs/workflow-design.md
```

for the complete send-gate behavior.

---

# 26. Before Activating Production-Like Use

Complete this checklist:

```text
[ ] Google Sheet created with all four schemas
[ ] Google credential configured
[ ] Gmail OAuth configured
[ ] Google Drive access configured
[ ] Vertex AI project configured
[ ] Brave Search credential configured
[ ] Hunter credential configured
[ ] Dashboard Header Auth configured
[ ] Dashboard .env created locally
[ ] All subworkflow references re-linked
[ ] Scraper reachable from n8n
[ ] Dashboard reachable from your browser
[ ] Discovery tested manually
[ ] Qualification tested manually
[ ] Queue builder tested manually
[ ] Contact research tested with controlled data
[ ] Draft save tested
[ ] Initial send tested with a safe recipient
[ ] Reply monitor tested
[ ] Follow-up flow tested
[ ] Scheduled workflows reviewed before activation
```

Once these checks pass, workflows can be activated selectively.
