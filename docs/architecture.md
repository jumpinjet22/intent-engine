# KNOCK Architecture

KNOCK is a local-first visitor conversation platform.

The project should not be designed as a UniFi-only doorbell script. The core should work with any input source that can provide a visitor event and any output source that can deliver a response.

## Current prototype reality

The current repo already contains a useful prototype:

- MQTT event handling
- Ollama-backed intent classification
- heuristic fallback intent classification
- basic state machine
- clarification flow
- escalation path
- mocked talkback status
- simple web UI/runtime configuration

That prototype is useful, but the next version should separate the core conversation system from hardware-specific integrations.

## Target architecture

```text
Input Provider
    ↓
KNOCK Core Orchestrator
    ↓
Policy Layer
    ↓
Conversation Engine
    ↓
Provider Layer
    ↓
Output Provider
```

## Core principle

The core should accept a generic visitor event and return a generic response decision.

Hardware-specific systems should be adapters, not baked into the brain.

## Generic visitor event

```json
{
  "event_type": "doorbell_press",
  "source": "front_door",
  "visitor_text": "Hi, I have a package for Jon.",
  "metadata": {
    "person_detected": true,
    "package_detected": true,
    "camera": "front_door"
  }
}
```

## Generic response decision

```json
{
  "reply": "Thanks. You can leave the package by the door.",
  "intent": "delivery",
  "confidence": 0.85,
  "action": "respond",
  "notify_owner": false,
  "escalate": false
}
```

## Provider categories

### Input providers

Input providers create visitor events.

Examples:

- CLI/local test provider
- REST webhook provider
- MQTT provider
- Frigate provider
- Home Assistant provider
- UniFi Protect provider
- ONVIF/Reolink/Amcrest provider

### AI providers

AI providers supply reasoning or classification.

Examples:

- Mock LLM provider
- Ollama provider
- OpenAI-compatible provider
- Vision model provider

### Audio providers

Audio providers handle speech in and speech out.

Examples:

- Mock STT provider
- Whisper provider
- Mock TTS provider
- Piper provider
- Kokoro provider
- XTTS provider

### Output providers

Output providers deliver the final response.

Examples:

- Console output
- MQTT publish
- Home Assistant notify
- UniFi talkback
- Local speaker
- Webhook output

## Policy layer

The policy layer is non-negotiable. It should run before and after AI generation.

The system should never:

- say whether anyone is home
- reveal schedules
- unlock doors
- disclose private names, routines, or personal information
- argue with visitors
- continue indefinitely when confused

The system should:

- keep replies short
- escalate emergencies
- hand off uncertain cases
- avoid making promises it cannot fulfill
- prefer boring safe responses over clever unsafe ones

## Build order

1. Document architecture and event schemas.
2. Build local text-only CLI/API harness.
3. Move safety logic into a standalone policy layer.
4. Add provider interfaces.
5. Wrap Ollama behind an LLM provider.
6. Add session management.
7. Add MQTT provider.
8. Add TTS/STT providers.
9. Add vision later.
10. Add hardware-specific talkback last.

## Not yet

Do not start with:

- full video reasoning
- real UniFi talkback
- voice cloning
- multi-GPU scheduling
- fancy dashboard work

Those are phase-two features. The first goal is a boring, testable, modular conversation core.
