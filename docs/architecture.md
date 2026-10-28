# System Architecture

## Overview

The AI-Powered Job Discovery & Outreach Automation Platform is designed as a set of loosely coupled services coordinated through n8n.

Instead of placing scraping, AI analysis, state management, user interaction, and email delivery inside one application, the system separates these responsibilities into dedicated components.

The main architectural components are:

- **Streamlit dashboard** for human review and actions
- **n8n** for orchestration and workflow state transitions
- **FastAPI scraper** for startup and article discovery
- **Google Sheets** as the operational data store
- **Vertex AI / LLM nodes** for structured analysis and drafting
- **Brave Search and Hunter** for contact research
- **Gmail API** for approved email delivery and reply monitoring
- **Docker** for service isolation
- **Google Cloud VM** for the original deployment environment
- **Tailscale** for private administrative access

The design follows a human-in-the-loop approach: automation performs repetitive processing, while the user keeps control over decisions such as opportunity selection, contact choice, outreach approval, and sending.

---

## High-Level Architecture

Conceptually, the system follows this flow:

```text
External Sources
       │
       ▼
FastAPI Scraper
       │
       ▼
n8n Discovery Workflows
       │
       ├──────────────► Vertex AI
       │
       ▼
Google Sheets
       │
       ▼
Streamlit Dashboard
       │
       ▼
n8n Action Workflows
       │
       ├──────────────► Brave Search
       ├──────────────► Hunter
       ├──────────────► Vertex AI
       │
       ▼
Human Review / Approval
       │
       ▼
Gmail API
       │
       ▼
Reply Monitoring / Follow-ups
```

The architecture intentionally separates the **user interface**, **workflow orchestration**, **data storage**, **AI reasoning**, and **external integrations**.

---

# Components

## 1. Streamlit Dashboard

The Streamlit application is the main human-facing interface.

Source code:

```text
dashboard/
```

Its role is not to reproduce the business logic already implemented in n8n.

Instead, it acts as a control layer that:

- retrieves opportunities,
- displays qualification information,
- exposes application state,
- allows users to review opportunities,
- triggers exploration actions,
- displays researched contacts,
- allows outreach drafts to be edited,
- submits approval decisions,
- manages follow-up actions,
- and displays reply state.

The dashboard communicates with n8n through authenticated webhook endpoints.

It does not directly modify the underlying Google Sheets data.

This keeps workflow state transitions centralized inside the orchestration layer.

---

## 2. n8n Orchestration Layer

n8n is the central orchestration engine.

The project contains several workflows grouped into three logical areas.

### Discovery

```text
workflows/discovery/
```

Contains:

```text
Scraper Connection Test
Company Qualification
Application Queue Builder
```

Responsibilities include:

- triggering the scraper,
- filtering previously processed articles,
- analyzing companies,
- qualifying employers,
- inspecting career information,
- detecting vacancies,
- generating opportunity records,
- and deduplicating opportunities.

---

### Dashboard API

```text
workflows/dashboard-api/
```

These workflows form the API boundary between Streamlit and the automation backend.

They expose authenticated webhook endpoints for:

- retrieving opportunities,
- triggering discovery,
- updating opportunity status,
- saving manual contacts,
- starting contact research,
- saving outreach drafts,
- approving outreach,
- and managing follow-up actions.

This allows the dashboard to remain relatively lightweight.

---

### Contact and Outreach

```text
workflows/outreach/
```

Contains:

```text
Contact Research
Approved Outreach Sender
Follow-up Draft Generator
Gmail Reply Monitor
```

Responsibilities include:

- finding possible company contacts,
- gathering contact evidence,
- verifying email information,
- ranking contact candidates,
- generating personalized outreach,
- enforcing approval gates,
- sending approved emails,
- detecting replies,
- and preparing follow-ups.

---

# 3. FastAPI Scraper

The scraper is implemented as a standalone Python service.

Source:

```text
scraper/
```

