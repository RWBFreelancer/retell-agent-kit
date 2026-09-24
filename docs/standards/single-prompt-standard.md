# Retell Single-Prompt Agent — Standard

The rules for building and editing a Retell **single-prompt** agent: one prompt,
no nodes, no edges.

This document is general. It is not tied to one client.

Its companion is [retell-flow-standard.md](retell-flow-standard.md), for
conversation flows. Almost nothing transfers between them. A flow is a map of
nodes and edges written with `update-conversation-flow`; a single-prompt agent is
one block of text on a Retell LLM object written with `update-retell-llm`. If you
are editing a flow, you are in the wrong file.

**Neither example agent below is a single-prompt agent.** one example agent and a second example agent are both
conversation flows. This document exists because the choice comes up on every new
build, and because the prompt-writing rules here are the ones that apply to a
flow's node instructions too.

## How to read a claim in this document

Same convention as the flow standard.

| Marker | Means | Trust it |
|---|---|---|
| A `docs.retellai.com` URL | Retell says so | Yes |
| A `developers.openai.com` URL | OpenAI says so about GPT-4.1 | Yes |
| "Observed in the starter kit" | One working production prompt does it | It is a technique, not a rule |
| Neither | Assumption | Verify before building on it |

---

## 1. When a single prompt is the right build

The flow standard's section 1 gives the shape test: caller-led calls suit a
single prompt, agent-led calls suit a flow.

Retell publishes thresholds that override the shape test. Reach for a conversation
flow when any one of these holds:

- More than three or four conditional paths.
- Five or more tools or functions.
- Several variables tracked across the call.
- A single prompt that is already behaving inconsistently.

Source: `https://docs.retellai.com/build/prompt-engineering-guide`.

Retell's own summary of the tradeoff: a single prompt is "fastest to set up" and
suits "simple, open-ended conversations like FAQs and basic customer service",
while a conversation flow gives "more fine-grained control ... with predictable
outcomes".

The last threshold is the one that gets ignored. "Already behaving
inconsistently" is a build signal, not a prompting problem. A prompt that needs a
fifth rewrite to hold a branch wants to be a flow.

### What you give up

A single prompt cannot override any setting partway through the call. Per-node
interruption sensitivity, per-node model choice, per-node voice speed, and a
node-scoped knowledge base do not exist here — there are no nodes. Everything is
agent-level for the whole call.

If any part of the call needs different behaviour from the rest — a disclosure
the caller must not talk over, a cheap model for a simple stretch — that is a
flow, not a prompt.

---

## 2. Prompt structure

Retell prescribes sections rather than one block of prose, "for better
organization and LLM comprehension". The published set:

| Section | What goes in it |
|---|---|
| Identity | The agent's role and who it works for |
| Style Guardrails | How it speaks |
| Response Guidelines | How it formats what it says |
| Task Instructions | The steps it follows |
| Objection Handling | Pre-written answers to the predictable pushback |

Source: `https://docs.retellai.com/build/prompt-engineering-guide`.

Retell's own wording for the first three:

**Identity** — "You are a friendly AI assistant for [Company Name]. Your role is
to [specific purpose]."

**Style Guardrails** — "Keep responses under 2 sentences unless explaining
complex topics"; "Use natural language, contractions, and acknowledge what the
caller says"; "Show understanding for the caller's situation".

**Response Guidelines** — "Return dates in spoken form: Say 'January fifteenth'
not '1/15'"; "Ask one question at a time: Avoid overwhelming the caller";
"Paraphrase important information back to the caller".

Those are starting text, not final text. The section names are the part worth
keeping.

---

## 3. GPT-4.1

A single-prompt agent runs the same model as everything else here. The whole of
[retell-flow-standard.md](retell-flow-standard.md) section 3a applies and is not
repeated. Read it.

Four points bite harder in a single prompt than in a flow, because there is no
node boundary to contain them:

**Literal instruction following.** "GPT-4.1 is trained to follow instructions
more closely and more literally than its predecessors, which tended to more
liberally infer intent." In a flow, an over-broad rule only affects the node it
sits in. In a single prompt every rule is live on every turn, so an unstated
exception is unstated for the entire call.

**Conflicting instructions resolve by position.** "if there are conflicting
instructions, GPT-4.1 tends to follow the one closer to the end of the prompt."
A long single prompt accumulates contradictions that a flow would have separated
into different nodes. When behaviour is wrong, look for the second rule before
rewriting the first.

**Instructions at both ends for a long prompt.** OpenAI: "ideally place your
instructions at both the beginning and end of the provided context". This applies
to single prompts and does **not** transfer to flow node instructions, which are
short by design.

**One sentence is usually enough.** "if model behavior is different from what you
expect, a single sentence firmly and unequivocally clarifying your desired
behavior is almost always sufficient to steer the model on course." If a third
rewrite has not held it, the prompt is not the problem — see section 1.

Source: `https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide`.

### Numbered sections are safe here

The flow standard bans numbered labels in node instructions, because Retell
documents them competing with a node's transition options. **A single-prompt
agent has no transitions**, so that warning does not apply. Retell's wording ties
it to "your global prompt or node instructions" in a conversation flow.

