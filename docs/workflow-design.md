# Workflow Design

## Overview

The platform is orchestrated through twelve n8n workflows grouped into three functional layers:

1. **Discovery and qualification** — discover companies, analyze source material, inspect careers pages, and create opportunities.
2. **Dashboard control layer** — expose authenticated webhook actions used by the Streamlit interface.
3. **Contact, outreach, reply, and follow-up automation** — research contacts, generate evidence-grounded drafts, enforce approval gates, send approved email, monitor replies, and prepare follow-ups.

The design intentionally separates automated processing from high-impact user decisions. Discovery, normalization, scoring, and state management are automated where appropriate; applying, choosing an outreach strategy, approving a draft, and sending communication remain human-controlled.

---

# Workflow Map

```text
Dashboard
   │
   ├── Dashboard API - Discovery Action
   │       │
   │       ├── Scraper Connection Test
   │       ├── Company Qualification
   │       └── Application Queue Builder
   │
   ├── Dashboard API - List Opportunities
   │
   ├── Dashboard API - Opportunity Action
   │       └── Contact Research
   │
   ├── Dashboard API - Outreach Action
   │       └── Approved Outreach Sender
   │
   └── Dashboard API - Follow-up Action
           └── Gmail threaded reply

Scheduled background workflows
   │
   ├── Gmail Reply Monitor
   └── Follow-up Draft Generator
```

The following sections document each workflow using the same structure:

- **Purpose**
- **Trigger**
- **Inputs**
- **Processing steps**
- **Outputs**
- **External services**
- **State changes**
- **Reliability considerations**
- **Human checkpoint**

---

# 1. Scraper Connection Test

## Purpose

Discovers recent startup-related articles, filters already processed material, extracts article details, uses an LLM to structure company-level information, and persists newly discovered companies to the `Companies` sheet.

Despite its historical name, this workflow functions as the main discovery pipeline.

## Trigger

The workflow can start in two ways:

- manual execution from n8n;
- execution as a subworkflow, primarily from `Dashboard API - Discovery Action`.

## Inputs

The scraper request is configured to discover articles across the supported target countries.

The discovery service returns article-level information including fields such as:

- article URL;
- title;
- publication date;
- country;
- source.

Existing `Companies` rows are also loaded so previously processed article URLs can be excluded.

## Processing Steps

1. Call the FastAPI scraper endpoint:
   ```text
   /discover-test
   ```

2. Split the returned `articles` collection into individual workflow items.

3. Read previously stored articles from the `Companies` sheet.

4. Normalize article URLs by removing:
   - query strings;
   - fragments;
   - trailing slashes;
   - casing differences.

5. Remove:
   - articles already processed in previous workflow runs;
   - duplicate article URLs returned during the same execution.

6. Fetch each new article through:
   ```text
   /article-details
   ```

7. Keep articles published within the last 24 months. If publication-date extraction fails, the article is retained rather than silently discarded.

8. Prepare the article for company analysis.

9. Process companies sequentially through `Loop Over Items`.

10. Run structured company analysis with Vertex AI.

11. Pause before continuing to the next item.

12. Normalize model output into deterministic fields.

13. Build a company record, including:
   - `company_key`;
   - `company_domain`;
   - hiring signal;
   - profile-fit information;
   - funding information;
   - recommended roles;
   - visa-support evidence when explicitly available;
   - research priority;
   - entity type.

14. Save the record into `Companies`.

## Outputs

New normalized company rows in the `Companies` sheet.

The workflow produces one company record per newly accepted discovery item.

## External Services

- FastAPI scraper service
- Vertex AI
- Google Sheets

## State Changes

New company records are persisted with discovery and analysis state such as:

```text
pipeline_status = RESEARCHED
analysis_version = 2
```

The workflow does not create application opportunities directly.

## Reliability Considerations

### Bulk duplicate lookup

Existing article URLs are loaded once rather than queried individually. This avoids unnecessary Google Sheets API calls.

### Historical and same-run deduplication

Two separate sets are used:

```text
existingUrls
seenThisRun
```

This prevents both previously processed and same-execution duplicates.

### Date-failure behavior

An article with an invalid or missing publication date is retained for inspection rather than being discarded automatically.

### LLM request pacing

The workflow serializes Vertex AI requests:

```text
Loop Over Items
→ Analyze Company Fit
→ Wait
→ next item
```

This was introduced to reduce model rate-limit failures.

### Deterministic company identity

Company identity prefers the normalized company domain. A normalized company-name fallback is used when no usable domain exists.

## Human Checkpoint

None inside the workflow.

Human review happens later when the resulting opportunities appear in the dashboard.

---

# 2. Company Qualification

## Purpose

Transforms discovered company records into actionable qualification records by checking company websites, locating careers pages, detecting public openings, and deciding whether a company should become a direct application, speculative outreach target, ecosystem contact, or monitor-only record.

## Trigger

The workflow can start through:

- manual execution;
- execution as a subworkflow from `Dashboard API - Discovery Action`.

## Inputs

Primary source:

```text
Companies
```

The workflow uses fields such as:

- `company_key`;
- `company_name`;
- `company_website`;
- `official_website_scraped`;
- `profile_fit_score`;
- `profile_fit_evidence`;
- `hiring_signal`;
- `hiring_evidence`;
- entity type;
- country-match information;
- visa-support evidence.