The service exposes endpoints such as:

```text
GET /health
GET /discover-test
GET /article-details
```

Its responsibilities are limited to retrieving and parsing source material.

It performs tasks such as:

- scanning startup-related article listings,
- extracting article URLs,
- identifying relevant funding-related articles,
- retrieving individual article pages,
- extracting article text,
- and returning structured results to n8n.

The scraper does not make application decisions itself.

Those decisions remain in the workflow layer.

---

# 4. Google Sheets State Store

Google Sheets acts as the lightweight operational database for the system.

The main logical datasets are:

```text
Companies
Company_Qualification
Application_Tracker
Contact_Candidates
```

Each sheet serves a different part of the lifecycle.

## Companies

Stores discovered company-level information and source metadata.

Typical information includes:

- company name,
- normalized company key,
- domain,
- source article,
- country,
- sector,
- company website,
- discovery context,
- and hiring-related signals.

---

## Company_Qualification

Stores the result of the company qualification process.

This includes information such as:

- qualification status,
- qualification score,
- qualification reason,
- careers URL,
- relevant vacancies,
- opportunity type,
- visa-related evidence when available,
- and qualification version.

Versioning allows the system to identify companies that require reprocessing after qualification logic changes.

---

## Application_Tracker

Acts as the central opportunity-state table.

An opportunity may represent either:

```text
DIRECT_APPLICATION
```

or:

```text
SPECULATIVE_OUTREACH
```

The tracker stores information related to:

- application status,
- outreach mode,
- opportunity identity,
- contact selection,
- email confidence,
- generated drafts,
- approval state,
- send status,
- Gmail message/thread IDs,
- reply state,
- follow-up status,
- and timestamps.

This table functions as the primary state machine for the application and outreach lifecycle.

---

## Contact_Candidates

Stores possible contacts discovered during research.

Candidate records may contain:

- contact name,
- role,
- company,
- LinkedIn URL,
- email address,
- confidence,
- source evidence,
- relevance score,
- and selection status.

This allows contact discovery to remain auditable rather than simply returning one opaque AI-generated choice.

---

# Data Flow

## Discovery Flow

The discovery pipeline begins when the user triggers:

```text
Find new opportunities
```

from the Streamlit dashboard.

The dashboard sends an authenticated request to:

```text
Dashboard API - Discovery Action
```

which orchestrates the discovery sequence.

The flow is approximately:

```text
Streamlit
    │
    ▼
Dashboard Discovery Webhook
    │
    ▼
Scraper Connection Test
    │
    ▼
FastAPI Scraper
    │
    ▼
New Article Filtering
    │
    ▼
Company Analysis
    │
    ▼
Companies
    │
    ▼
Company Qualification
    │
    ▼
Company_Qualification
    │
    ▼
Application Queue Builder
    │
    ▼
Application_Tracker
```

---

# Article Deduplication

The scraper may rediscover articles that were processed during previous runs.

Instead of performing one Google Sheets request for every article, the workflow loads existing article records once.

The existing URLs are normalized and placed into an in-memory JavaScript `Set`.

Incoming URLs are then compared locally.

The workflow also maintains a second `Set` for duplicates appearing during the same execution.

Conceptually:

```text
Scraped Articles
       +
Existing Article URLs
       │
       ▼
Normalize URLs
       │
       ▼
In-Memory Set Comparison
       │
       ▼
Only New Articles
```

This avoids excessive external API calls and makes discovery idempotent.

---

# Company Analysis

New articles are processed by an AI analysis step.

The model receives:

- article content,
- source metadata,
- candidate profile context,
- and strict analysis instructions.

The prompt explicitly prevents unsupported assumptions.

For example, the model is instructed not to infer that a technical company necessarily needs AI engineers or that a company provides visa sponsorship unless supporting evidence exists.

The result is structured before being stored.

---

# LLM Request Pacing

Running several AI requests simultaneously initially caused model API rate-limit errors.

The workflow therefore serializes company analysis:

