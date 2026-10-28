# Data Model

## Overview

The platform uses Google Sheets as a lightweight operational state store.

Rather than storing all information in one large table, the system separates data into four logical datasets:

```text
Companies
Company_Qualification
Application_Tracker
Contact_Candidates
```

Each dataset represents a different stage of the job-search lifecycle.

The relationships between them are based primarily on normalized identifiers such as:

```text
company_key
opportunity_key
company_domain
```

The system relies on these deterministic identifiers to support deduplication, repeatable workflow execution, and state tracking.

---

# High-Level Data Relationships

Conceptually:

```text
Companies
    │
    │ company identity derived from company_name / company_website
    ▼
Company_Qualification
    │
    │ company_key
    ▼
Application_Tracker
    │
    │ opportunity_key
    ▼
Contact_Candidates
```

`company_key` is created during qualification; it is not stored as a column in the `Companies` sheet.

The relationship is not implemented as a traditional relational database with foreign-key constraints.

Instead, workflows maintain consistency through deterministic keys and explicit state fields.

---

# 1. Companies

The `Companies` dataset stores organizations discovered by the discovery pipeline.

Each record represents a company extracted from a source article or discovery event.

Its purpose is to preserve the original discovery context before deeper qualification begins.

---

## Core Identity Fields

The stored identity-related fields are:

```text
company_name
company_website
official_website_scraped
```

### `company_name`

Human-readable company name extracted during discovery.

Example:

```text
Example AI Labs
```

`company_key` and `company_domain` are derived later by the qualification workflow and are stored from `Company_Qualification` onward; they are not columns in `Companies`.

### `company_website`

Resolved company website used by later qualification steps.

### `official_website_scraped`

Website detected during the initial discovery process.

This field is preserved as source evidence even when a later workflow identifies a more appropriate canonical website.

---

# Discovery Metadata

Company records may also include fields such as:

```text
article_url
article_title
published_at
source
country
location
sector
pipeline_status
```

These fields preserve where the company was discovered and the context associated with that discovery.

---

## Article URL

The original source article.

URLs are normalized before deduplication by removing elements such as:

```text
query parameters
fragments
trailing slashes
```

This prevents multiple representations of the same article from creating duplicate company records.

---

# AI Analysis Fields

The discovery workflow can also store structured analysis fields.

Examples include:

```text
profile_fit_score
profile_fit_evidence
profile_fit_inference
hiring_signal
hiring_evidence
recommended_roles
research_priority
confidence_score
```

These values represent an initial interpretation of the article.

They do not represent final qualification.

---

## `profile_fit_score`

Numerical estimate of how relevant the company appears to the candidate profile.

The score is based only on evidence available in the source material.

---

## `hiring_signal`

Indicates whether the source contains evidence suggesting company growth or hiring relevance.

The system does not interpret every funding announcement as proof that a specific role is available.

---

## `recommended_roles`

Possible role categories suggested by the available evidence.

These are exploratory signals rather than confirmed vacancies.

---

# 2. Company_Qualification

The `Company_Qualification` dataset stores the result of deeper company-level analysis.

A company reaches this stage after discovery.

The qualification workflow checks additional information such as:

```text
company website
careers page
relevant vacancies
company context
role relevance
available visa evidence
```

---

# Primary Identifier

The main logical link to the `Companies` dataset is:

```text
company_key
```

Conceptually:

```text
Companies.company_key
        │
        ▼
Company_Qualification.company_key
```

---

# Qualification State

Important fields include values such as:

```text
qualification_status
qualification_score
qualification_reason
qualification_version
```

---

## `qualification_status`

Represents whether the company passed the qualification logic.

For example:

```text
QUALIFIED
```

Other statuses may represent companies that do not currently justify creating an opportunity.

---

## `qualification_score`

Numerical result of the qualification process.

The qualification score represents a deeper evaluation than the initial discovery fit score.

---

## `qualification_reason`

Human-readable explanation supporting the qualification decision.

This allows the dashboard and later workflows to expose why a company was considered relevant.

---

## `qualification_version`

Version of the qualification logic used to produce the record.

Example:

```text
3
```

This is important because qualification logic evolves over time.

A workflow can identify records produced by an older version and selectively reprocess them.