Numbered task steps in a single prompt are fine, and the starter-kit reference
prompt uses them.

---

## 4. Tool calling

This section applies to single and multi-prompt agents only. Conversation flows
attach tools to nodes and the rules are different.

Retell's do's:

- "Always specify exact conditions for tool usage in your prompts"
- "Use trigger words: List specific words/phrases that should trigger tool calls"

Retell's don't: do not rely on tool descriptions alone. Agents "may call tools at
inappropriate times" or "fail to call tools when needed".

Source: `https://docs.retellai.com/build/prompt-engineering-guide`.

This is the same underlying issue as prompt-edge reliability in a flow, and it
has the same lever: `tool_call_strict_mode`, which Retell support describes as
ensuring "stricter adherence to the tool calling schema"
(`https://community.retellai.com/t/anyone-else-having-node-transitions-not-working-on-gpt-4-1/877`).

---

## 5. Techniques from the reference prompt

`PROMPT-REFERENCE-EXAMPLE.md` in the Voice AI starter kit is a sanitised copy of
a working production single-prompt agent. It lives at
`C:\GoogleDrive\Freelance Clients\Assets\Retell Conversational Flow\Voice-ai-starter-kit\`.

**Do not copy from its sibling `PROMPT-WRITING-RULES.md`.** That file contains a
plain-text Retell API key. Never open it into a paste buffer, never quote it,
never copy any part of it into this repository.

The reference prompt's own sections are: Role, Personality, Primary Objective,
Available Tool Calls, Rules, Speech Normalization Rules, Conversation Flow. Its
techniques, described rather than copied:

**Personality by negation.** It says what the agent must not sound like as often
as what it should, in the same breath — not verbose, no volunteering
information, not fluffy. Negation is more specific than a positive adjective, and
GPT-4.1 takes it literally.

**Spelling confirmation on the fields that matter.** Read the value back and
spell the ambiguous part, letter by letter, rather than asking the caller to
repeat it.

**One final confirmation, not one per field.** Confirm each critical value as it
arrives, then confirm the whole set once before acting. Confirming twice is the
most common way a voice agent becomes tedious.

**Silent pre-fetching.** Run the lookup while saying the sentence that covers the
latency, and never tell the caller a lookup is happening.

**Explicit speech normalization.** Prices, square footage, and street-type
abbreviations spelled as spoken words. Retell also offers a
`speech_normalization` handbook toggle; use one or the other, never both, for the
reason in the flow standard's section 16.

**A `NO_RESPONSE_NEEDED` handler.** When the caller says "hold on", reply exactly
`NO_RESPONSE_NEEDED`. It is a hard-coded Retell stop sequence: generation halts
and the agent says nothing. Source: `https://docs.retellai.com/build/no-response`.

One caution about the reference prompt as a model. Its personality section is
long and heavily capitalised, and per section 3a a long prompt with emphatic
rules is exactly where contradictions hide. It is a good source of techniques and
a poor source of house style.

---

## 6. Settings

A single-prompt agent has the same agent-level settings as a flow agent — voice,
speech, silence, DTMF, guardrails, post-call analysis. The flow standard's
section 15 covers them and is not repeated.

Retell's documented defaults, from
`https://docs.retellai.com/api-references/create-agent`:

| Field | Default |
|---|---|
| `interruption_sensitivity` | 1 |
| `responsiveness` | 1 |
| `reminder_trigger_ms` | 10000 |
| `reminder_max_count` | 1 |
| `end_call_after_silence_ms` | 600000 |
| `max_call_duration_ms` | 3600000 |
| `ring_duration_ms` | 30000 |
| `stt_mode` | fast |
| `denoising_mode` | noise-cancellation |

Set them deliberately. Ten minutes of silence before hanging up is almost never
what an inbound line wants.

---

## 7. Cost

Retell's token surcharge applies to single-prompt agents exactly as it does to
flows, and it bites harder. A flow in rigid mode sends one node's instruction per
turn; a single prompt sends the whole thing every turn.

The rule: above 4,000 prompt tokens, `Scaling Factor = Prompt LLM Tokens / 4,000`
and `Billed Duration = Original Duration × Scaling Factor`. The six inputs
counted are the global prompt, tool descriptions, the node or state prompt, the
transcript, tool call history and results, and retrieved knowledge base content.

Source: `https://docs.retellai.com/accounts/billing-exceptions`. See
[../lessons-token-cost.md](../lessons-token-cost.md) for what a trim is worth and
for how to measure with `llm_token_usage`.

Below 4,000 tokens the scaling factor floors at 1.0 and a cut is worth nothing.
Above it, every word is charged on every turn of the call.

---

## 8. Testing

The flow standard's section 22 applies unchanged, including what text testing
cannot prove: voice, interruption, speech-to-text, background noise, a caller
going silent, and whether the agent speaks first.

One difference. A flow's routing can be checked structurally with `flowlint.py`
before anyone speaks to it. A single-prompt agent has no structure to lint —
every behaviour is probabilistic, and the only evidence is repetitions on a real
or simulated call. Nine of ten is a defect, not a pass.

This is the strongest practical argument for a flow whenever the choice is close.
