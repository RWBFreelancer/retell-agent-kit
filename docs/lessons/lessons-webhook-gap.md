# The days a client got no leads, and no error said so

2026-08-27. Rey found that a second example agent agent versions 24, 25 and 26 were published
with `webhook_url` unset. Every call answered on those versions was analysed
correctly by Retell and then forwarded nowhere.

The window: **2026-08-24 23:19 to 2026-08-27 08:58**, 22 calls, of which 3 were
real service leads and 1 was a message asking the client to call back.

Nothing in this repository said anything was wrong. Every test was green. The
flow was correct. The agent was correct. The deliverable was not being
delivered.

## Lesson 41 - a green flow can still deliver nothing, because the delivery setting is not in the flow

`flowlint.py` proves the wiring. `tracerun.py` proves what the agent says.
`simtest.py` proves it handles an improvising caller. `askcheck.py` proves every
question was asked. All four passed throughout the outage, because **none of
them can see `webhook_url`.** It is not in the ConversationFlow at all. It lives
on the Agent object.

The whole point of Phase 1 is "collect the caller details and send a recap for
a human to read". For three days the agent did the collecting perfectly and the
sending not at all.

**The general rule.** For every deliverable, name the ONE setting that carries
it out of the system, and check that setting separately from everything that
produces it. A test suite scoped to the flow cannot fail on a setting that is
not in the flow. Ask "what would still be broken if every test passed?"

## Lesson 42 - Retell omits null fields, so a lost setting reads as a deleted line, not a fault

This is the reason nobody caught it, and it is the part worth fixing in code.

`tools/agentpull.py` mirrors the agent object into `agent-settings.json` and
`AGENT-SETTINGS.md` precisely so `git diff` shows drift. It built its rows with:

```python
rows = [(k, agent[k]) for k in keys if k in agent]
```

Retell's API omits a field that is null. So when `webhook_url` was cleared, the
key was absent from the response, the row disappeared from the mirror, and the
key vanished from the JSON.

`git diff` therefore showed a **deleted line**. A deleted line reads like
tidying up. A changed value reads like a fault. The drift detector was working
and reported the outage in the one format a human ignores.

**The fix, now in the tool.** A `REQUIRED` list of settings that are always
rendered, showing `_not set_` when absent, and written into the JSON as an
explicit `null`:

```python
REQUIRED = ["webhook_url", "webhook_events"]
...
rows = [(k, agent.get(k)) for k in keys if k in agent or k in REQUIRED]
...
for k in REQUIRED:
    stable.setdefault(k, None)
```

**The general rule.** Any mirror built for drift detection must distinguish
"this setting is off" from "this setting is not in the response". Absence and
emptiness are different facts, and only one of them is an outage. Render the
critical ones unconditionally.

**And the second-order rule.** When a monitoring tool fails to catch something,
check whether it actually reported it in a form nobody reads, before adding a
new tool. The report existed. The format defeated it.

## Lesson 43 - nothing is lost, because Retell stores the whole call

The recovery was straightforward and is worth knowing before the next outage.

`GET /v2/get-call/{id}` returns the complete call, including `call_analysis`
with all 34 custom fields. That is exactly the payload the webhook would have
carried. So a missed webhook is a **delivery** failure, never a data loss.

`tools/webhookreplay.py` reads those calls back and POSTs them in Retell's own
envelope:

```
{"event": "call_analyzed", "call": { ... }}
X-Retell-Signature: v={unix_ms},d={hmac_sha256(body + timestamp, api_key)}
```

The signature scheme is documented at
https://docs.retellai.com/features/secure-webhook. The timestamp is generated
fresh, so the 5-minute replay window is satisfied and a workflow that verifies
will accept the replay. Measured on 2026-08-27: all 6 replayed calls returned
`HTTP 200 {"message":"Workflow was started"}` from the n8n endpoint.

