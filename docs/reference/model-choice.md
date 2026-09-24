# Model and settings choice

Read this before `choose-model` runs, and refresh the price table below
before quoting a number to a client.

## Priority to direction

| Priority | Direction |
|---|---|
| Cost saving | Smallest model that passes the traces. Shorter prompts. Fewer extract nodes. |
| Token efficiency | Conversation flow over one big prompt. Short node instructions. Structure over prose. |
| Precision | Stronger model. More structure. More examples on edges. |
| Speed (low delay) | Fast model. Fewer silent nodes before a spoken line. |
| HIPAA compliance | Only the setup Retell documents as HIPAA-eligible. Run `hipaa-check`. A BAA with Retell is needed. |

## Price per minute per model

**Do not fill this from memory.** Pull it from Retell's current pricing
page (docs.retellai.com or retellai.com/pricing) at build time, and
record the date checked.

| Model | Price / min | Date checked |
|---|---|---|
| _fill from a live check_ | | |

## What the model surcharge actually is

The model is one part of a real bill, alongside telephony, STT and TTS.
Cost talk should use the real share the model contributes to a bill, not
a guessed one. See `docs/lessons/lessons-token-cost.md` for a worked
example: on one real account the model surcharge was about 5% of the
total bill, far smaller than intuition suggests. Measure it on the
client's own account before recommending a model swap purely for cost.

## Settings, each with a default to confirm or change

LLM, temperature, voice, language, interruption sensitivity,
responsiveness, end-call-after-silence, reminder count, max call length,
post-call analysis fields, webhook URL and events, data storage and PII
settings, boosted keywords.

Retell's own defaults are the starting point for any setting the client
has no opinion on. State the default when you use it; do not present a
default as a considered choice.