Conceptually:

```text
qualification_version < current_version
        │
        ▼
Requalification required
```

---

# Website and Careers Information

The qualification dataset can contain fields such as:

```text
careers_url
careers_page_status
relevant_vacancy_urls
```

These allow later workflows to distinguish between companies with matching public roles and companies suitable only for speculative outreach.

---

# Careers Page State

The current qualification schema stores website/careers discovery in:

```text
careers_page_status
```

Observed workflow values include:

```text
CAREERS_PAGE_FOUND
CAREERS_PAGE_POSSIBLE
CAREERS_PAGE_NOT_FOUND
CAREERS_PAGE_UNREACHABLE
```

This distinction matters because no relevant vacancy is not equivalent to an unreachable careers page. A more explicit persisted homepage-fetch failure state remains a future hardening improvement.

---

# Opportunity Type

One of the most important outputs of qualification is:

```text
opportunity_type
```

The system distinguishes primarily between:

```text
DIRECT_APPLICATION
SPECULATIVE_OUTREACH
```

---

## DIRECT_APPLICATION

Used when evidence exists for a relevant public vacancy.

Typically requires:

```text
qualification_status = QUALIFIED
```

and at least one relevant vacancy URL.

---

## SPECULATIVE_OUTREACH

Used when the company is sufficiently relevant but no suitable public vacancy is currently available.

This allows the company to remain actionable without presenting speculation as a real vacancy.

---

# 3. Application_Tracker

`Application_Tracker` is the central operational dataset.

It represents individual opportunities and their lifecycle.

While `Companies` represents organizations and `Company_Qualification` represents company-level evaluation, `Application_Tracker` represents actionable job-search records.

---

# Primary Identifier

Each opportunity receives:

```text
opportunity_key
```

This is a deterministic identifier used to prevent duplicate opportunity creation.

---

# Company Relationship

Opportunity records retain:

```text
company_key
company_name
company_domain
```

Conceptually:

```text
Company_Qualification.company_key
            │
            ▼
Application_Tracker.company_key
```

---

# Opportunity Fields

Typical opportunity information includes:

```text
opportunity_key
opportunity_type
company_key
company_name
company_domain
country
position_title
vacancy_url
qualification_score
qualification_reason
visa_support_status
```

---

# Application State

The tracker contains state fields such as:

```text
application_status
```

Examples include:

```text
TO_REVIEW
APPLY
APPLIED
SKIPPED
```

The dashboard uses this field to determine how opportunities should be presented.

---

# Outreach Strategy

Outreach behavior is represented separately from application state.

Important fields include:

```text
outreach_mode
outreach_status
outreach_approval
```

Possible outreach modes include:

```text
ADJACENT_ROLE
SPECULATIVE
```

This separation matters because a user may:

- apply directly and then contact someone,
- explore an adjacent role,
- or perform speculative outreach without a public application.

---

# Contact State

Once contact research begins, the tracker may contain:

```text
contact_name
contact_role
contact_email
contact_linkedin_url
contact_email_confidence
contact_source
```

---

## Email Confidence

Email addresses are not treated equally.

Confidence values can include:

```text
HIGH
MEDIUM
USER_VERIFIED
```

The sending workflow explicitly checks confidence before allowing email delivery.

This prevents low-confidence automatically generated addresses from immediately becoming outbound messages.

---

# Manual Contact State

The dashboard supports manually supplied contacts.

Relevant fields include concepts such as:

```text
manual_contact_status
contact_source
```

A manually verified contact can be marked:

```text
USER_VERIFIED
```

so that the workflow can distinguish user-confirmed information from automatically researched information.

---

# Draft Fields

Generated communication is stored directly alongside the opportunity state.

Typical fields include:

```text
email_subject
email_draft
linkedin_connection_note
linkedin_message
draft_final_status
```

This allows drafts to be:

```text
generated
reviewed
edited
saved
approved
```

without losing association with the opportunity.

---

# Approval State

The system explicitly records approval rather than assuming that draft generation implies authorization.

Important fields include:

```text
outreach_approval
draft_final_status
```

Typical required states before sending include:

```text
outreach_approval = APPROVED

draft_final_status = READY

outreach_status = DRAFT_READY
```