**The general rule.** Before rebuilding anything by hand after a webhook
outage, check whether the platform still holds the events. Retell does. Replay
beats reconstruction, and it produces the recap in the format the client
already reads instead of a one-off spreadsheet.

## Lesson 44 - `unknown` is the analyser abstaining, and it is not the same as `no`

Two of the six replayed calls were pitches: a merchant-account pitch from
"A List Payments", and a truck-parking platform. Both were graded:

    sales_or_spam : "unknown"
    call_type     : "non_service_business_message"

**The first read of this was wrong and is worth recording.** They were reported
as `sales_or_spam: false`, because the checking code treated anything that was
not `yes` as a negative. The enum is `yes` / `no` / `unknown`, and the value was
`unknown`. The analyser did not decide these were not sales. It declined to
decide at all, and a "not yes" test hides that completely.

Counted across all 182 a second example agent calls:

| `sales_or_spam` | Calls |
|---|---|
| `no` | 90 |
| `unknown` | **85** |
| `yes` | **2** |
| absent | 5 |

Two `yes` in 182 calls, and neither of them was one of the two clearest pitches
in the whole set.

**The cause was the description**, which read in full:

> "Whether the call is a sales, spam, or solicitation call. unknown if not
> clear."

Thirteen words, no list, no examples, and an explicit invitation to abstain.
Meanwhile the FLOW's `Guardrail Refusals` condition carries a long, specific
list of what counts, built by measurement: trace T-AF went 0 of 3 before that
list and 3 of 3 after. **The post-call analyser was never given it.** The same
requirement was solved carefully in one place and left bare in the other.

`call_type` failed the same way. `sales_solicitation` was an available choice
and was plainly correct; the model picked `non_service_business_message`
because nothing said which wins when a caller is both a business and a pitch.

The fix, in `tools/agentfields.py`: both descriptions now carry the flow's own
list, state that a pitch stays a pitch when it arrives as the ANSWER to an
intake question, say `sales_solicitation` OUTRANKS
`non_service_business_message`, and narrow `unknown` to "too little was said to
tell, such as a hang-up" instead of "not clear".

**Three general rules.**

1. **A three-value enum needs its middle value defined as tightly as its ends.**
   "unknown if not clear" makes abstaining the safe choice for any hard call,
   so the field stops discriminating exactly where it is needed. Say when
   `unknown` is FORBIDDEN, not only when it is allowed.

2. **When a rule is solved in the flow, port it to the analysis field that
   describes the same fact.** They are two independent classifiers of one
   question, and getting one right does nothing for the other. This is
   lesson 24 again from the other direction: two descriptions of the same fact
   must not disagree, and one of them being empty IS a disagreement.

3. **Never collapse an enum to a boolean when reading it.** `!= "yes"` merges
   "no" and "unknown", which are opposite facts about the analyser's
   confidence. Read the three values and count them separately, or the
   abstention rate stays invisible.


## Lesson 45 - deleting a Retell field silently re-routes the n8n workflow that reads it

2026-08-27. Rey exported the n8n workflow "Retell Voice AI Phase 1 - Recap Only"
for review. It is well built - event guard, retry de-dupe, business-timezone
folders, a careful status ladder. It is also **broken for every live call**, and
this repository caused it.

On 2026-08-23 `tools/agentfields.py` removed `item_category` and
`service_area_status` from a second example agent's `post_call_analysis_data`, under "facts,
not categories": the client moved the the client CRM category and the service-area
verdict to the downstream owner. That was correct and approved.

The n8n workflow reads `item_category` eight times. Its accessor supplies a
fallback:

```js
item_category: s(cad.item_category, 'unclear'),
```

and its status ladder tests, BEFORE the qualified branch:

```js
else if (isServiceish
      && (f.item_category === 'passenger_vehicle'
       || f.item_category === 'unclear'))   status = 'REVIEW SCOPE';
```

