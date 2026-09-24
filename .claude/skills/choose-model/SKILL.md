---
name: choose-model
description: Runs the model and settings choice for a new agent, once, and again only if asked. Writes the choice and reason into intake.md. Use when a new agent needs its LLM and settings picked, or when the client asks to change them.
---

# Choose model and settings

Run this once per new agent. Re-run only if the client asks to change it.

## Question 1

"Do you want to name the LLM and settings, or pick a priority?"

If they name them, use them and skip to Confirm settings.

## Question 2, if no name given

"What matters most: cost, token use, precision, speed, or HIPAA?"

| Priority | Direction to recommend |
|---|---|
| Cost saving | Smallest model that passes the traces. Shorter prompts. Fewer extract nodes. |
| Token efficiency | Conversation flow over one big prompt. Short node instructions. Structure over prose. |
| Precision | Stronger model. More structure. More examples on edges. |
| Speed (low delay) | Fast model. Fewer silent nodes before a spoken line. |
| HIPAA compliance | Only the setup Retell documents as HIPAA-eligible. Run `hipaa-check`. A BAA with Retell is needed. |

## Confirm settings

Each with a stated default. Ask only about ones the intake or a source
document has not already answered.

LLM, temperature, voice, language, interruption sensitivity,
responsiveness, end-call-after-silence, reminder count, max call length,
post-call analysis fields, webhook URL and events, data storage and PII
settings, boosted keywords.

## Write the choice

Append to `<client>/intake.md`:

```markdown
## Model and settings
- Priority: <cost|token|precision|speed|hipaa|named>
- LLM: <model>, reason: <one line>
- Settings: <list, each with its value and default marked>
```

## Prices and facts

Read `$K/docs/reference/model-choice.md` for the current price per
minute per model. If the date checked is more than about 90 days old,
say so and offer to refresh it from Retell's current docs before quoting
a number. Never state a price from memory.

`$K/docs/lessons/lessons-token-cost.md` shows the model surcharge is
about 5% of a real bill. Cost talk must use real bill shares, not
guesses.