These are independent checks.

---

# Email Sending State

After an approved email is sent, the tracker stores Gmail-related identifiers.

Typical fields include:

```text
sent_at
gmail_message_id
gmail_thread_id
```

These identifiers allow later workflows to monitor replies without relying only on recipient or subject matching.

---

# Reply State

Reply monitoring adds fields such as:

```text
response_status
reply_detected_at
```

A typical initial state is:

```text
NO_RESPONSE
```

Once a response is detected, the workflow updates the opportunity so that unnecessary follow-ups are prevented.

---

# Follow-Up State

Follow-up state is stored primarily in:

```text
follow_up_status
follow_up_date
follow_up_approval
follow_up_sent_at
```

Current `follow_up_status` values used by the workflows include:

```text
NOT_STARTED
DRAFT_READY
FAILED
SENDING
SENT
```

A follow-up becomes *due* when `follow_up_date` has been reached while the campaign is still eligible; `FOLLOW_UP_DUE` is therefore not the main persisted `follow_up_status` in the current workflow.

The workflow checks existing campaign identity before creating follow-up actions, preventing multiple opportunity records associated with the same company/contact from generating competing follow-ups.

---

# Update Protection

The tracker also includes fields that control whether automated workflows are allowed to modify records.

One example is:

```text
can_update_tracker
```

This acts as a safety/control signal for state mutation.

The dashboard API workflows validate actions before updating records.

---

# 4. Contact_Candidates

The `Contact_Candidates` dataset stores people discovered during contact research.

Instead of returning only one final person, the system preserves candidate contacts and supporting evidence.

This makes the research process more transparent and auditable.

---

# Opportunity Relationship

Contact candidates are associated with an opportunity through:

```text
opportunity_key
```

Conceptually:

```text
Application_Tracker.opportunity_key
              │
              ▼
Contact_Candidates.opportunity_key
```

Multiple candidate contacts can therefore exist for one opportunity.

---

# Candidate Identity

Typical fields include:

```text
contact_name
contact_role
contact_email
contact_linkedin_url
```

---

# Evidence Fields

Research information may include:

```text
contact_source
evidence
email_confidence
```

The system uses external evidence rather than assuming that an AI-generated contact name is correct.

---

# Candidate Ranking

Candidate contacts can be evaluated based on factors such as:

```text
role relevance
company relevance
available evidence
email confidence
source quality
```

The objective is to identify useful contacts without pretending that the ranking is certain.

---

# Contact Selection

The selected contact is eventually copied into the corresponding `Application_Tracker` record.

Conceptually:

```text
Contact_Candidates
       │
       │ human / workflow selection
       ▼
Application_Tracker
```

This allows all later outreach workflows to operate from one central opportunity record.

---

# Deterministic Keys

Deterministic identifiers are one of the most important parts of the data model.

The platform avoids relying exclusively on generated UUIDs for business identity.

Instead, normalization functions are used for objects such as:

```text
company domains
company names
article URLs
vacancy URLs
email addresses
LinkedIn URLs
```

---

# URL Normalization

A URL may be normalized by:

```text
removing query parameters
removing URL fragments
removing trailing slashes
converting to lowercase where appropriate
```

Example:

```text
https://example.com/jobs/123/?ref=linkedin#apply
```

becomes approximately:

```text
https://example.com/jobs/123
```

---

# Domain Normalization

Domains are normalized by removing elements such as:

```text
https://
http://
www.
paths
query strings
trailing dots
```

Example:

```text
https://www.example.com/careers
```

becomes:

```text
example.com
```

---

# Email Normalization

Email identities are typically normalized using:

```text
trim
lowercase
```

Example:

```text
Alex@Example.com
```

becomes:

```text
alex@example.com
```

---

# LinkedIn Normalization

LinkedIn URLs may be normalized by removing:

```text
query parameters
fragments
trailing slashes
```

This allows the system to recognize the same contact even when URLs arrive in slightly different forms.

---

# Deduplication Model

The platform performs deduplication at several stages.

## Article Level

Prevents repeatedly processing the same source article.

---

## Company Level

Prevents multiple discovered articles from unnecessarily creating duplicate company qualification work.

---

## Opportunity Level

Prevents the same vacancy or speculative campaign from being inserted repeatedly.