So a deleted field became the string `'unclear'`, and `'unclear'` was already
spoken for as "the category could not be determined". **`[QUALIFIED]` became
unreachable.**

Measured by running the node's real `jsCode` against three real leads from the
webhook-gap backlog:

| Payload shape | Before | After the one-line guard |
|---|---|---|
| a second example agent, no `item_category` (all live traffic) | `[REVIEW SCOPE]` | `[QUALIFIED]` |
| one example agent, `commercial_truck` | `[QUALIFIED]` | `[QUALIFIED]` |
| one example agent, `passenger_vehicle` | `[REVIEW SCOPE]` | `[REVIEW SCOPE]` |
| one example agent, `unclear` | `[REVIEW SCOPE]` | `[REVIEW SCOPE]` |

`qualified_service_request` was `true` the whole time. Only the subject-line
label was wrong - the triage the client approved on 2026-08-10, on every genuine
lead, for four days.

**Why nobody saw it.** one example agent still carries both fields, so the workflow is
correct for one example agent and wrong for a second example agent. a second example agent takes 100% of live calls.
The two systems drifted apart, and the side carrying the traffic is the broken
one.

**Three general rules.**

1. **A field deletion is an interface change.** `post_call_analysis_data` is a
   contract with whatever consumes the webhook. Before removing a field, grep
   every consumer for its name. The consumer here is outside this repository,
   which is exactly why it was missed.

2. **A fallback value must not collide with a real value.** `'unclear'` meant
   both "not determined" and "this agent no longer sends it". A fallback needs
   to be a value the field can never legitimately take - `null`, or a distinct
   sentinel - so downstream code can tell absent from uncertain. This is
   lesson 42 again, one system further along: absence and emptiness are
   different facts.

3. **Two agents on one webhook need the same field set, or the consumer must
   handle both.** Running a comparison pair is only safe while the thing
   reading them can tell them apart. Add the check to the delivery protocol.

**The fix**, applied in n8n, not in this repository: one derived flag,
`const hasItemCategory = s(cad.item_category) !== '';`, added to the ladder
branch so it fires only when a category was actually sent. one example agent behaviour is
byte-identical; a second example agent gets its label back.

**Also found in the same review, and NOT yet fixed:**

- `uncertain_fields` appears **zero** times in the workflow. It is the $75
  deliverable the client approved on 2026-08-19, the Retell side now produces it,
  and the recap email never prints it.
- The workflow never reads `collected_dynamic_variables`, although root
  `CLAUDE.md` names it as the reliable source for the two recap lists. It
  recomputes its own missing list from the analysis fields instead.
- The webhook node has **no authentication and no signature check**. Anyone who
  learns the URL can post a fake lead. That is why `webhookreplay.py` was
  accepted; the signature it sends is never verified.

---

## Lesson 46 - a tool built for one agent of a pair will carry that agent's flow assumptions onto the other

2026-08-27. Rey asked whether a second example agent's changes should go to one example agent. one example agent
had the same solicitation miss lesson 44 describes: `sales_or_spam` at 14
words, `call_type` at 51, byte-identical to a second example agent before v28. The fix lives
in `tools/agentfields.py`, the tool already takes `--agent a`, and the obvious
move was to run it.

**Running it unguarded would have made five changes to one example agent, not the one
that was wanted.** Read from the dry run before the guard existed:

| Block | What it would have done to one example agent | Correct? |
|---|---|---|
| `UNCERTAIN_FIELDS` | ADD `uncertain_fields`, described as "copy the value of `{{uncertain_fields}}`" | **No** |
| `MISSING_REQUIRED_DESCRIPTION` | repoint `missing_required_fields` at "copy `{{missing_fields}}`" | **No** |
| `REMOVE_FIELDS` | delete `item_category`, `service_area_status` | Interface change, needs a decision |
| `HUMAN_REVIEW_DESCRIPTION` | drop the service-area clause | Only alongside the removal |
| `DESCRIPTION_FIXES` | rewrite `sales_or_spam` and `call_type` | **Yes.** The only one wanted |

