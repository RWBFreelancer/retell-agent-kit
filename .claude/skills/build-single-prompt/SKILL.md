---
name: build-single-prompt
description: Build a Retell single-prompt voice agent from a written brief, from documents, or from scratch. Asks the ten discovery questions first, drafts the sectional prompt, lints it offline with 27 checks, drives a throwaway copy over text to prove it behaves, then writes a draft or hands over a JSON file to import by hand. Works with or without an API key. Use for creating a new single prompt agent, a retell-llm, a prompt-based voice agent, or turning a call script or document into a voice agent.
---

# Build a single-prompt Retell agent

Run `setup` first if the mode is not set. It asks about the API key.

`K` below means the retell-agent-kit repo root (found via `.kit-path` in retell-clients).

## Step 0: is a single prompt right?

Read `K/docs/reference/agent-type-choice.md`. Three things force a conversation
flow instead, and finding out later costs a rebuild:

1. A **required field**. Prose cannot guarantee a question was asked.
2. A **legal or safety line that must be said once**. Prose cannot count.
3. A **branch that must be exact**, not a judgement call.

Say which one applies, or say none do, then continue.

## Step 1: ask the discovery questions. Before drafting. Always.

Ten questions in four groups, from
`K/docs/reference/amplify-voice-prompt-engineer.md`. Gather every answer before
you write a line, or you will pay for it in revision rounds.

**Use case**
1. What is the agent's one primary objective?
2. Inbound or outbound? If outbound, what triggers the call?
3. What do you already know about the contact before the call?
4. What is the ideal outcome, and the fallback?

**Integration**
5. What tools are needed? Calendar, SMS, CRM, knowledge base, transfer.
6. Business hours, blackout dates, scheduling limits?
7. What must be collected, and what must be confirmed?

**Brand**
8. Personality and tone?
9. Required phrases, company terms, compliance lines?
10. How should it handle objections and off-topic questions?

Use `AskUserQuestion` in batches. Do not ask all ten in one wall of text.

If they gave you documents instead, read them first and ask only what the
documents do not answer.

## Step 2: draft from the template

Start from `K/templates/single-prompt.md`. Do not start from a blank file.
The template already carries every rule the linter checks, in the right
order, and it lints 0 fail.

Its eight sections, and what each holds, are in
`K/docs/reference/amplify-voice-prompt-engineer.md`.

Rules that catch people out:

- Ask one question at a time. This is the rule that breaks most often.
- **Never use the em dash.** Use a hyphen.
- Write symbols as words. Not the dollar sign, not the at sign.
- Phone numbers in groups of three. Names and emails spelled in letter
  groups.
- Say the timezone once.
- Variables in `{{ALL_CAPS_WITH_UNDERSCORES}}`. Always include
  `{{current_time}}` and `{{user_number}}` under Context.
- At most three choices at any point.
- Under 2,000 tokens excluding the knowledge base.

Write it to a file, then substitute the placeholders. On Windows use a
heredoc through the Bash tool, or edit the copied template.

## Step 3: lint it. No API key needed.

```bash
python "$K/kit/promptlint.py" my-prompt.md
```

27 checks. Fix every FAIL. Read every WARN and say why you are keeping it.

The five FAIL classes are: a missing critical section, no "do not guess"
rule, no end-call rule, no one-question rule, no scope limit, and a
`begin_message` that is quote marks rather than text.

Then build the LLM object:

```bash
python "$K/kit/sp.py" new --from my-prompt.md --out llm.json \
    --begin "Hi, thanks for calling Example Company, this is Kate. How can I help?"
```

`new` lints again automatically. Omit `--begin` to let the caller speak
first.

## Step 4: prove it behaves. This is the step people skip.

A clean lint means the prompt is well formed. It does not mean it works.

```bash
python "$K/kit/sp.py" chat --file llm.json \
    -m "hi there my van broke down" \
    -m "it's Jane Doe" \
    -m "how much will this cost me?" \
    -m "five five five one two three four five six seven"
```

Read the transcript. Check, by eye:

- one question per turn
- the price refusal actually fires
- the number read back in groups of three
- the enthusiasm word varies
- no braces from an unsupplied variable

Run it a second time with different wording. A prompt-driven agent is
probabilistic. One pass is a sample, not a proof.

## Step 5: hand it over

**No API key.** Give them `llm.json`. In the Retell dashboard: create an
agent, choose Single Prompt, paste `general_prompt`, set `begin_message`,
set the model and temperature. Say exactly that.

**With an API key.** Dry run first, always:

```bash
python "$K/kit/sp.py" push --file llm.json --new
python "$K/kit/sp.py" push --file llm.json --new --push
```

`push` refuses if promptlint reports a failure, refuses a published
version, reads the result back to confirm it landed, and never publishes.

Then attach it to an agent and run `delivery-check`.

## Verified commands

Example commands, proven against a real workspace.

```bash
K=$(cat .kit-path)
RETELL_API_KEY= python "$K/kit/promptlint.py" "$K/templates/single-prompt.md"
python "$K/kit/sp.py" new --from prompt.md --out llm.json --begin "Hi..."
python "$K/kit/sp.py" chat --file llm.json -m "hi" -m "it's Jane Doe"
python "$K/kit/sp.py" cleanup --yes
```

Real output from the live run, showing the rules holding:

```
CALLER: it's Jane Doe
 AGENT: Great, Jane. So, I have your name as Jane Doe, spelled J A N E - D O E.
        What is the best number to reach you on?
CALLER: how much will this cost me?
 AGENT: I am not able to give a price on this call. What I will do is pass this
        to the team and they will come back to you with that. So, what is the
        best number to reach you on?
```

## Gotchas

- **A text sandbox cannot show whether the agent speaks first.**
  `create-chat` returns no messages at all, so `begin_message` never
  arrives as its own turn. The agent folds it into its reply to turn one.
  Only a real phone call proves the greeting fires on pickup.

- **A text sandbox cannot express silence.** An empty turn is still a
  turn. Anything hinging on a caller going quiet must be walked on paper
  and confirmed on a real call.

- **An example outranks the rule it contradicts.** After changing any
  rule, re-read every example. A stale example showing the old behaviour
  beats the new rule written above it. This is the commonest cause of an
  agent ignoring a rule that is plainly there.

- **`begin_message` can be the two-character string `""`.** A dashboard
  paste stores quote marks, the API reports the field as set, and the
  agent speaks nothing. `promptlint` fails on this specifically.

- **Two size lines, not one.** 2,000 tokens is quality and latency. 4,000
  is Retell's billing surcharge. Below 2,000 a trim buys nothing.

- **Speech-check false positives are suppressed, not perfect.** A `$3` on
  a line that says "not $3" is ignored. A `$3` in an example dialogue is
  not. Read the line before you act.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `promptlint` says a section is missing that is clearly there | It grades against whichever of the two structures fits better. Check the `structure` line saying which it chose. Rename the heading to match. |
| The agent stacks two questions despite the rule | Add a negative example showing the wrong behaviour. A negative example moves a model where more prose does not. |
| The caller hears `{{SOMETHING}}` | The variable was never supplied. Add it to `default_dynamic_variables`, or seed it with `--seed '{"NAME":"value"}'`. |
| `push` refuses | Read the lint block above the refusal. Fix the FAIL, or pass `--force` and state the reason out loud. |
