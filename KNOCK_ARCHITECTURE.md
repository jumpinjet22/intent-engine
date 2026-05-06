# KNOCK AI Doorbell Conversation System — High-Level Architecture

## Goal

Define a modular, testable architecture for the KNOCK conversation system that:
- separates policy/rules from LLM generation,
- makes message and event flow explicit,
- documents conversation lifecycle and state transitions,
- and clarifies external integration points (MQTT, STT, TTS, Frigate, UniFi Protect).

---

## 1) Subsystem Boundaries

The system should be split into independently testable subsystems with narrow interfaces.

### A. Ingress + Event Normalization
**Responsibility**
- Consume raw external events and normalize to internal event schema.

**Inputs**
- MQTT topics:
  - `frigate/events`
  - `doorbell/doorbell_press`
  - `doorbell/human_active`
  - `doorbell/dialogue/answer`

**Outputs**
- Internal `NormalizedEvent` objects published to the orchestration bus.

### B. Session + Conversation Orchestrator
**Responsibility**
- Own conversation/session state machine.
- Start, advance, and terminate sessions.
- Invoke policy and downstream actions.

**Inputs**
- Normalized events.
- Timeouts and system timers.

**Outputs**
- `DecisionRequest` to Policy Engine.
- Action requests to TTS/STT/LLM/notification modules.
- Session state updates.

### C. Policy Engine (Rule Layer)
**Responsibility**
- Deterministic decision logic, guardrails, escalation policy, confidence gating, and business rules.
- Decide *whether* and *how* to respond.

**Inputs**
- `DecisionRequest` (session context, person/package info, safety state, confidence, time of day, etc.).

**Outputs**
- `PolicyDecision`:
  - allow/deny response,
  - response mode (auto, ask follow-up, escalate),
  - prompt strategy/profile,
  - hard constraints (no claims, no sensitive disclosure, etc.).

### D. LLM Interaction Layer
**Responsibility**
- Handle prompt construction and response generation only after policy approval.
- No business-rule decisions.

**Inputs**
- `PolicyDecision` + scoped context bundle.

**Outputs**
- Candidate textual response + optional structured metadata (intent confidence, cited rationale tags).

### E. Speech Pipeline
**Responsibility**
- STT ingestion of visitor audio and TTS synthesis of approved responses.

**Inputs**
- Audio stream/chunks and text-to-speak requests.

**Outputs**
- Transcript events and playable audio artifacts.

### F. Device/Platform Integrations
**Responsibility**
- Adapters to external systems (Frigate, UniFi Protect, MQTT broker, optional web UI).
- Keep protocol-specific code out of policy/orchestration core.

---

## 2) Separation: Policy Layer vs LLM Layer

### Policy Layer MUST own
- Safety checks and escalation rules.
- Confidence thresholds and abstain/fallback behavior.
- Conversation eligibility (e.g., no person detected, stale session, repeated spam ring).
- Allowed response templates and tone constraints.

### LLM Layer MUST own
- Language generation and paraphrasing.
- Filling response content under policy constraints.

### Hard rule
LLM outputs are **proposals**, not final actions, until validated by policy and orchestrator.

---

## 3) Message/Event Flow

## 3.1 Core flow (doorbell press to response)
1. **Doorbell press** event arrives via MQTT.
2. Ingress normalizes event and forwards to orchestrator.
3. Orchestrator opens/resumes a session and requests policy decision.
4. Policy decision selects response mode:
   - immediate canned response,
   - LLM response generation,
   - ask visitor follow-up (STT loop),
   - escalate (notify user / handoff).
5. If LLM mode is allowed, LLM layer generates candidate text.
6. Orchestrator applies post-generation checks and issues TTS request.
7. TTS output status is published and session state advances.

## 3.2 Visitor speech flow
1. Audio/answer input is captured and passed to STT.
2. STT transcript event is normalized.
3. Orchestrator updates session context and re-runs policy.
4. System responds via TTS or escalates/ends based on policy.

## 3.3 Error flow
1. Subsystem failure emits typed error event.
2. Orchestrator maps error class to fallback:
   - retry,
   - canned apology,
   - silent fail + log/telemetry,
   - escalate.

---

## 4) Conversation Lifecycle

Suggested session states:

1. `IDLE` — no active conversation.
2. `TRIGGERED` — doorbell or human event received.
3. `CONTEXT_READY` — policy has minimum data (person/package/time/context).
4. `RESPONDING` — generating or speaking response.
5. `LISTENING` — awaiting visitor reply (optional loop).
6. `ESCALATED` — human handoff requested.
7. `COMPLETED` — successful terminal state.
8. `ABORTED` — timeout/error terminal state.

### Lifecycle constraints
- Every session has TTL and max-turn limit.
- Duplicate rings within debounce window map to same session.
- Any escalation or terminal error forces single terminal state transition.

---

## 5) Integration Points

## MQTT
- Primary event bus and command/status channel.
- Use versioned topic schema and JSON payload contracts.
- Include message IDs and timestamps for idempotency and replay safety.

## STT
- Adapter accepts audio payload/stream and returns transcript + confidence.
- Confidence should be policy-gated before response generation.

## TTS
- Adapter accepts approved text + voice profile + session ID.
- Emits synthesis status events for orchestrator state progression.

## Frigate
- Supplies detections (person/package/event metadata).
- Normalization layer converts source events into internal detection schema.

## UniFi Protect
- Supplies doorbell camera/press metadata and device context.
- Integration adapter reconciles identifiers with internal session IDs.

---

## 6) Modularity and Testability Requirements

- Each subsystem exposes a small interface and can be unit tested with mocks.
- Contract tests validate event schema between subsystem boundaries.
- Orchestrator state machine has deterministic tests for:
  - happy path,
  - timeout path,
  - retry path,
  - escalation path,
  - duplicate-event idempotency.
- Policy tests are pure-data in / decision out, without network calls.
- Integration adapters are tested with fixture payloads from MQTT/Frigate/Protect.

---

## 7) Suggested Near-Term Implementation Tasks

1. Define canonical internal event schemas (`NormalizedEvent`, `PolicyDecision`, `SessionStateEvent`).
2. Extract policy rules into isolated module (no LLM imports).
3. Route all LLM calls through one gateway module.
4. Add explicit session state enum + transition table tests.
5. Add integration-contract fixtures for MQTT, Frigate, and UniFi Protect payloads.