Existing rows from:

```text
Company_Qualification
```

are loaded for duplicate protection.

## Processing Steps

1. Load companies from `Companies`.

2. Deduplicate candidates by `company_key`.

3. Load existing qualification records.

4. Remove companies that are already present in `Company_Qualification`.

5. Prepare the website scan using:
   - `company_website`;
   - fallback `official_website_scraped`.

6. Reuse an already known careers URL when one is available.

7. Otherwise fetch the company homepage.

8. Extract homepage links.

9. Identify likely:
   - careers links;
   - contact links;
   - about/team links;
   - company LinkedIn links.

10. Build careers-page candidates.

11. If no explicit careers link exists, generate common candidate paths such as:
    ```text
    /careers
    /jobs
    /join-us
    /work-with-us
    /karriere
    /kariera
    /praca
    ```

12. Probe candidate pages and classify results as:
    - `LIKELY_CAREERS_PAGE`;
    - `POSSIBLE_CAREERS_PAGE`;
    - `NO_CAREER_SIGNAL`;
    - `NOT_FOUND`;
    - `BLOCKED`;
    - `HTTP_ERROR`.

13. Summarize the careers scan into statuses such as:
    - `CAREERS_PAGE_FOUND`;
    - `CAREERS_PAGE_POSSIBLE`;
    - `CAREERS_PAGE_NOT_FOUND`;
    - `CAREERS_PAGE_UNREACHABLE`.

14. If no usable careers page is available, build the speculative path.

15. If a careers page exists:
    - fetch it;
    - extract links and mailto addresses;
    - identify job-listing URLs;
    - filter for target technical roles;
    - extract a suitable careers contact email when present.

16. Finalize qualification and persist the result.

## Outputs

One `Company_Qualification` row per newly qualified company.

Important outputs include:

- `company_key`;
- careers URL;
- careers-page status;
- opening counts;
- relevant role titles;
- relevant vacancy URLs;
- careers contact email;
- vacancy status;
- opportunity type;
- qualification score;
- qualification reason;
- visa-support fields;
- `qualification_version`.

## External Services

- Google Sheets
- Public company websites via HTTP

This workflow does not use an LLM for careers-page qualification.

## State Changes

The workflow persists qualification state such as:

```text
qualification_status = QUALIFIED
qualification_version = 3
```

Possible `opportunity_type` values generated by the workflow include:

```text
DIRECT_APPLICATION
SPECULATIVE_OUTREACH
ECOSYSTEM_OUTREACH
MONITOR_ONLY
```

Possible vacancy outcomes include:

```text
RELEVANT_OPENING
OTHER_OPENINGS
NO_OPENINGS_FOUND
CAREERS_PAGE_NOT_FOUND
UNKNOWN
```

## Reliability Considerations

### Company-level deduplication

Existing `company_key` values and same-run duplicate keys are filtered before qualification.

### Reuse of saved careers URLs

A previously known careers URL can bypass homepage rediscovery.

### Multiple careers-page strategies

The workflow first uses discovered links and then falls back to common path probing.

### Probe classification

HTTP status, not-found text, career-related text, and application-related signals are combined before accepting a page as a careers page.

### Retry behavior

Career-page probing includes retry behavior for transient failures.

### Known hardening area

The homepage fetch uses retry and error-output handling, but the current workflow does not route that error output into a full fallback qualification branch. A company whose homepage fetch fails can therefore leave the normal qualification path prematurely. An explicit `FETCH_FAILED` persistence path is a future reliability improvement.

## Human Checkpoint

None inside the workflow.

Qualification produces evidence and state that the user reviews later in the dashboard.

---

# 3. Application Queue Builder

## Purpose

Converts qualified companies into actionable opportunity records while keeping direct applications and speculative company prospects distinct.

## Trigger

The workflow can start through:

- manual execution;
- execution as a subworkflow from `Dashboard API - Discovery Action`.

## Inputs

Reads from:

```text
Company_Qualification
```

and uses qualification records with:

```text
qualification_status = QUALIFIED
```

Two logical branches are evaluated.

### Direct applications

Require:

```text
opportunity_type = DIRECT_APPLICATION
relevant_vacancy_urls != empty
```

### Speculative prospects

Require:

```text
opportunity_type = SPECULATIVE_OUTREACH
```

## Processing Steps

1. Load qualification rows.

2. Filter direct-application candidates.

3. Split pipe-delimited vacancy URLs and role titles.

4. Normalize vacancy URLs.

5. Create one opportunity per relevant public vacancy.

6. Build deterministic direct-application keys:
   ```text
   company_key::normalized_vacancy_url
   ```

7. Filter speculative-outreach candidates.

8. Build one speculative opportunity per company.

9. Build deterministic speculative keys:
   ```text
   company_key::speculative
   ```

10. Merge direct and speculative candidates.

11. Load existing `Application_Tracker` rows.

12. Remove opportunities already stored from previous executions.

13. Remove duplicate opportunity keys generated during the same execution.

14. Save only new opportunities to `Application_Tracker`.

## Outputs

New rows in:

```text
Application_Tracker
```

A new opportunity begins with a review-oriented state.

Direct and speculative records are created with clear `opportunity_type` values rather than being mixed together.

## External Services

