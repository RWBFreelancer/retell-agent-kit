---
name: test-single-prompt
description: Test and fix a Retell single-prompt voice agent. Lints the prompt offline with 27 checks, drives a throwaway copy over text with scripted caller turns, reads what real callers actually heard, and applies fixes as a safe draft push. Works with or without an API key. Use when a single prompt agent misbehaves, repeats itself, asks two questions at once, ignores a rule, mispronounces numbers, or when someone wants to audit, debug, improve, or QA a retell-llm or prompt-based agent.
---

# Test and fix a single-prompt agent

Run `setup` first if the mode is not set.
`K` below means the retell-agent-kit repo root (found via `.kit-path` in retell-clients).

## The fix ladder. Climb it in order.

Most people jump to step 4 and rewrite the prompt. Do not.

1. **Read a real transcript.** What the caller HEARD, not what the prompt
   SAYS. On one real project this found five defects in ten minutes.
2. **Lint.** Offline, free, 27 checks.
3. **Reproduce it in a sandbox.** A defect you cannot reproduce is a
   guess.
4. **Change the smallest thing.** Then re-run the same script.

## Step 1: read what the caller actually heard

```bash
python "$K/kit/agentkit.py" calls --agent-id agent_xxx --limit 5 --redact
python "$K/kit/agentkit.py" calls --agent-id agent_xxx --limit 10 --summary
```

`--redact` masks phone numbers and emails. `--summary` shows the recap
fields instead of the whole transcript.

**Privacy.** Transcripts carry names, numbers, and addresses. Terminal
only. Never paste them into a repository, a changelog, or a prompt. Quote
the agent's own line and the call id instead.

## Step 2: lint the prompt. No API key needed.

```bash
python "$K/kit/sp.py" pull --llm-id llm_xxx --out llm.json     # needs a key
python "$K/kit/promptlint.py" llm.json
python "$K/kit/promptlint.py" llm.json --json                  # machine readable
```

No key? Point it straight at whatever the client sent: a `.md`, a `.txt`,
an LLM export, or a full agent export. It reads all four.

The 27 checks, grouped:

| Group | Finds |
|---|---|
| structure | Missing section, under either accepted structure |
| size | Over 2,000 quality tokens, or over 4,000 billing tokens |
| speech | Literals the agent will mispronounce, with the fix for each |
| turn-taking | Two questions stacked in one line |
| required | No guess rule, no end-call rule, no scope limit, no AI deflection, no wrong-person rule, no transcription-error rule, no never-ask-twice rule |
| risk | Guarantee, promise, price, diagnosis language |
| amplify | Em dash, fillers, three-option limit, timezone-once, ALL_CAPS variables, number format, tool bridge, time awareness |
| variables | Used but never supplied |
| examples | Where they are, and the warning to re-read them |
| greeting | `begin_message` empty, or the quote-marks trap |
| duplication | The same instruction line twice |

## Step 3: reproduce it in a sandbox

```bash
python "$K/kit/sp.py" chat --file llm.json \
    -m "hi there my van broke down" \
    -m "it's Jane Doe" \
    -m "how much will this cost me?"
```

Or against a live agent, which the kit copies into a throwaway first:

```bash
python "$K/kit/sp.py" chat --llm-id llm_xxx -m "hello"
```

Seed dynamic variables with `--seed '{"COMPANY_NAME":"Acme"}'`.
Save the transcript with `--out`, **outside any repository**.

**Run it more than once.** A prompt-driven agent is a weighted coin, not a
switch. One clean pass is a sample. If a behaviour matters, run it three
times and say how many passed.

## Step 4: fix, smallest change first

In order of how well each works:

1. **Add a negative example.** Show the wrong behaviour and label it
   wrong. A negative example moves a model where more prose does not.
2. **Move the rule closer to where it fires.** A rule in Important
   Reminders is weaker than the same rule in the Stage that needs it.
3. **Delete a contradicting example.** An example outranks the rule it
   contradicts. Always hunt for a stale one before adding new prose.
4. **Add prose.** Last, not first. It is the weakest lever and it costs
   tokens.
5. **Make it structural.** If a rule MUST hold, a prompt cannot guarantee
   it. Move to a conversation flow. See `build-flow`.

Then re-run the exact same script from step 3 and compare.

## Step 5: push the fix

```bash
python "$K/kit/sp.py" push --file llm.json --llm-id llm_xxx
python "$K/kit/sp.py" push --file llm.json --llm-id llm_xxx --push
```

Dry run first, always. It lints, refuses on a FAIL, refuses a published
version, reads back to confirm it landed, and never publishes.

Keep the pre-change `llm.json`. That snapshot is your only way back.

## Verified commands

Example commands, proven against a real workspace.

```bash
K=$(cat .kit-path)
RETELL_API_KEY= python "$K/kit/promptlint.py" llm.json
python "$K/kit/sp.py" pull --llm-id llm_xxx --out llm.json
python "$K/kit/sp.py" chat --file llm.json -m "hi" -m "it's Jane Doe"
python "$K/kit/agentkit.py" calls --agent-id agent_xxx --limit 5 --redact
python "$K/kit/sp.py" cleanup --yes
```

Real findings from linting a live 36,878-character production prompt:

```
FAIL  greeting            begin_message is '""', which is quote marks, not text
FAIL  required/one-question  no 'one question at a time' rule
WARN  amplify/em-dash     51 em dash character(s) in the prompt
WARN  size                about 9219 tokens, over BOTH lines (2000, 4000)
WARN  turn-taking         two or more questions in one line (line 123)
```

## Gotchas

- **A text sandbox cannot show whether the agent speaks first.**
  `create-chat` returns no messages at all, so `begin_message` never
  arrives as its own turn. It gets folded into the reply to turn one.
  Confirmed live. Only a phone call proves the greeting fires on pickup.

- **A text sandbox cannot express silence.** An empty turn is still a
  turn. Anything about a caller going quiet must be walked on paper.

- **An exact-sentence count is blind to a paraphrase.** If you check that
  a line is said once, the agent saying the same thing in different words
  passes. Read the transcript, do not only count.

- **A green lint is not a working agent.** Structure is not behaviour.

- **A green everything is not a delivered lead.** Run `delivery-check`.

- **Test evidence expires the moment the prompt is edited by hand.** A
  pass from before a dashboard edit proves nothing about now.

- **Sandbox runs cost about 0.7 cents a message.** Over five turns needs
  `--yes`.

- **Clean up after a crash.** `python "$K/kit/sp.py" cleanup --yes`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| The sandbox ignores your change | You used `--llm-id` on a live agent and Retell gave the chat agent version 0. Use `--file`. |
| `promptlint` flags a `$3` that is inside a rule banning it | Lines containing not, never, avoid, or an arrow are suppressed. Ones inside an example dialogue are not. Read the line. |
| A rule is in the prompt but ignored | Search for an example showing the opposite. The example wins. |
| The caller hears `{{BRACES}}` | The variable is never supplied. Add a `default_dynamic_variables` entry. |
| Fixed in the sandbox but still wrong on a real call | Voice differs from text: interruption, speech-to-text, and timing exist only on a call. |