The first two are the dangerous ones. `{{missing_fields}}` and
`{{uncertain_fields}}` are built by a second example agent's `Capture Check` extract node and
`Recap Lists` code node, added in the v24 rebuild. **one example agent's 21-node flow has
neither.** Confirmed by counting: both strings appear **zero** times in
`agents/agent-a/exports/v51.json`.

So the model would have been told to copy a variable that never exists. Two
fields arriving blank on every one example agent call, in the recap the client reads, and
nothing in the tool's output would have said so - it reports
`uncertain_fields: ADDED (plan Step 6)`, which reads like success.

### The general rule

**An agent-level tool encodes assumptions about a flow. Name which agent's
flow, and gate on it.** `post_call_analysis_data` is on the Agent object, so
neither `flowlint.py` nor `tracerun.py` nor any transform can see the mismatch.
The field says "copy `{{x}}`" and the flow that must set `{{x}}` is a different
object entirely. Nothing cross-checks the two.

This is lesson 41 turned around. Lesson 41: a flow-scoped test cannot fail on a
setting that is not in the flow. Lesson 46: **an agent-scoped tool cannot fail
on a variable that is not in the agent.** Both halves of the split need the
same question asked - *what would still be broken if this tool reported
success?*

The tell is a field description containing `{{...}}`. Every one of them is a
contract with a specific flow. Before running an agent-level tool against a
second agent, grep that agent's export for every `{{variable}}` the tool's
descriptions mention, and gate any block whose variables come back zero.

### The fix, now in the tool

Two independent gates, because the two questions are independent:

```python
RECAP_VARIABLE_AGENTS = {"b"}          # needs Capture Check + Recap Lists
FACTS_NOT_CATEGORIES_AGENTS = {"a", "b"}  # needs nothing from the flow
```

`build()` takes `agent_key` and reports what it skipped, rather than skipping
silently:

```
agent 'a': flow has no Recap Lists node, so the uncertain_fields and
           missing_required_fields blocks are SKIPPED
```

A skipped block that announces itself is the point. The old code could not
distinguish "this agent does not need it" from "this agent was forgotten".

**Regression proof that a second example agent was untouched:** the `--agent b` dry run after
the change reports all seven blocks `already correct` and `changed: False`.

**What landed on one example agent**, draft v51, verified by a fresh `agentpull.py`:
35 fields to 33, `item_category` and `service_area_status` removed,
`uncertain_fields` NOT added, three descriptions changed (`call_type`,
`sales_or_spam`, `human_review_required`), no `choices` array touched. Reversal:
`agents/agent-a/exports/v51-post-call-analysis-before.json`.

one example agent and a second example agent now differ by exactly one analysis field,
`uncertain_fields`, and that difference is correct: only a second example agent's flow can
populate it. Lesson 45's rule is satisfied - the consumer handles both, because
the one field that differs is one n8n never reads.

---

## Lesson 47 - a trace built on silence measures the sandbox, not the flow

2026-08-27, building `transforms/a_emergency_line_flag_gap.py` for one example agent.

one example agent's `Roadside / Safety Gate` leaves by four edges. Three set both
`roadside_gate_visited` and `emergency_line_said`. The fourth,
`edge-1783001197053-emjqtacbk`, sets only `roadside_gate_visited` - and its own
prompt covers two different situations:

    "Caller hangs up, goes silent, or refuses to continue BEFORE CONFIRMING
     THEY ARE SAFE, or BEFORE THE BLOCKING-TRAFFIC-OR-BUSINESS STATUS HAS
     BEEN CAPTURED."

A caller who confirms safety hears the emergency-service line, because the gate
says it "in your very first turn after the caller answers the safety question".
If they then stop answering at the blocking-traffic question they leave by that
edge with `emergency_line_said` still `"false"`, and the router sends them to
the twin whose job is to say the line they just heard.