- Google Sheets

## State Changes

New opportunities are initialized with values such as:

```text
application_status = TO_REVIEW
contact_research_status = NOT_STARTED
outreach_approval = PENDING
outreach_status = NOT_STARTED
response_status = NO_RESPONSE
```

For speculative prospects:

```text
opportunity_type = SPECULATIVE_OUTREACH
outreach_mode = empty
```

The outreach mode remains empty until the user explicitly chooses speculative outreach.

## Reliability Considerations

### Deterministic opportunity keys

Business identity is based on normalized company/vacancy information rather than random UUIDs.

### Historical deduplication

Existing `Application_Tracker` keys are loaded once into an in-memory set.

### Same-run deduplication

A separate `seenThisRun` set prevents duplicates generated during the current execution.

### URL normalization

Direct vacancy URLs are normalized before becoming part of an opportunity key.

## Human Checkpoint

The workflow only creates `TO_REVIEW` opportunities.

The user decides what to do with them in the Streamlit dashboard.

---

# 4. Dashboard API - Discovery Action

## Purpose

Provides the dashboard with a single authenticated endpoint that launches the complete discovery pipeline.

## Trigger

Authenticated HTTP webhook:

```text
POST /webhook/dashboard-discovery
```

Webhook authentication is handled through n8n Header Auth.

## Inputs

No business payload is required.

The request itself represents the user action:

```text
Find new opportunities
```

## Processing Steps

The webhook triggers the three discovery workflows sequentially:

```text
Scraper Connection Test
→ Company Qualification
→ Application Queue Builder
```

Each subworkflow is configured to wait for its called workflow before proceeding to the next stage.

The HTTP branch returns a start acknowledgement independently of the long-running discovery path.

## Outputs

The dashboard receives an HTTP `202` acknowledgement similar to:

```json
{
  "success": true,
  "status": "STARTED",
  "message": "Opportunity discovery started. Refresh the dashboard after the workflows finish."
}
```

The actual business outputs are persisted by the three called workflows.

## External Services

Indirectly orchestrates workflows that use:

- FastAPI scraper
- Vertex AI
- Google Sheets
- public company websites

The API workflow itself primarily uses n8n subworkflow execution.

## State Changes

No tracker state is written directly by this workflow.

State changes occur inside the three called workflows.

## Reliability Considerations

### Authenticated entry point

The dashboard does not receive an unauthenticated public mutation endpoint.

### Sequential dependency order

Qualification does not run before discovery completes, and queue building does not run before qualification completes.

### Fast dashboard acknowledgement

The dashboard receives a start response instead of waiting for the full discovery chain to complete.

## Human Checkpoint

The user explicitly starts discovery from the dashboard.

No applications or outreach are sent as a consequence of this action.

---

# 5. Dashboard API - List Opportunities

## Purpose

Provides the Streamlit dashboard with a normalized read model of opportunities and computed UI flags.

## Trigger

Authenticated HTTP webhook:

```text
GET /webhook/job-dashboard/opportunities
```

## Inputs

No business payload is required.

The workflow reads current rows from:

```text
Application_Tracker
```

## Processing Steps

1. Load all tracker rows.

2. Remove test opportunities whose keys begin with:
   ```text
   test::
   ```

3. Normalize application, outreach, approval, response, and confidence states.

4. Build the dashboard response object.

5. Compute helper flags including:
   - whether an opportunity has a contact;
   - whether it has a draft;
   - whether email sending is currently eligible.

6. Determine `canSendEmail` only when:
   - the opportunity is outreach-eligible;
   - approval is `APPROVED`;
   - outreach status is `DRAFT_READY`;
   - final draft status is `READY`;
   - email confidence is `HIGH`, `MEDIUM`, or `USER_VERIFIED`;
   - a contact email exists;
   - the email has not already been sent.

7. Sort opportunities primarily by application state and then by qualification score.

8. Return opportunity data and dashboard counts.

## Outputs

A JSON response containing normalized opportunities and summary counts.

The workflow exposes the state needed by the dashboard without requiring the Streamlit code to reimplement n8n business rules.

## External Services

- Google Sheets

## State Changes

None.

This workflow is read-only.

## Reliability Considerations

### Test-data exclusion

Production dashboard responses exclude `test::` records.

### Centralized UI eligibility

The dashboard receives computed eligibility flags rather than independently deciding whether an email may be sent.

### Default normalization

Missing values receive safe defaults such as:

```text
application_status = TO_REVIEW
outreach_approval = PENDING
outreach_status = NOT_STARTED
opportunity_type = DIRECT_APPLICATION
```

for compatible legacy rows.

## Human Checkpoint

The entire purpose of this workflow is to support human review.

It exposes current state but performs no mutation.

---

# 6. Dashboard API - Opportunity Action

## Purpose

Processes opportunity-level user decisions from Streamlit and launches contact research when an accepted action requires it.

## Trigger

Authenticated HTTP webhook:

```text
POST /webhook/job-dashboard/opportunity-action
```

## Inputs

Required:

```text
action
opportunity_key
```

Supported actions are:

```text
mark_applied
skip
explore_adjacent
explore_speculative
save_manual_contact
move_to_manual_outreach
```

A manual-contact request can additionally contain:

```text
contact_name
contact_role
contact_email
contact_linkedin_url
```