```text
Loop Over Items
       │
       ▼
Analyze Company
       │
       ▼
Wait
       │
       └────► Next Item
```

This trades some execution speed for reliability and predictable request pacing.

---

# Qualification Flow

Once companies have been discovered, the qualification workflow determines whether each company should generate an opportunity.

The workflow performs operations such as:

```text
Load Companies
       │
       ▼
Deduplicate Companies
       │
       ▼
Check Existing Qualifications
       │
       ▼
Determine Whether Requalification Is Needed
       │
       ▼
Inspect Website / Careers Information
       │
       ▼
Analyze Qualification
       │
       ▼
Persist Result
```

The system distinguishes between:

```text
DIRECT_APPLICATION
```

and:

```text
SPECULATIVE_OUTREACH
```

A direct application requires evidence of a relevant public vacancy.

A speculative opportunity allows the system to retain promising employers even when no matching vacancy is currently available.

---

# Opportunity Identity

Each opportunity receives a deterministic key.

The key is derived from normalized information rather than relying on random IDs.

This makes it possible to detect:

- opportunities already processed during previous runs,
- duplicate vacancies,
- duplicate speculative campaigns,
- and duplicates generated during the same execution.

The Application Queue Builder therefore performs both:

```text
historical deduplication
```

and:

```text
same-run deduplication
```

before writing new opportunities.

---

# Human Review Flow

After opportunities are stored, the Streamlit dashboard retrieves them through:

```text
Dashboard API - List Opportunities
```

The user can then decide how to proceed.

Examples include:

```text
Mark as applied
Skip
Explore adjacent roles
Explore speculative outreach
Add a manual contact
Move to manual outreach
```

These actions are submitted back to dedicated n8n webhook workflows.

This design ensures that application state is not changed directly inside the Streamlit interface.

---

# Contact Research Flow

When outreach is requested, the Contact Research workflow collects evidence from several sources.

The process includes:

```text
Opportunity
     │
     ▼
Company / Role Context
     │
     ├────► Search Engine Evidence
     │
     ├────► Hunter Domain Search
     │
     ├────► Hunter Email Finder
     │
     ▼
Candidate Contacts
     │
     ▼
Evidence Processing
     │
     ▼
Candidate Ranking
     │
     ▼
Contact_Candidates
```

Relevant contacts may include people working in:

- recruitment,
- talent acquisition,
- engineering,
- AI/data teams,
- technical leadership,
- or other roles appropriate to the opportunity.

The system retains supporting evidence rather than relying only on an LLM-generated name.

---

# Manual Contact Fallback

Automated research will not always find a reliable contact.

For this reason, the system provides a manual fallback.

The user can add:

- a contact name,
- role,
- email,
- LinkedIn URL,
- or another manually verified source.

Manual contacts receive a distinct confidence state such as:

```text
USER_VERIFIED
```

This allows the workflow to continue without pretending that automatic research succeeded.

---

# Outreach Generation

Once a contact has been selected, the system gathers context required to prepare outreach.

Separate drafts are produced for:

```text
Email
LinkedIn connection note
LinkedIn direct message
```

The drafting prompt uses evidence already collected during the workflow.

It explicitly avoids language that would imply knowledge the system does not possess.

Examples of prohibited behavior include:

- inventing company projects,
- assuming technologies are used internally,
- assuming technical challenges,
- overstating the candidate's relevance,
- and making unsupported claims about hiring.

The objective is credible professional outreach rather than automated sales-style messaging.

---

# Approval and Sending

Generated outreach is never sent immediately.

The dashboard first presents the drafts to the user.

The user can:

```text
edit
save
approve
```

the content.

Only after approval can the Approved Outreach Sender execute.

The sender verifies several independent conditions before sending.

Conceptually:

```text
Eligible Opportunity?
       │
       ▼
Approved?
       │
       ▼
Draft Ready?
       │
       ▼
Final Status Ready?
       │
       ▼
Valid Contact Email?
       │
       ▼
Acceptable Confidence?
       │
       ▼
Already Sent?
       │
       ▼
Send Email
```

