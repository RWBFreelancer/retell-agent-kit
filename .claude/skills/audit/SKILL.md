---
name: audit
description: Grade a Retell voice agent against the standard and produce a findings report, working fully offline with no API key. Reads a prompt document, a retell.json, an LLM export, a conversation flow, or a dashboard agent export, and reports what is wrong, why it matters, and what to change. Use when someone sends a prompt or an export and asks for a review, an audit, a health check, a second opinion, or what is wrong with this agent, and when there is no API key available.
---

# Audit a Retell agent

**This is the skill that works when nothing else can.** No API key, no
account, no live agent. Just the file the client sent.

Run `setup` first if the mode is not set.
`K` below means the retell-agent-kit repo root (found via `.kit-path` in retell-clients).

## Step 1: work out what you were given

```bash
python -c "
import json,sys
o=json.load(open(sys.argv[1],encoding='utf-8'))
print(type(o).__name__, sorted(o)[:15] if isinstance(o,dict) else f'list of {len(o)}')
" thefile.json
```

| What you see | It is | Audit with |
|---|---|---|
| `general_prompt`, `llm_id` | A single-prompt LLM export | `promptlint.py` |
| `general_prompt` plus `states` | A multi-prompt agent | `promptlint.py` |
| `nodes`, `start_node_id` | A conversation flow | `flowkit.py lint` |
| `conversationFlow` (camelCase) | A dashboard agent export | `flowkit.py lint`, it un-nests |
| `response_engine`, `voice_id` | A full agent object | Both, plus read the settings |
| A `.md` or `.txt` | A raw prompt | `promptlint.py` |
| A bare JSON list | A fragment, such as `post_call_analysis_data` | Not an agent. Ask for the real export. |

## Step 2: run the linter. Offline.

```bash
python "$K/kit/promptlint.py" thefile.json
python "$K/kit/promptlint.py" thefile.json --json     # machine readable
python "$K/kit/flowkit.py" lint thefile.json
python "$K/kit/flowkit.py" lint thefile.json --line "Is there anything else?"
```

Neither touches the network. Prove it by clearing the key first:

```bash
RETELL_API_KEY= python "$K/kit/promptlint.py" thefile.json
```

## Step 3: read the things a linter cannot grade

A regex cannot judge these. You must. The full list is in
`K/docs/reference/amplify-voice-prompt-engineer.md`.

**Contradictions.** The single highest-value finding. Look for:
- A rule, and an example showing the opposite. The example wins.
- Two rules that cannot both hold.
- A stage order that disagrees with the instructions above it.

**Implicit instructions.** GPT-4.1 follows instructions **literally**.
Anything implied is not followed. "Be helpful" is not an instruction.
"If the caller has not given a number by stage 4, ask for it" is.

**Tool descriptions.** Does each name say what it does? Is there a usage
example? What happens when there is not enough information to call it?

**Missing edge cases.** Background noise. A bad line. The wrong person.
The caller going silent. The caller talking over the agent. Business
hours and blackout dates.

**Scope.** Is it clear what the agent must never do? Price, promise,
diagnosis, and anything outside the objective.

## Step 4: write the report

One table. Most severe first. Every row needs all four columns.

| # | Finding | Why it matters | The change |
|---|---|---|---|
| 1 | `begin_message` is the two-character string `""` | The agent speaks quote marks or nothing on pickup. The API reports the field as set, so no "is it empty" check catches it. | Clear the field, or put the real opening line in. |

Rules for the report:

- **Name the specific change.** Never "improve the wording". Give the
  exact replacement text.
- **Cite the location.** Line number, node id and name, or section
  heading.
- **Separate fact from judgement.** A linter FAIL is a fact. "This reads
  cold" is judgement. Label which is which.
- **Do not invent a requirement.** If something is undefined, that is a
  gap. Report it as a gap and ask. Do not fill it.
- **Say what you could not check.** Anything needing a live call, and
  anything needing an API key you do not have.

## Step 5: say what the audit cannot prove

Always close with this. It is the honest part.

- A clean lint means well formed, **not** working.
- A paper audit cannot prove behaviour. Only a call can.
- It cannot see agent-level settings: voice, interruption sensitivity,
  boosted keywords, and above all `webhook_url`. A perfect agent that
  forwards nothing looks perfect on paper.
- It cannot see whether the client is receiving leads. That needs
  `delivery-check` and an API key.

## Verified commands

Example, with the API key deliberately cleared.

```bash
K=$(cat .kit-path)
RETELL_API_KEY= python "$K/kit/promptlint.py" llm.json
RETELL_API_KEY= python "$K/kit/flowkit.py" lint agents/agent-a/exports/v51.json
RETELL_API_KEY= python "$K/kit/flowkit.py" lint flow.json --line "anything else"
```

Real audit output from a live production single-prompt agent, offline:

```
  FAIL  greeting               begin_message is '""', which is quote marks, not text
  FAIL  required/one-question  no 'one question at a time' rule
  WARN  amplify/em-dash        51 em dash character(s) in the prompt
  WARN  amplify/fillers        no filler-word guidance
  WARN  amplify/tool-bridge    1 tool(s) but no verbal bridge phrase
  WARN  size                   about 9219 tokens, over BOTH lines (2000, 4000)
  WARN  turn-taking            two or more questions in one line (line 123)

  2 fail, 11 warn, 14 ok
```

And from a live production 21-node conversation flow, offline:

```
  WARN  no-fallback    node 'node_closing_normal' has 2 conditional edge(s)
                       and no else_edge or always_edge
  ok    dead-end       no node is stuck
  ok    global-nodes   3 global node(s), reached by condition, not by an edge
  ok    size           21 nodes, 51 transitions

  0 fail, 13 warn, 5 ok
```

## Gotchas

- **The linter grades against whichever structure fits better.** Retell's
  five sections, or the Amplify Voice eight. Read the `structure` line
  saying which it chose before arguing about a missing section.

- **Speech false positives are suppressed on negation lines only.** A
  `$3` on a line saying "not $3" is ignored. A `$3` inside an example
  dialogue is reported, and correctly so.

- **A big prompt is not automatically a bad prompt.** Below 2,000 tokens a
  trim buys nothing at all. Between 2,000 and 4,000 it buys latency and
  reliability. Above 4,000 it buys money, because Retell surcharges and
  scales the whole billed duration. Say which band the agent is in.

- **A missing rule is not always a defect.** An outbound agent needs the
  wrong-person rule. An inbound one to a direct line may not. Check the
  use case before calling it a fault.

- **`unreachable` on a global node is a false finding.** Globals are
  reached by condition. The current linter skips them; an older copy may
  not.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `flow has no nodes` on a real export | Dashboard export. Nested under `conversationFlow`, camelCase. |
| `holds a JSON list, not a conversation flow` | A fragment. Ask for the full export. |
| Every section reported missing | The prompt has no headings at all. That is itself the top finding. |
| `promptlint` on a flow file finds nothing | Wrong tool. Flows have no `general_prompt`. Use `flowkit lint`. |