## Processing Steps

1. Validate the requested action.

2. Validate `opportunity_key`.

3. For manual contacts:
   - require a contact name;
   - require at least an email or LinkedIn URL;
   - validate email format;
   - validate that a supplied LinkedIn URL is a LinkedIn URL.

4. Load the matching opportunity.

5. Reject invalid transitions such as:
   - marking a speculative prospect as applied;
   - skipping an already applied opportunity;
   - using adjacent-role outreach on a speculative prospect;
   - using speculative outreach on a direct vacancy;
   - restarting research already `IN_PROGRESS` or `COMPLETED`;
   - moving to manual outreach while contact research is still running.

6. Apply the requested transition.

### `mark_applied`

Sets:

```text
application_status = APPLIED
outreach_mode = POST_APPLICATION
applied_at = current timestamp
```

### `skip`

Sets:

```text
application_status = SKIPPED
```

### `explore_adjacent`

Sets:

```text
outreach_mode = ADJACENT_ROLE
contact_research_status = NOT_STARTED
```

### `explore_speculative`

Sets:

```text
outreach_mode = SPECULATIVE
contact_research_status = NOT_STARTED
```

### `move_to_manual_outreach`

Sets:

```text
manual_contact_status = NEEDS_CONTACT
```

while retaining automatically discovered contact information as reference.

### `save_manual_contact`

Stores the user-supplied contact and sets:

```text
contact_source = MANUAL
manual_contact_status = CONTACT_ADDED
contact_email_confidence = USER_VERIFIED
```

when an email is supplied.

It also resets previous outreach drafts and approval state so a fresh draft is generated for the new contact.

7. Persist the updated opportunity.

8. Decide whether Contact Research should launch.

9. Launch `Contact Research` for:
   - a newly marked application;
   - adjacent-role exploration;
   - speculative exploration;
   - a newly saved manual contact.

10. Return a structured API response.

## Outputs

- updated `Application_Tracker` record;
- optional Contact Research subworkflow execution;
- JSON success or rejection response to the dashboard.

## External Services

- Google Sheets
- n8n subworkflow execution

## State Changes

This workflow is one of the primary state-transition controllers for:

```text
application_status
outreach_mode
applied_at
contact_research_status
manual_contact_status
contact_source
contact fields
outreach_channel
draft fields
outreach_approval
outreach_status
```

## Reliability Considerations

### Explicit action allow-list

Unexpected dashboard actions are rejected.

### Transition guards

Invalid state transitions return a rejection rather than silently mutating data.

### Production/test separation

Test opportunities do not launch production contact research.

### Fresh manual-contact drafting

When the user replaces an automatically discovered contact with a manual contact, old drafts are cleared so messages intended for the previous person are not reused.

### Contact-research idempotency

Research is not started again when it is already `IN_PROGRESS` or `COMPLETED`.

## Human Checkpoint

This workflow exists specifically to translate explicit user decisions into state changes.

Important transitions cannot occur unless the user selects the corresponding dashboard action.

---

# 7. Contact Research

## Purpose

Finds relevant company contacts, gathers supporting evidence, verifies available email information, scores candidates, selects the strongest candidate, builds personalization context, and generates outreach drafts.

It also supports a user-provided manual contact path.

## Trigger

The public workflow supports:

- manual execution for controlled testing;
- execution as a subworkflow from `Dashboard API - Opportunity Action`.

## Inputs

The main runtime input is:

```text
opportunity_key
```

The request can also include manually supplied contact information.

The workflow then loads the corresponding row from:

```text
Application_Tracker
```

and uses company, role, outreach-mode, and application context from that record.

## Processing Steps

### Stage 1 — Request normalization and eligibility

1. Normalize the incoming request.
2. Load the requested tracker opportunity.
3. Verify that the opportunity is ready for contact research.
4. Mark:
   ```text
   contact_research_status = IN_PROGRESS
   ```

### Stage 2 — Manual or automated contact path

5. Restore the research context.
6. Check whether a manual contact was provided.

#### Manual path

7. Build a deterministic manual contact record.

8. Mark the contact as selected.

9. When a manual email is present:
   ```text
   email_confidence = USER_VERIFIED
   ```

10. Give the manual contact a dominant selection score so the workflow does not replace a user-confirmed person with an automated candidate.

#### Automated path

7. Generate contact-search queries.

8. Search the web using Brave Search.

9. Normalize search results.

10. Prepare evidence for structured extraction.

11. Use Vertex AI plus a structured output parser to extract contact candidates.

12. For candidates with an email:
    - verify the address through Hunter;
    - calculate the candidate score.

13. For candidates without an email:
    - attempt Hunter Email Finder;
    - verify a found address;
    - otherwise retain and score the candidate without email.

14. Save candidates into:
    ```text
    Contact_Candidates
    ```

15. Reload saved candidates.

16. Select the best candidate.

17. Mark the chosen candidate as selected.

18. Update the corresponding `Application_Tracker` row with the selected contact.

### Stage 3 — No-contact fallback

If no candidate can be selected:

1. prepare a no-contact result;
2. reload the opportunity;
3. verify the opportunity is eligible for manual fallback;
4. set states such as:
   ```text
   contact_research_status = NOT_FOUND
   manual_contact_status = NEEDS_CONTACT
   ```
