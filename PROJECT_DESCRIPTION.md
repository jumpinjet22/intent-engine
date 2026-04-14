# Doorbell Intent Engine — Historical Project Description

> **Historical/context document:** This file describes intended use and context. It is not the canonical implementation spec.

**Last verified against:** 2026-04-14 (UTC)

**Canonical references:**
- `README.md`
- `.env.example`
- `docker-compose.yml`
- `docker-compose.min.yml`
- `docker-compose.external.yml`

## What this project is

A local-first, Docker-oriented intent handling stack for doorbell workflows. The repository currently centers on an `intent-engine` service that consumes MQTT signals and can integrate with an Ollama endpoint for LLM responses.

## What is verifiable in the current repo

- Compose-managed service definitions exist for `intent-engine` across all provided compose files.
- The full compose file also defines `ollama`, `mqtt`, and `web-ui` services.
- `.env.example` provides baseline variables for MQTT connectivity, image names, web UI port, MQTT topics, and intent/decision thresholds.
- `README.md` documents expected setup flow and runtime expectations at a high level.

## Startup patterns that match repository files

Primary (full stack):

```bash
cp .env.example .env
docker compose up -d
```

Alternatives:

```bash
docker compose -f docker-compose.min.yml up -d
docker compose -f docker-compose.external.yml up -d
```

## Non-canonical/aspirational content policy

Examples, scenarios, and outcome narratives (for example, specific business/home workflows or guaranteed automation behavior) should be interpreted as conceptual context unless they are explicitly documented as implemented in the canonical files above.
