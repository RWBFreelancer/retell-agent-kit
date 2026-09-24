# The text sandbox and the phone can take different routes through the same flow

Measured 2026-09-05, one example agent flow v53, `--model gpt-4.1`, 8 reps.

A trace said 7 of 8 callers were being closed as an incomplete intake. Real
calls on the same flow shape said 3 of 142. The trace was about to justify a
change to a live routing edge. **The change would have been wrong.**

## What happened

Trace `T-IE-A` drives a caller who gives a name, a callback number, text
permission, a vehicle, an issue and an urgency, and gives only a city for the
location. Six of seven items captured; `missing_fields` comes back as exactly
`full_address`. the client's rule of 2026-08-19 says that call closes NORMALLY: "a
refusal is an answer, so the flow notes the address as missing and closes the
call normally ... A caller who declines one question has not had an incomplete
call."

The trace asserts the call reaches `Closing / Anything Else — Normal` and is
asked "Anything else I should include?".

| Flow | Result |
|---|---|
| `exports/v53-drift.json`, before the 2026-09-05 session | **1 of 8** |
| `exports/v53-postpush6.json`, after six changes | **1 of 8** |

Identical. So the session had not caused it, which is what the measurement was
for. Seven of eight sandbox runs walked

    Service Request Intake -> Incomplete Intake Exit Router
      -> Incomplete Intake Exit — Normal -> ... -> End Call

and the caller heard "No problem. I'll pass along what I have, and the team may
follow up for anything missing" instead of the closing question.

The edge that fires is `Service Request Intake -> Incomplete Intake Exit
Router`, whose condition reads "Caller ends the call, refuses to continue, or
goes silent before vehicle/equipment type, issue description, and city or ZIP
have been captured." Read literally that fires whenever the address is missing,
whatever else was captured. So there was a mechanism, a rule it broke, and 8
reps of evidence. Everything said "narrow that condition."

## What the real calls said

Counted over every one example agent call of 90 seconds or longer, straight from
`/v2/list-calls`:

| Set | calls | said the closing question | said the incomplete line |
|---|---|---|---|
| one example agent, v49 and v50 | 15 | **11** | **0** |
| one example agent, all versions | 142 | **109** | **3** |
| a second example agent, v34 and v37 | 8 | 5 | 0 |

Three calls in 142. Reading all three, none is the case the trace models:

- `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx` said BOTH lines, so it recovered.
- `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx` is a merchant-services solicitation.
- `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx` is a caller who said the whole thing was
  a joke.

Real callers who gave only a city — `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`, "I
don't know the exact address, I just know it's in Dallas"; and
`call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`, a campground named by cross streets — both
reached the closing question normally.

**On the phone this defect does not happen. In the sandbox it happens 7 times
in 8.**

## The rule

**A route difference measured only in the text sandbox is not a defect until a
real transcript agrees.** Sentence counts, variable values, say-once rules and
wiring all transfer from the sandbox. Which EDGE a prompt-judged decision takes
does not always transfer, because the caller's turns do not arrive the same
way.

Root `CLAUDE.md` already says text testing cannot verify voice, interruption or
speech-to-text, and that an empty turn is still a turn. This is the sharper
version: the same limitation moves ROUTING, not just audio. A scripted caller
answers "Irvine" and nothing else, in one clean turn, with no hesitation and no
surrounding chatter. A real caller says "It is, uh, in Newport Beach, the
Newport Dunes, it's a campground on Jamboree and Pacific Coast Highway." Those
two are not the same input to an edge that is judging whether the caller has
stopped cooperating.

## What to do instead

1. When a trace shows a ROUTE problem, count the same thing on real calls
   before writing a transform. `tools/callreview.py`, or a line count over
   `/v2/list-calls`, costs nothing and takes a minute.
2. Keep the trace. `T-IE-A` is still worth having: if the live counts ever move
   toward the sandbox's answer, it is already written. It is documented as a
   WATCH, not a failing guard.
3. Do not "fix" the edge. There is no production defect to fix, and narrowing a
   condition that real calls handle correctly would be a change with a real
   risk and no measured benefit.

## What this cost, and what it saved

The measurement was two 8-rep runs, 34.5 cents. It prevented a change to a live
routing edge on one example agent that would have been justified by a table, a rule and a
mechanism, and would have been wrong.

## The other half of the same day

The reverse error also happened, on the same flow, and is recorded in
[lessons-green-verdict-blindness.md](lessons-green-verdict-blindness.md): a
trace that asserted only "the call ended" passed a call where the caller heard
the goodbye twice. Two extra `say_times` lines turned that false green into a
true red.