5. allow the user to continue through Manual Outreach.

### Stage 4 — Personalization research

After a contact is selected:

1. generate contact/context search queries;
2. run additional Brave searches;
3. normalize and clean the evidence;
4. build personalization context;
5. use Vertex AI to extract structured personalization points;
6. validate:
   - allowed personalization point types;
   - evidence references;
   - confidence;
   - safe wording.

The workflow accepts only `HIGH` or `MEDIUM` confidence for normal personalization points.

### Stage 5 — Draft generation

1. attach the candidate profile;
2. reload the current application state;
3. prepare outreach context;
4. determine whether draft generation is ready;
5. allow a safe fallback when a manually verified contact exists but personalization evidence is insufficient;
6. use Vertex AI to generate:
   - email subject;
   - email draft;
   - LinkedIn connection note;
   - LinkedIn direct message;
7. parse the output;
8. validate the draft for:
   - required fields;
   - unsupported application claims;
   - adjacent-role wording;
   - overconfident fit claims;
   - attachment wording;
   - other safety/quality conditions;
9. save valid drafts to `Application_Tracker`.

### Stage 6 — Completion

Finally:

```text
contact_research_status = COMPLETED
```

is persisted for successful research/drafting completion.

## Outputs

### `Contact_Candidates`

Candidate records containing fields such as:

- contact identity;
- role;
- email;
- LinkedIn URL;
- evidence;
- role category;
- email confidence;
- relevance components;
- candidate score;
- selection status.

### `Application_Tracker`

The selected contact and generated outreach drafts are written back to the opportunity.

For an applied opportunity, the generated draft can reach:

```text
outreach_status = DRAFT_READY
```

For a non-applied preview scenario, the workflow can keep the result in a preview-oriented state rather than making it immediately sendable.

New drafts remain:

```text
outreach_approval = PENDING
```

## External Services

- Google Sheets
- Brave Search API
- Hunter Email Finder
- Hunter Email Verifier
- Vertex AI

## State Changes

The workflow can update:

```text
contact_research_status
contact_name
contact_role
contact_email
contact_email_confidence
contact_linkedin_url
contact_source
manual_contact_status
outreach_channel
email_subject
email_draft
linkedin_connection_note
linkedin_message
draft_final_status
draft_generated_at
outreach_status
outreach_approval
```

It also creates and updates `Contact_Candidates`.

## Reliability Considerations

### Structured model outputs

Contact extraction and personalization use structured parsers rather than treating free-form model output as authoritative.

### Evidence retention

Contact candidates retain evidence and sources instead of storing only a selected name.

### Email verification

Hunter verification is used where email data is available.

### Multi-stage contact scoring

Candidate selection includes role relevance, company confirmation, hiring connection, email quality, and evidence freshness.

### Retry-tolerant research APIs

Hunter verification/finder calls and context search steps use retry/continue behavior so a single failed enrichment request does not necessarily destroy the whole branch.

### No-contact fallback

Failure to find a suitable person is represented explicitly instead of inventing a contact.

### Manual override

A user can provide a contact and mark it effectively as `USER_VERIFIED`.

### Conservative personalization

Insufficient evidence is not converted into fabricated personalization.

### Draft validation

Generated drafts are checked before being persisted as ready.

## Human Checkpoint

The workflow can automatically select the highest-scoring researched contact, but the user remains in control of the communication:

- the selected contact is visible in the dashboard;
- a user can replace it with a manually verified contact;
- generated drafts remain editable;
- generated drafts are not sent by this workflow;
- approval is required later.

---

# 8. Dashboard API - Outreach Action

## Purpose

Accepts edited outreach drafts from the dashboard, enforces campaign and send-readiness rules, saves the draft, and optionally launches the approved email sender.

## Trigger

Authenticated HTTP webhook:

```text
POST /webhook/job-dashboard/outreach-action
```

## Inputs

Required:

```text
action
opportunity_key
email_subject
email_draft
```

Optional draft fields include:

```text
linkedin_connection_note
linkedin_message
```

Supported actions are:

```text
save_draft
approve_and_send
```

## Processing Steps

1. Validate the request and required draft fields.

2. Load `Application_Tracker`.

3. Find the requested opportunity.

4. Reject test opportunities.

5. Verify outreach eligibility:
   - application status is `APPLIED`; or
   - outreach mode is `ADJACENT_ROLE`; or
   - outreach mode is `SPECULATIVE`.

6. Reject already-sent campaigns.

7. Compare related tracker rows using campaign identity signals such as:
   - company domain;
   - contact email;
   - LinkedIn URL;
   - fallback company name.

8. Detect an already active canonical campaign for the same company/contact.

9. Block duplicate company-level outreach when another related opportunity already owns the campaign.

10. For `approve_and_send`, additionally require:
    - `contact_research_status = COMPLETED`;
    - contact email present;
    - confidence `HIGH`, `MEDIUM`, or `USER_VERIFIED`;
    - resume file ID present;
    - resume filename present.

11. Persist the edited draft.

12. Set:
    ```text
    draft_final_status = READY
    outreach_status = DRAFT_READY
    ```

13. For `save_draft`:
    ```text
    outreach_approval = PENDING
    ```

14. For `approve_and_send`:
    ```text
    outreach_approval = APPROVED
    ```

