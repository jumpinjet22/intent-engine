# KNOCK Roadmap

## Phase 0: Foundation (current)
- Add clean package boundaries alongside legacy prototype.
- Keep mock-only providers for local development and tests.
- Add policy-first orchestration path.

## Phase 1: Adapter migration
- Add adapter layers to bridge existing `intent-engine/` logic into `knock/` modules.
- Start routing selected paths through `knock.core.orchestrator`.

## Phase 2: Real integrations
- Add optional real integrations behind provider interfaces.
- Keep local-first mock defaults.