### The wasted pair

The first `T-A4` drove that edge with three empty turns. It measured:

| Export | Result |
|---|---|
| before the fix | 2 of 8 |
| after the fix  | 2 of 8, and two reps said the line THREE times |

Identical, so the fix looked worthless. It was the trace that was worthless.
`path walked` gave it away:

    Greetings -> Contact Capture -> Triage -> Roadside / Safety Gate

The call never left the gate. The sandbox sends `""` as a user message, the
gate answers and re-reads its own instruction, and the repetition being counted
was the gate stalling against an artificial empty turn - not the routing defect
under test. The edge never fired, so neither export was ever exercised.

### The fix to the trace

Same edge, driven by the OTHER trigger in its own prompt:

    "look I'm not answering any more questions, just send somebody out"

| Export | Result | `path walked` |
|---|---|---|
| before | 7 of 8 | Gate -> Flag -> Incomplete Exit -> Router -> **After Roadside** twin |
| after  | **8 of 8** | routes to the Normal twin instead |

The before-run's `vars` is the proof the static reading was right:
`{'roadside_gate_visited': 'true', ...}` with **no `emergency_line_said` at
all**.

### Two general rules

1. **Never drive a trace through silence.** Root `CLAUDE.md` already says text
   testing cannot express a caller going silent, and that an empty turn is
   still a turn. The trap is that such a trace still RUNS and still prints a
   number. It fails honestly-looking, at a stable rate, on both exports. When
   an edge fires on "silent OR refuses", drive it with the refusal; when it
   fires only on silence, walk it on paper and confirm on a real call.

2. **A before/after pair that reads identical is a claim about the TRACE
   first.** Before concluding a fix did nothing, read `path walked` and check
   the trace reached the changed path at all. Lesson 33's noop control catches
   a fake defect rate; this catches a fake NON-defect rate, and nothing in the
   runner's output flags it. The runner cannot know which path you meant.

Checklist lines J11l and J11m.

---

## Lesson 48 - an error branch that ends in a NoOp is a silent failure by design

Recorded 2026-09-01, while building `transforms/example_dual_send.py`.

### What happened to the downstream owner, and nearly happened here

the downstream owner's the client CRM intake broke on 2026-08-28 and stayed broken until
2026-09-01. 66 workflow runs died. 38 callers who spoke got no text and no
email. 13 of them gave a name and should have become leads.

the client noticed before the downstream owner did, because there was nothing to notice. the downstream owner's
own words in the the client CRM group, 2026-09-01:

> "A failed run is silent on your side, so it looked like a quiet week."

The bug was not the expensive part. The missing alarm was. He fixed both, and
he tested the alarm by deliberately breaking something to prove it fires.

The first draft of the dual-send in this repository put a **NoOp** on the
HTTP node's error output, named `Handoff Failed - Logged`. That is the same
trap. It writes an execution record nobody opens. Three days of lost leads
would have looked exactly like three quiet days.

### Why this keeps happening

Lesson 41 already recorded this repository losing three days to a silent
delivery failure, because `webhook_url` was unset on three published versions.
Same shape, different layer:

| | The 2026-08-24 gap | the downstream owner's 2026-08-28 gap | The NoOp nearly shipped |
|---|---|---|---|
| What broke | a setting off the flow | a code fault | nothing yet |
| Why nobody saw | no test reads the agent | no failure alarm | a NoOp is not an alarm |
| Cost | 3 days of leads | 66 runs, 13 leads | would have been the same |

An error branch feels handled because it exists. Wiring the error output to
*something* satisfies the linter, satisfies the reviewer's eye, and delivers
exactly as much warning as leaving it unwired.

### The general rule

**An error path must reach a human, or it is not an error path.** A NoOp, a
log line, a `console.log`, a swallowed `try/catch`, and an execution record in
a dashboard nobody opens are all the same thing: a silent failure with extra
steps.