15. If sending was approved, launch `Approved Outreach Sender`.

16. Return the sender result or saved-draft response.

## Outputs

- updated draft fields in `Application_Tracker`;
- optional sender subworkflow result;
- structured HTTP response.

## External Services

- Google Sheets
- n8n subworkflow execution

## State Changes

Can update:

```text
email_subject
email_draft
linkedin_connection_note
linkedin_message
draft_final_status
draft_generated_at
outreach_status
outreach_approval
last_updated
```

## Reliability Considerations

### Explicit send action

Saving and sending are separate actions.

### Company-level duplicate-campaign protection

The workflow prevents multiple active outreach campaigns from targeting the same company/contact identity.

### Contact-research dependency

Sending cannot be approved until contact research is complete.

### Confidence threshold

Only:

```text
HIGH
MEDIUM
USER_VERIFIED
```

email confidence can proceed to email sending.

### Resume presence check

The workflow prevents send approval when the expected resume attachment metadata is missing.

## Human Checkpoint

This is the main pre-send human checkpoint.

The user reviews/edits the generated content and explicitly chooses either:

```text
Save draft
```

or:

```text
Approve and send
```

---

# 9. Approved Outreach Sender

## Purpose

Performs the final protected email-send operation after dashboard approval.

The workflow deliberately rechecks send eligibility rather than trusting the API action alone.

## Trigger

The workflow can start through:

- manual execution for controlled testing;
- execution as a subworkflow from `Dashboard API - Outreach Action`.

## Inputs

Primary runtime input:

```text
opportunity_key
```

The workflow then reloads the authoritative opportunity from `Application_Tracker`.

## Processing Steps

1. Normalize the sender request.

2. Load `Application_Tracker`.

3. Select the requested opportunity.

4. Reject the request if no matching row exists.

5. Download the configured resume from Google Drive.

6. Run the final email send gate.

7. Require outreach eligibility:
   ```text
   application_status = APPLIED
   OR outreach_mode = ADJACENT_ROLE
   OR outreach_mode = SPECULATIVE
   ```

8. Block duplicate campaigns.

9. Require:
   ```text
   outreach_approval = APPROVED
   outreach_status = DRAFT_READY
   draft_final_status = READY
   ```

10. Validate:
    - recipient email format;
    - email confidence;
    - subject;
    - body;
    - absence of an existing `sent_at`;
    - resume file ID;
    - resume filename;
    - downloaded resume binary;
    - PDF MIME type;
    - `.pdf` filename.

11. Send the email through Gmail with the resume attached.

12. Record Gmail identifiers.

13. Calculate a follow-up date five business days after sending.

14. Update the tracker.

## Outputs

Updated `Application_Tracker` state including:

```text
outreach_status = SENT
outreach_approval = APPROVED
sent_at
follow_up_date
response_status = NO_RESPONSE
gmail_message_id
gmail_thread_id
```

## External Services

- Google Sheets
- Google Drive
- Gmail

## State Changes

Primary post-send transition:

```text
DRAFT_READY
→ SENT
```

The workflow also initializes reply/follow-up tracking.

## Reliability Considerations

### Defense in depth

The workflow repeats eligibility checks even though the dashboard API already validated approval.

### Duplicate-send protection

A populated `sent_at` blocks resending.

### Duplicate-campaign protection

A campaign flagged as covered by another canonical campaign is blocked.

### Email-confidence gate

Only:

```text
HIGH
MEDIUM
USER_VERIFIED
```

is accepted.

### Attachment validation

The resume must exist, download successfully, be available as binary data, use PDF MIME type, and have a PDF filename.

### Authoritative tracker reload

The workflow reloads current state before sending rather than relying only on request payload data.

## Human Checkpoint

The sender itself does not ask the user again.

Its required human checkpoint is the prior:

```text
approve_and_send
```

action in `Dashboard API - Outreach Action`.

Without that approval state, the send gate blocks the email.

---

# 10. Gmail Reply Monitor

## Purpose

Passively monitors sent outreach threads for incoming replies and updates campaign response state.

## Trigger

Scheduled execution every:

```text
3 hours
```

The sanitized public workflow is intended to operate as a background monitor.

## Inputs

Reads outreach campaigns from:

```text
Application_Tracker
```

A campaign is considered for monitoring when it has:

- an appropriate sent/active outreach state;
- `response_status = NO_RESPONSE`;
- a Gmail thread ID;
- a sent timestamp;
- no existing reply-detected timestamp.

## Processing Steps

1. Load tracker rows.

2. Remove test campaigns.

3. Select campaigns that require monitoring.

4. Deduplicate monitored Gmail thread IDs.

5. Determine the earliest relevant sent timestamp.

6. Search Gmail using:
   ```text
   in:anywhere -from:me
   ```

7. Start the search one day before the earliest monitored sent timestamp to reduce timezone-boundary issues.

8. Match messages back to campaigns using the exact Gmail thread ID.

9. Require the candidate reply to have arrived after the original sent timestamp.

10. Select the newest valid incoming message in the thread.

11. Update the corresponding tracker row.

## Outputs

When a reply is detected:

```text
response_status = REPLIED
reply_detected_at
reply_message_id
reply_from
reply_subject
reply_snippet
```

When no reply is found, the workflow returns a no-reply monitor result without mutating campaign state.

