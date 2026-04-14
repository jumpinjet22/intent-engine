# Doorbell Intent Engine — Historical Project Summary

> **Historical/context document:** This file is a high-level summary for project background and may include aspirational architecture notes. For implementation truth, use the canonical docs linked below.

**Last verified against:** 2026-04-14 (UTC)

**Canonical references:**
- `README.md`
- `.env.example`
- `docker-compose.yml`
- `docker-compose.min.yml`
- `docker-compose.external.yml`

## Scope

This repository packages a Docker-based doorbell intent pipeline centered on MQTT events, an `intent-engine` service, and optional supporting services (`ollama`, `mqtt`, `web-ui`) depending on which compose profile you run.

## Repository-aligned service layout

### Full stack (`docker-compose.yml`)
- `ollama`
- `intent-engine`
- `mqtt`
- `web-ui` (optional dashboard service included in this compose file)

### Minimal stack (`docker-compose.min.yml`)
- `intent-engine`
- `web-ui` (optional debug dashboard in this file)

### External dependency mode (`docker-compose.external.yml`)
- `intent-engine`

## Startup commands (current repo)

```bash
cp .env.example .env
# update values as needed

docker compose up -d
```

Alternative compose files:

```bash
docker compose -f docker-compose.min.yml up -d
docker compose -f docker-compose.external.yml up -d
```

## Runtime configuration source of truth

Environment defaults and tunables (MQTT topics, LLM toggles, confidence thresholds, talkback mock flag, image tags/ports) are defined in:
- `.env.example`
- `environment:` sections inside compose files

## Notes on prior claims

Earlier versions of this summary included specific latency/VRAM/performance numbers and detailed hardware assumptions. Those values are environment-dependent and are **not treated as verified defaults** in this normalized document.