Three tests for any error branch you write:

1. **Who gets woken up?** Name the person and the channel. If the answer is
   "it is in the logs", it is not handled.
2. **Which person?** The operator, not the client. the client already gets the
   recap; a delivery fault is Rey's to fix and would be noise to him. the downstream owner's
   new alarm alerts the downstream owner and not the client, for the same reason.
3. **Has it actually fired?** the downstream owner broke something on purpose to prove his
   alarm works. An untested alarm is an assumption, and this file exists
   because of an untested assumption.

Also: an alert node must not be able to take the workflow down with it. Set the
alert's own error handling to continue.

### What landed

`Handoff Failed - Alert Rey`, a Gmail node on the HTTP error output, reusing
the credential the recap email already uses so no new credential is needed. It
carries the call ID, the caller number, the dialled number and the error. The
recap email path is untouched, so a fault at the downstream owner's end never costs the client
his recap.

Do not change it back to a NoOp.

## 2026-09-09: the same shape again, one layer further out

the downstream owner reported every handoff returning 401 from 08:53 Pacific. Ten failed
handoffs across eight callers. His reading was that the a second example agent republish, v37
to v38, had put an older credential back.

**It had not, and it could not.** The token is not in the workflow. The
`Send to the downstream owner` node holds no value at all. It holds a pointer:

    credentials.httpHeaderAuth = {"id": "KPmpD2rgfiFijVsq",
                                  "name": "Header Auth account"}

So four things in this repository were blind to it at once. `flowdiff.py` cannot
see it, because it is not in the flow. A workflow snapshot cannot see it: the
`Send to the downstream owner` node is byte-identical across `recap-2026-09-05-live-postpush`,
`recap-2026-09-06-live`, and both 09-08 snapshots. `git diff` cannot see it, for
the same reason. And `deliverycheck.py` passed on both agents that same morning,
because it checks Retell to n8n and this break was n8n to the downstream owner.

**n8n never returns a credential value through its API, by design.** So the
value cannot be read, compared, or diffed. The only way to know is to make n8n
use it and watch what comes back. `tools/n8n_credcheck.py` does that.

**A single probe proves nothing. It needs three controls.** Measured
2026-09-09, before and after the token was replaced:

| Probe | Before, 03:00:37Z | After, 03:15:48Z |
|---|---|---|
| A, the real credential | 401 `Unauthorized` | **400** `{"status":"rejected","problems":["a handoff needs at least a phone number or a caller name"]}` |
| B, a token invented on purpose | 401 | 401 |
| C, no auth at all | 401 | 401 |
| D, same credential aimed at Rey's OWN n8n webhook | 200, `authorization` arrived | 200, `authorization` arrived |

Each control kills one wrong conclusion. Without **D**, a 401 from A might only
mean the throwaway node never attached the credential, which looks identical.
Without **B and C**, a 200 from A might only mean the endpoint had stopped
checking auth. And the "after" row is the real proof: A stopped being refused at
the door and was turned away by the downstream owner's own validator instead, while B and C
did not move.

**The general rule.** When a call fails auth, the thing to test is the
credential in the place that sends it, not the code around it. And prove the
probe works before you trust what it says: send the same credential somewhere
you control and confirm the header actually leaves.

**Two habits this run is worth copying.** Probe with an EMPTY body, so the auth
layer answers and nothing is written. `Send to the downstream owner` creates or updates a real
customer in the client's account, so a probe carrying a real payload would have put
junk in there. And never print the value: D reports header NAMES only.

**One wrong turn worth recording.** The first version of the probe used GET and
got `404 {"error":"Not found."}` with and without the credential. That route does
not exist, so the probe never reached the auth layer at all. A 404 that is
identical with and without a token is not evidence about the token. Read what
the status code actually means before drawing a conclusion from a matched pair.