## External Services

- Google Sheets
- Gmail

## State Changes

Primary transition:

```text
NO_RESPONSE
→ REPLIED
```

## Reliability Considerations

### Exact Gmail thread matching

The workflow does not rely only on subject text or sender identity.

### Timestamp validation

A message must be newer than the original outreach.

### Thread deduplication

The same Gmail thread is not monitored more than once within one run.

### Search-window buffer

The one-day lookback reduces missed messages caused by date/timezone boundaries.

### Idempotent reply detection

Campaigns with an existing `reply_detected_at` are skipped.

## Human Checkpoint

None inside the monitor.

The workflow only records reply state. The user reviews the actual reply from the dashboard/Gmail and decides how to continue.

---

# 11. Follow-up Draft Generator

## Purpose

Finds campaigns that are legitimately due for follow-up, generates a concise follow-up draft, validates it, and stores it for human approval.

It does not send the follow-up.

## Trigger

Two supported triggers:

- manual execution;
- scheduled execution every 3 hours.

## Inputs

Reads all candidate campaigns from:

```text
Application_Tracker
```

## Processing Steps

### Due-campaign selection

1. Normalize company domains, email addresses, LinkedIn URLs, and company names.

2. Compare related rows to identify one canonical campaign for a company/contact identity.

3. Compute campaign rank from states such as:
   - sent;
   - approved;
   - draft ready;
   - research completed;
   - research in progress.

4. Exclude test opportunities.

5. Require:
   ```text
   outreach_status = SENT
   response_status = NO_RESPONSE
   sent_at != empty
   gmail_thread_id != empty
   follow_up_date <= today
   ```

6. Exclude campaigns when:
   - a reply has been detected;
   - a follow-up has already been sent;
   - follow-up state is not eligible;
   - the row is not the canonical campaign.

### Draft generation

7. Send due campaigns to Vertex AI.

8. Parse structured output.

9. Remove an unnecessary subject line because Gmail follow-ups are sent as threaded replies.

10. Validate the generated draft.

The validator checks for:

- linked opportunity key;
- non-empty content;
- approximately 50–120 words;
- unresolved placeholders;
- false claims that an application was submitted;
- required configured sign-off.

11. Set:
    ```text
    follow_up_status = DRAFT_READY
    follow_up_approval = PENDING
    ```
    when valid.

12. Set:
    ```text
    follow_up_status = FAILED
    ```
    when validation fails.

13. Save valid drafts to `Application_Tracker`.

## Outputs

A stored follow-up draft with metadata such as:

```text
follow_up_draft
follow_up_generated_at
follow_up_status
follow_up_approval
```

The workflow also returns summary results such as:

```text
DRAFTS_SAVED
DRAFT_VALIDATION_FAILED
NO_DUE_CAMPAIGNS
```

## External Services

- Google Sheets
- Vertex AI

## State Changes

Typical successful transition:

```text
follow_up_status = NOT_STARTED
→ DRAFT_READY
```

with:

```text
follow_up_approval = PENDING
```

## Reliability Considerations

### Campaign-level deduplication

Only one canonical campaign per company/contact identity is selected.

### Reply awareness

Campaigns with detected replies are excluded.

### Date enforcement

The workflow does not generate a follow-up before the configured follow-up date.

### Thread requirement

A Gmail thread ID must exist, ensuring later follow-up sending can remain in the original conversation.

### Draft validation

Generated content is checked for length, unresolved placeholders, false application claims, and sign-off requirements.

### Failure state

Invalid generated text becomes `FAILED` instead of being treated as sendable.

## Human Checkpoint

Every generated follow-up remains:

```text
follow_up_approval = PENDING
```

The user must review it before it can be sent.

---

# 12. Dashboard API - Follow-up Action

## Purpose

Handles user edits and approval of follow-up drafts and sends an approved follow-up as a reply in the original Gmail thread.

## Trigger

Authenticated HTTP webhook:

```text
POST /webhook/job-dashboard/follow-up-action
```

## Inputs

Required:

```text
action
opportunity_key
follow_up_draft
```

Supported actions are:

```text
save_follow_up_draft
approve_and_send_follow_up
```

## Processing Steps

1. Validate the request.

2. Remove an accidental subject line from the submitted body.

3. Reject:
   - unsupported actions;
   - missing opportunity key;
   - empty follow-up draft;
   - excessively long draft.

4. Load `Application_Tracker`.

5. Find the requested campaign.

6. Reject test campaigns.

7. Verify:
   ```text
   outreach_status = SENT
   sent_at exists
   response_status = NO_RESPONSE
   no reply_detected_at
   no previous follow_up_sent_at
   follow_up_date exists
   ```

8. For send approval, additionally require:
   - follow-up date is due;
   - `follow_up_status = DRAFT_READY`;
   - original Gmail message ID;
   - original Gmail thread ID.

9. For a save-only action:
   ```text
   follow_up_status = DRAFT_READY
   follow_up_approval = PENDING
   ```

10. For an approved send:
    ```text
    follow_up_status = SENDING
    follow_up_approval = APPROVED
    ```

11. Reply inside the original Gmail thread.

12. Persist the sent result:
    ```text
    follow_up_status = SENT
    follow_up_approval = APPROVED
    follow_up_sent_at
    follow_up_message_id
    response_status = NO_RESPONSE
    ```

