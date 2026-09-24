# Retell platform reference

Read this before building or debugging an agent. When a node does not behave as
its instruction says, assume the platform has a documented reason before
assuming the prompt is wrong. Search for the symptom in Retell's own words, and
quote what you find in the transform docstring.

## Where to look

| Source | Good for |
|---|---|
| `docs.retellai.com` | Node reference, API schema, per-node fields that appear in no export |
| `community.retellai.com` | Retell staff answering the exact failure. The most valuable, most skipped |
| Reddit, YouTube walkthroughs | How people really use a feature, and failure modes the docs skip |
| Other web write-ups | Changelogs, latency guides, third-party notes |

Why this is not optional:

- 2026-08-26: a community thread named "losing the race with an in-progress caller turn" as a defect class this repo had chased as a prompt problem for two days.
- 2026-08-26: the API reference showed `interruption_sensitivity` is also a **per-node** field. No export shows it.
- 2026-08-29: the debug guide says numbered labels fire transitions whose condition never matched. This repo had been mandating numbered labels.

## Pages already read

Verified 2026-08-29. Re-check any page a change depends on. Retell edits them.

| Page | Settles |
|---|---|
| `/build/conversation-flow/debug-guide` | Numbered labels firing transitions. Retell's fix ladder for a node ignoring its instruction |
| `/build/conversation-flow/transition-condition` | Edge order: always, then equations top to bottom, then all prompt conditions together, then else, then stay |
| `/build/conversation-flow/node` | The node type list |
| `/build/conversation-flow/conversation-node` | `prompt` vs `static_text`. The per-node override list with ranges |
| `/build/conversation-flow/global-node` | Globals evaluated only after a user turn. Cool-down default of 3 steps |
| `/build/conversation-flow/flex-mode` | What is sent per turn in rigid vs flex. The 20-node degradation line |
| `/api-references/create-conversation-flow` | Every node and edge field name |
| `/api-references/create-agent` | Every agent setting and its default |
| `/accounts/billing-exceptions` | The 4,000-token surcharge and its inputs |
| `/features/post-call-analysis-overview` | Analysis reads the transcript and runs after `call_ended` |
| `/build/prompt-engineering-guide` | Prompt sections. When a flow beats a single prompt |
| `/build/llm-options` | Temperature ranges. Fast tier |
| `/build/no-response` | `NO_RESPONSE_NEEDED`, a hard-coded stop sequence that keeps the agent silent |

## Node instruction format

Plain text with `# HEADER` lines. No Markdown bold. No `*` bullets. Use dashes.

**Never start a line with a number or a numbered label.** Retell, debug guide:
"Items like 'PRIORITY 1' or 'Step 2' in your global prompt or node instructions
can be confused with transition options and trigger a transition whose condition
was never met. Use letters ('PRIORITY A') or descriptive names instead."
Ordinals inside running prose are fine. This applies to conversation-flow node
instructions and the global prompt, not to single-prompt agents.

Instructions written under the old numbered rule were audited in
an audit done once when this rule was adopted, across every node in a real flow.

## The model

Both agents run `gpt-4.1` for every real caller. Its behaviour is documented at
<https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide>, and the
parts that apply here are in section 3a of `docs/retell-flow-standard/retell-flow-standard.md`.
Read 3a before rewriting any node instruction: literal instruction following,
transitions as tool calls, sample phrases repeated verbatim, and the agent
sometimes speaking its own prompt aloud are all model behaviour.

## Test model vs production model

Rey, 2026-09-03: "use always gpt 4.1 mini for chat tests. however, prompts and
the contents of the voice ai should be in 4.1 only."
Rey, 2026-09-17: "use gpt 4.1 mini or smaller models, he did not approve for
those tests." the client had not approved the cost of `gpt-4.1` test runs.

| Where | Model |
|---|---|
| `tracerun.py`, `askcheck.py`, `retell_chat.py` sandboxes | `gpt-4.1-mini` (default) or `gpt-4.1-nano`, forced in memory by `retell_chat.Sandbox`; anything else is refused |
| `simtest.py` (Retell Simulation Testing) | Blocked: it runs the flow's own `gpt-4.1` |
| Both agents, every real caller | `gpt-4.1` |

A green run on mini proves wiring and node text. It does **not** prove `gpt-4.1`
takes the same edge. Measured 2026-09-08: T-W and T-Y both failed on mini and
both passed on 4.1, on the same export, and real calls agreed with 4.1. See
`docs/lessons-sandbox-route-divergence.md`.

So a mini result on a prompt-judged transition, or on a say-once count guarded
by prose, is weak evidence. Count real calls first, which is free, and tell Rey
when the sandbox cannot settle a question. Do not re-run on `gpt-4.1`. The
2026-09-08 advice to do so is withdrawn.

## Limits of text testing

- It cannot test voice, interruption, or speech-to-text, and it cannot express silence. An empty turn is still a turn. Walk silence on paper and confirm on a real call.
- No Retell feature copies a dynamic variable verbatim into a post-call analysis field. A description saying "copy `{{missing_fields}}`" is an instruction, not a guarantee. The recap reading the variable directly is the reliable path.

## Agent settings that shape a call

These live on the agent, not the flow. Defaults from `/api-references/create-agent`.

| Setting | Default | Effect |
|---|---|---|
| `responsiveness` | 1 | Lower waits longer before speaking. Governs the turn-detection wait, the largest slice of latency |
| `interruption_sensitivity` | 1 | Lower is harder to interrupt, by callers and noise alike |
| `enable_dynamic_responsiveness` | false | Speeds up when the caller is clearly done, waits when they pause mid-thought |
| `denoising_mode` | | The setting that can tell background noise from a person |
| `reminder_trigger_ms`, `reminder_max_count` | 10000, 1 | Nudges a silent caller |
| `end_call_after_silence_ms` | 600000 | Hangs up on a silent caller |

Measured latency breakdown: `docs/2026-09-11_latency-breakdown.md`.