Together they are one rule with two faces. **A trace measures exactly what it
asserts, on exactly the input it sends.** Assert more than you think you need,
and check the input against a real call before believing what the assertion
tells you.

## 2026-09-08: the same divergence between the two MODELS, on a say-once count

The rule in the root `CLAUDE.md` said this, and it is now wrong:

> Structural changes, variable plumbing and say-once counts are safe to sign
> off on mini.

**Say-once counts are NOT safe on mini.** Measured the same day, on the same
export, `agents/agent-b/exports/v38-postpush-silence-gate.json`:

| Trace | `gpt-4.1-mini` | `gpt-4.1` |
|---|---|---|
| T-W | FAIL, `"What kind of vehicle or equipment are you calling about?"` said 2x, and never reached `Sign-off & Goodbye` | **PASS** |
| T-Y | FAIL, `"Anything else I should include?"` said 2x | **PASS** |
| T-V | PASS | not re-run |

Both mini failures were run twice, on the changed export and on the unchanged
`v38`, with byte-identical paths, so they were stable and they looked exactly
like real defects.

**Real calls agreed with `gpt-4.1`, not with mini.** Counted over 200 real
a second example agent calls, read-only, free:

| Agent sentence | Calls that said it | Calls that said it 2x |
|---|---|---|
| `"What kind of vehicle or equipment are you calling about?"` | 38 | **0** |
| `"Anything else I should include?"` | 58 | 2, both on **v22 and v19** |
| `"Let me get that written down."` | 12 | 2, both on **v37** |

Zero on the first line, in 38 real calls. The mini failure was not a small
version of a real defect. It did not exist at all.

**Why mini fails where 4.1 does not, on this flow.** Both failing lines are
guarded by prose that asks the model to reason about its own past turns:
`Service Intake` says "a refusal counts as asked and answered", and
`Guardrail Refusals` says the sentence may be said "ONCE in the whole call, by
this node or by the Closing node". `Service Intake` is 1,165 words. That kind
of guard is exactly where the smaller model gives out.

**The rule.** A trace whose subject is a say-once count, on a node whose guard
is PROSE rather than an edge equation, is not evidence on mini. Re-run it on
`--model gpt-4.1` before believing either the red or the green. A guard that is
an equation on a variable is still safe on mini, because the equation does not
care which model reads it.

**The cheap order, and it matters.** Real calls first, at zero cost, then one
`gpt-4.1` run. On this defect that order was: free count, then 33 cents. Fixing
either "defect" would have meant editing a 1,165-word intake node, which
`docs/lessons-intake-node-capacity.md` shows makes complete calls WORSE. The
free measurement stopped a change that would have cost money and made the agent
worse.

## The sandbox agent does not carry the production agent's settings

Found 2026-09-24 while testing the handbook presets.

`retell_chat.Sandbox` creates the chat agent with only `response_engine` and
`agent_name`. Every agent-level setting falls back to Retell's default. The one
that touches the prompt is `handbook_config`: Retell's defaults are
"Default Tone - Professional" (about 480 tokens) and "AI Disclosure When Asked"
(about 30) ON, everything else off. Production a second example agent runs the opposite:
`high_empathy` and `nato_phonetic_alphabet` ON, both of those OFF.

**Wrong before:** every trace since the sandbox was built ran with a different
handbook, so a different prompt, from real calls. Nobody had checked. Analysis
fields were never on a sandbox agent either.

**Evidence:** `docs/test-log.md`, 2026-09-24, 27 chats on 3 hand-built chat
agents. Passing `handbook_config`, `post_chat_analysis_data` and
`post_chat_analysis_model` to `create-chat-agent` works; `get-chat-agent` echoes
them back. With production vs all-off handbook the transcripts matched or
differed only by normal run-to-run noise, so no earlier result is known to be
wrong because of it. NATO does not apply to chat agents at all (Retell's Agent
Handbook page), so a text sandbox can never test it.

**Rule:** when a test depends on tone, disclosure, or anything an agent setting
controls, build the sandbox agent with production's `handbook_config` (from
`agents/agent-b/agent-settings.json`), not the bare default. To test post-call
analysis without touching real calls, give the chat agent the real
`post_call_analysis_data` as `post_chat_analysis_data`. Never use the dashboard
"rerun analysis" on real calls: the docs do not say whether it re-fires the
`call_analyzed` webhook, and a re-fire would send the downstream owner the call again.
