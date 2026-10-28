# Deployment

## Overview

The original version of this project was deployed on a Google Cloud VM using Docker containers.

The deployment separated the main components into independent services:

```text
Google Cloud VM
│
├── n8n
├── Streamlit dashboard
├── FastAPI scraper
└── Tailscale
```

The goal of this architecture was to keep orchestration, scraping, and the user interface isolated while allowing them to communicate over a private network.

---

# Services

## n8n

n8n is the main orchestration service.

It is responsible for:

- workflow execution,
- Google Sheets integration,
- Vertex AI calls,
- Brave Search and Hunter integrations,
- Gmail sending,
- Gmail reply monitoring,
- dashboard webhook endpoints.

The original container exposed n8n internally on:

```text
5678
```

Administrative access was not intended to remain publicly exposed.

---

## Streamlit Dashboard

The dashboard runs as a separate container.

Source:

```text
dashboard/
```

Default application port:

```text
8501
```

The dashboard communicates with n8n through authenticated webhook endpoints.

Example environment variables:

```env
N8N_API_URL=http://n8n:5678/webhook/job-dashboard/opportunities
N8N_ACTION_URL=http://n8n:5678/webhook/job-dashboard/opportunity-action
N8N_OUTREACH_URL=http://n8n:5678/webhook/job-dashboard/outreach-action
N8N_FOLLOWUP_URL=http://n8n:5678/webhook/job-dashboard/follow-up-action
N8N_DISCOVERY_URL=http://n8n:5678/webhook/dashboard-discovery

DASHBOARD_API_KEY=replace_with_your_own_secret
```

The real production API key must never be committed.

---

## FastAPI Scraper

The scraper runs independently from n8n.

Source:

```text
scraper/
```

Default port:

```text
8000
```

Main endpoints:

```text
GET /health
GET /discover-test
GET /article-details
```

The discovery workflow communicates with the scraper over the private Docker network.

The original workflow used:

```text
http://startup-scraper:8000
```

where:

```text
startup-scraper
```

was the container/service hostname.

---

# Docker Networking

The original deployment used Docker networking so internal services could communicate without relying on public internet exposure.

Conceptually:

```text
              Private Docker Network
┌─────────────────────────────────────────┐
│                                         │
│   Streamlit ───────────────► n8n        │
│                                │        │
│                                ▼        │
│                         FastAPI Scraper │
│                                         │
└─────────────────────────────────────────┘
```

External integrations such as Google APIs, Vertex AI, Brave Search, and Hunter were accessed from n8n.

---

# Private Access with Tailscale

Tailscale was used as the private access layer for administrative interfaces.

This allowed the dashboard and n8n UI to be accessed from trusted devices without intentionally exposing management interfaces directly to the public internet.

Conceptually:

```text
Trusted Device
      │
      ▼
 Tailscale
      │
      ▼
Google Cloud VM
      │
      ├── Streamlit
      └── n8n
```

This was preferred over leaving administrative ports publicly accessible.

---

# Google Cloud VM

The project originally ran on a Google Cloud virtual machine.

The VM hosted:

- Docker,
- n8n,
- the Streamlit dashboard,
- the FastAPI scraper,
- Tailscale.

The public repository intentionally excludes:

- the original VM IP address,
- GCP project identifiers,
- Tailscale hostnames,
- machine-specific configuration,
- runtime container IDs.

These values are environment-specific and not required to understand the architecture.

---

# Persistent State

n8n used persistent storage for its runtime state.

A typical n8n runtime directory can contain:

```text
database.sqlite
database.sqlite-wal
database.sqlite-shm
config
storage/
nodes/
n8nEventLog*.log
```

This directory is private and is not part of the public repository.

It may contain:

- workflow execution history,
- encrypted credential data,
- user/account metadata,
- runtime logs,
- instance configuration.

For backup purposes, it should be stored securely and separately from source control.

---

# Environment Configuration

The public repository provides:

```text
.env.example
```

for the dashboard configuration.

A real deployment should create:

```text
.env
```

with production values.

The `.env` file is excluded by `.gitignore`.

Example:

```env
N8N_API_URL=http://n8n:5678/webhook/job-dashboard/opportunities
N8N_ACTION_URL=http://n8n:5678/webhook/job-dashboard/opportunity-action
N8N_OUTREACH_URL=http://n8n:5678/webhook/job-dashboard/outreach-action
N8N_FOLLOWUP_URL=http://n8n:5678/webhook/job-dashboard/follow-up-action
N8N_DISCOVERY_URL=http://n8n:5678/webhook/dashboard-discovery

DASHBOARD_API_KEY=your_private_secret
```

---

# Example Dashboard Container

A simplified deployment command could look like:

```bash
docker run -d \
  --name job-outreach-dashboard \
  --network <your-network> \
  -p 127.0.0.1:8501:8501 \
  --env-file .env \
  <your-dashboard-image>
```

Binding to:

```text
127.0.0.1
```

keeps the service from being directly exposed on every public network interface.

The exact networking strategy depends on your infrastructure.

---

# Example Scraper Container

A simplified scraper deployment could look like:

```bash
docker run -d \
  --name startup-scraper \
  --network <your-network> \
  -p 127.0.0.1:8000:8000 \
  <your-scraper-image>
```

n8n can then reach it through:

```text
http://startup-scraper:8000
```

when both containers share the same Docker network.

---

# Deployment Security

The original deployment followed several important security principles.

## Keep Secrets Outside Images

Secrets should be provided through:

- environment variables,
- n8n credentials,
- a managed secret store.

They should not be embedded in:

- Dockerfiles,
- source code,
- Git history,
- workflow JSON exports.

---

## Do Not Publish Docker Inspect Output

Docker inspection files can contain:

- environment variables,
- secrets,
- network configuration,
- mounted paths,
- internal container metadata.

For this reason, raw production files such as:

```text
*.inspect.json
docker-ps.txt
docker-images.txt
*-image-history.txt
```

are intentionally excluded from the public repository.

---

## Keep Administrative Interfaces Private

Where possible:

```text
n8n UI
Streamlit dashboard
```

should remain behind:

- Tailscale,
- VPN,
- reverse-proxy authentication,
- an identity-aware proxy,
- or another private access layer.

---

# Deployment Limitations

The current repository does not include a production-ready Docker Compose configuration.

This is intentional.

The original production configuration contained machine-specific and sensitive deployment information.

A future public deployment template could introduce:

```text
docker-compose.yml
```

containing only generalized service definitions and environment placeholders.

---

# Recommended Production Improvements

For a more production-oriented deployment, recommended improvements include:

## Docker Compose

Use a version-controlled Compose configuration for:

- n8n,
- dashboard,
- scraper,
- database.

## PostgreSQL

Replace the n8n SQLite database and potentially the Google Sheets state store with PostgreSQL where appropriate.

## Reverse Proxy

Use a reverse proxy such as:

```text
Nginx
Caddy
Traefik
```

for controlled HTTPS routing.

## Managed Secrets

Use:

```text
Google Cloud Secret Manager
```

or a similar managed secret store.

## Centralized Logging

Centralize logs and redact:

- authentication headers,
- API keys,
- email contents,
- personal contact data.

## Health Monitoring

Add health checks for:

```text
n8n
Streamlit
FastAPI scraper
```

and alert when services become unavailable.

---

# Local vs Original Deployment

The public repository can be run locally without reproducing the original Google Cloud environment.

For local development:

```text
Streamlit
    │
    ▼
local n8n
    │
    ▼
local FastAPI scraper
```

The important requirement is that the configured URLs are reachable between the services.

See:

```text
docs/setup.md
```

for installation and configuration instructions.

---

# Summary

The original deployment architecture can be summarized as:

```text
Trusted device
      │
      ▼
   Tailscale
      │
      ▼
Google Cloud VM
      │
      └── Docker network
            │
            ├── n8n
            │     ├── Google Sheets
            │     ├── Vertex AI
            │     ├── Brave Search
            │     ├── Hunter
            │     └── Gmail
            │
            ├── Streamlit dashboard
            │
            └── FastAPI scraper
```

The public repository preserves the software architecture while intentionally removing the private infrastructure details of the original deployment.