13. Return an API response.

## Outputs

- saved follow-up edits; or
- Gmail reply result plus updated follow-up state.

## External Services

- Google Sheets
- Gmail

## State Changes

Save-only:

```text
DRAFT_READY
PENDING
```

Approved send:

```text
DRAFT_READY
→ SENDING
→ SENT
```

with approval and send timestamps persisted.

## Reliability Considerations

### Separate save and send actions

Editing a follow-up does not imply authorization to send it.

### Reply-aware blocking

The workflow blocks follow-up sending once a reply has already been detected.

### Due-date enforcement

A future follow-up date blocks send approval.

### Duplicate-follow-up prevention

A populated `follow_up_sent_at` or already-sent follow-up state blocks a second follow-up.

### Threaded delivery

The workflow requires original Gmail message/thread identifiers and sends the follow-up as a reply rather than starting an unrelated email thread.

### Authenticated webhook

Header authentication protects the mutation endpoint.

## Human Checkpoint

This is the explicit follow-up approval boundary.

The user must choose:

```text
approve_and_send_follow_up
```

before Gmail is called.

---

# Cross-Workflow State Lifecycle

The workflows collectively implement a stateful lifecycle rather than a single autonomous pipeline.

A simplified opportunity path is:

```text
Company discovered
    ↓
Company qualified
    ↓
Opportunity created
    ↓
TO_REVIEW
    │
    ├── SKIPPED
    │
    ├── APPLIED
    │      ↓
    │   POST_APPLICATION
    │
    ├── ADJACENT_ROLE
    │
    └── SPECULATIVE
           ↓
    Contact Research
           ↓
      IN_PROGRESS
           ↓
     COMPLETED / NOT_FOUND
           ↓
       Draft generated
           ↓
     DRAFT_READY / PREVIEW
           ↓
       Human approval
           ↓
          SENT
           ↓
     ┌─────┴────────────────────┐
     ↓                          ↓
  REPLIED             follow_up_date becomes due
                                ↓
                         Follow-up draft
                         (DRAFT_READY)
                                ↓
                         Human approval
                                ↓
                         follow_up_status = SENT
```

Multiple state fields are intentionally used because application, outreach, research, reply, and follow-up state are separate dimensions.

---

# Cross-Workflow Reliability Patterns

Several engineering patterns repeat across the workflow set.

## 1. Deterministic business keys

The system uses normalized keys for:

- articles;
- companies;
- vacancies;
- opportunities;
- contacts;
- outreach campaigns.

This supports idempotent workflow execution.

## 2. Bulk state reads

Google Sheets data is loaded in bulk where practical and compared in memory rather than queried once per item.

## 3. Same-run deduplication

Historical duplicate prevention is supplemented with in-memory sets for duplicate records created during one execution.

## 4. Explicit state transitions

The dashboard does not directly edit arbitrary state. Mutation workflows validate actions and transitions first.

## 5. Human approval boundaries

Email and follow-up sending require explicit approval actions.

## 6. Defense in depth

The final sender repeats send-readiness checks rather than trusting only the preceding API workflow.

## 7. Evidence-aware AI usage

LLMs are used for interpretation and drafting, but deterministic code controls:

- identity;
- state;
- duplicate prevention;
- eligibility;
- confidence gates;
- sending;
- persistence.

## 8. Failure states instead of invented success

Examples include:

```text
NOT_FOUND
NEEDS_CONTACT
FAILED
BLOCKED
INSUFFICIENT
```

These states allow the dashboard or user to handle uncertainty without fabricating data.

## 9. Private authenticated control surface

Dashboard mutation endpoints use Header Auth and are designed to sit behind the private deployment boundary.

---

# Human-in-the-Loop Boundaries

The project intentionally distinguishes between automation and authorization.

## Automated

The system can automatically:

- discover articles;
- parse source content;
- score company relevance;
- inspect careers pages;
- identify vacancies;
- build opportunity records;
- research contacts;
- verify email evidence;
- select a candidate contact;
- generate drafts;
- monitor Gmail threads;
- identify due follow-ups.

## Human-controlled

The user controls:

- whether an opportunity is applied to;
- whether adjacent-role outreach should be explored;
- whether speculative outreach should be explored;
- whether a manual contact should replace automatic research;
- draft editing;
- initial outreach approval;
- follow-up editing;
- follow-up approval.

Most importantly:

```text
LLM generation != authorization to send
```

Communication leaves the system only after an explicit user approval action.

---

# Workflow Dependencies

```text
Scraper Connection Test
        ↓
Company Qualification
        ↓
Application Queue Builder
        ↓
Dashboard API - List Opportunities
        ↓
Dashboard API - Opportunity Action
        ↓
Contact Research
        ↓
Dashboard API - Outreach Action
        ↓
Approved Outreach Sender
        ↓
Gmail Reply Monitor
        ↓
Follow-up Draft Generator
        ↓
Dashboard API - Follow-up Action
```

Not every opportunity passes through every workflow.

For example:

- skipped opportunities stop before contact research;
- speculative opportunities never need to be marked applied;
- no-contact results can move to manual outreach;
- replied campaigns are excluded from follow-up generation;
- unsent drafts never enter reply monitoring.

This conditional structure is central to the platform design.