This prevents an AI-generated draft from becoming an automatically sent message without human review.

---

# Gmail Integration

Approved emails are sent through Gmail.

After sending, the workflow stores identifiers such as:

```text
gmail_message_id
gmail_thread_id
sent_at
```

These identifiers allow later workflows to monitor the conversation.

The reply-monitoring workflow primarily monitors sent campaigns and matches incoming messages by Gmail thread ID. It also accepts legacy outreach-status labels such as `FOLLOW_UP_DUE` and `FOLLOW_UP_SENT` for compatibility, while current follow-up state is tracked separately through `follow_up_status`, `follow_up_date`, and related fields. Campaigns with an already detected response are ignored.

---

# Follow-Up Lifecycle

The system can identify outreach campaigns that have not received a response.

Before generating or sending a follow-up, campaign identity is normalized using signals such as:

- company domain,
- contact email,
- LinkedIn identity,
- and company name.

This prevents multiple opportunity records related to the same contact or company from creating competing follow-up campaigns.

The human-in-the-loop principle remains in place for follow-up actions.

---

# Service Boundaries

The system deliberately assigns different responsibilities to different components.

## FastAPI

Responsible for:

```text
web retrieval
article extraction
structured scraper responses
```

Not responsible for:

```text
application decisions
contact selection
email sending
```

---

## n8n

Responsible for:

```text
workflow orchestration
data transformation
business rules
state transitions
API integrations
AI orchestration
```

---

## Streamlit

Responsible for:

```text
presentation
human review
user actions
draft editing
approval
```

---

## Google Sheets

Responsible for:

```text
persistent operational state
```

---

## LLMs

Responsible for:

```text
structured interpretation
classification
context synthesis
draft generation
```

They are not treated as the authoritative source of workflow state.

---

# Deployment Architecture

The original system was self-hosted on a Google Cloud VM.

Services ran as Docker containers.

Conceptually:

```text
Google Cloud VM
│
├── n8n container
│
├── Streamlit dashboard container
│
├── FastAPI scraper container
│
└── Tailscale
```

The dashboard and scraper communicated with n8n through internal/private networking.

Administrative interfaces were accessed privately using Tailscale rather than intentionally exposing them as public management interfaces.

More deployment information is available in:

```text
docs/deployment.md
```

---

# Reliability Principles

Several architectural principles guide the system.

## Idempotency

Repeated execution should not continuously create duplicate:

- companies,
- articles,
- vacancies,
- opportunities,
- contacts,
- or outreach campaigns.

---

## Minimize External API Calls

External systems such as Google Sheets and AI APIs are accessed in batches or paced when possible.

---

## Deterministic State

Important workflow decisions are represented explicitly using fields such as:

```text
application_status
opportunity_type
outreach_mode
outreach_status
outreach_approval
draft_final_status
response_status
```

rather than relying on implicit workflow position.

---

## Evidence Before Automation

Contact research and company analysis preserve the evidence used to reach decisions.

---

## Human Approval at High-Impact Boundaries

Actions that communicate externally remain gated by explicit human decisions.

---

# Security Boundaries

Sensitive runtime configuration is not stored in the public source code.

The public repository excludes:

```text
API keys
OAuth tokens
n8n credentials
production environment variables
n8n SQLite databases
Docker inspection output
real contact information
real application records
private infrastructure identifiers
```

Configuration is injected through environment variables and n8n credentials.

The repository contains only:

```text
.env.example
```

with placeholder values.

---

# Architecture Diagrams

The repository includes four visual diagrams under:

```text
assets/diagrams/
```

They cover:

```text
system-architecture.png
workflow-overview.png
data-flow.png
opportunity-lifecycle.png
```

These diagrams provide a visual companion to the component, workflow, data-flow, and lifecycle descriptions in this document.