---

## Contact Level

Avoids duplicate contact candidates produced by different research sources.

---

## Campaign Level

Prevents multiple opportunity records from sending equivalent outreach to the same company/contact.

---

# Historical vs Same-Run Deduplication

Two different duplicate cases are handled.

## Historical Duplicate

The record already exists from a previous workflow execution.

```text
incoming key
     │
     ▼
existing key Set
     │
     ▼
skip
```

---

## Same-Run Duplicate

Two items in the current execution resolve to the same normalized key.

```text
incoming item 1 ─► key A ─► accept
incoming item 2 ─► key A ─► skip
```

A second in-memory `Set` is used to prevent these duplicates before persistence.

---

# State Machine

The `Application_Tracker` can be understood as a lightweight state machine.

A simplified lifecycle is:

```text
TO_REVIEW
    │
    ├────────► SKIPPED
    │
    ▼
APPLY
    │
    ▼
APPLIED
    │
    ▼
CONTACT_RESEARCH
    │
    ▼
DRAFT_READY
    │
    ▼
APPROVED
    │
    ▼
SENT
    │
    ├────────► REPLIED
    │
    ▼
follow_up_date becomes due
    │
    ▼
DRAFT_READY
    │
    ▼
APPROVED / SENDING
    │
    ▼
SENT (follow_up_status)
```

Speculative outreach follows a slightly different branch:

```text
TO_REVIEW
    │
    ▼
SPECULATIVE
    │
    ▼
CONTACT_RESEARCH
    │
    ▼
DRAFT_READY
    │
    ▼
APPROVED
    │
    ▼
SENT
```

The actual implementation uses several separate fields rather than placing the entire lifecycle in one status column.

That avoids overloading a single field with unrelated concepts.

---

# Why Multiple State Fields Are Used

For example:

```text
application_status
```

answers:

> What is the application state?

while:

```text
outreach_mode
```

answers:

> What outreach strategy is being used?

and:

```text
outreach_status
```

answers:

> What stage has the outreach process reached?

Similarly:

```text
response_status
```

answers:

> Has the recipient responded?

These dimensions can change independently.

---

# Example

A direct application with an approved outreach draft might conceptually look like:

```text
opportunity_type = DIRECT_APPLICATION

application_status = APPLIED

outreach_mode = ADJACENT_ROLE

outreach_status = DRAFT_READY

outreach_approval = APPROVED

draft_final_status = READY

response_status = NO_RESPONSE
```

A speculative opportunity could instead be:

```text
opportunity_type = SPECULATIVE_OUTREACH

application_status = TO_REVIEW

outreach_mode = SPECULATIVE

outreach_status = DRAFT_READY

outreach_approval = APPROVED
```

This multidimensional state model allows the system to represent more complex cases than one linear status value.

---

# Why Google Sheets Was Used

Google Sheets was selected as the operational store because the project initially prioritized:

- fast iteration,
- easy visual inspection,
- manual corrections,
- straightforward integration with n8n,
- and low infrastructure overhead.

For the current project scale, this provides a practical balance between automation and observability.

---

# Limitations

Google Sheets is not intended to replace a production database.

As the system grows, limitations include:

```text
API rate limits
weak relational constraints
limited transactional guarantees
concurrent update risks
schema management
query performance
```

The project already encountered Google Sheets API rate limits, which required replacing per-item lookups with bulk reads and in-memory comparisons.

---

# Possible Future Migration

A larger version of the platform could move the operational state to a relational database such as:

```text
PostgreSQL
```

The logical entities would map naturally to tables such as:

```text
companies
company_qualifications
opportunities
contacts
outreach_campaigns
messages
```

The existing deterministic identifiers could remain as unique business keys.

Google Sheets could then remain available as a reporting or manual-review surface rather than acting as the primary state store.

---

# Public Repository Data

The public repository does not contain the production workbook.

Real company/contact/application data is intentionally excluded.

The repository will instead provide synthetic examples under:

```text
samples/
```

Planned files include:

```text
companies.sample.csv
company-qualification.sample.csv
application-tracker.sample.csv
contact-candidates.sample.csv
```

These samples will reproduce the structure needed to understand the workflows without exposing real application or contact information.