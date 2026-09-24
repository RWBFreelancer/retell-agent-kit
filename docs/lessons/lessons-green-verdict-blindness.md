# The green verdict that hid a worse defect

2026-08-31. a second example agent, live v30 / draft v31.

## What happened

The handoff named one open defect on the live agent: `T-AH` failing 0 of 5, the
closing line "Anything else I should include?" asked twice. The plan was to
reproduce it, diagnose it, build two candidate fixes and let the measurement
pick the winner.

The reproduction run came back **PASS 3 of 3**.

Two things were true at once, and both mattered more than the original ticket.

## One: the defect in the handoff did not reproduce

`flowpull.py --agent b --suffix drift` gave v31. It is **byte-identical** to
`v31-handoff.json`, and `flowdiff.py` against `v30-published.json` reports
changes only to `version`, `is_published` and `last_modification_timestamp`.
So the flow measured at 0 of 5 and the flow measured at 3 of 3 are the same
flow. Whatever produced "0 of 5" was not this trace against this export.

The lesson is not "the previous session was careless". It is that **a failure
count copied into a handoff is a claim, not evidence**, and it decays the moment
anyone cannot say exactly which object it was measured against. Record the
export filename and the command line beside every count, or the next session
spends money re-deriving it.

## Two: the passing trace was hiding a much worse defect

`T-AH` asserts three sentence counts:

    "Anything else I should include?"                          : 1
    "The team will review the information"                     : 0
    "Can we text you at that number regarding your service..."  : 1

All three were satisfied. The transcript underneath them, read with `--verbose`:

The caller asks a pricing question at `Text Permission`, with the vehicle, the
problem, the location and the urgency all still unasked. `Guardrail Refusals`
fires, answers, and appends its closing question. On the caller's next turn the
agent runs `Capture Check (Close) -> Recap Lists (Close) -> Sign-off & Goodbye`
and says goodbye. **The intake is over, four questions early.**

The caller then volunteers everything that was never asked — the van, the fault,
the full address, the timing — and every one of those turns produces:

    AGENT   Thank you, I'll add that to the request.
    AGENT   OK, thank you. I'll end the call now. Take care.

The goodbye is spoken **five times**. No assertion in the trace mentions the
goodbye, so the trace is green.

Confirmed on a real production call the same day, reached through a different
door: `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`, v30, 98 seconds, ending with
`missing_fields` listing five items and `successful: True`. Full detail in
a saved audit of the calls that showed this pattern.

## The general rule

**A green verdict is only as wide as its assertions.** `say_times` counts the
sentences the trace author thought to list. Everything else is unmeasured.

A red trace gets investigated. A green one closes the ticket. That asymmetry is
what makes this failure mode worse than an outright failure.

So, in order of how much they cost to adopt:

1. **Read one passing transcript per change.** `--verbose` already prints it.
   The verdict describes the assertions; only the transcript describes the call.
2. **Assert the lines a defect would ADD**, not only the line you are
   protecting. Closing and sign-off lines get a count in every trace that
   reaches the close. A repeated goodbye is the cheapest available symptom of a
   routing loop.
3. **Assert completeness, not just wording.** A trace that walks an intake
   should assert that every question was asked. `say_times` on each question
   sentence does it for free.
4. **A trace inherited from an old defect is scoped to that defect.** It does not
   become a general regression test by passing.

## Three: the verdict named a trace it never ran

Same day, worse. A new trace reproducing a real call was added as `T-AK`. That
id was already in use by a 2026-08-26 trace further down `tests/TRACES.md`.

`tracerun.load_traces` builds a dict in file order:

```python
out[t["id"]] = t
```

so the LATER block silently replaced the earlier one. The runner then printed

    T-AK   PASS  8/8

while executing the pre-existing "two-place location answer" trace. The
existing-customer scenario was never run, at either 3 reps or 5.

That number was reported to Rey as evidence the defect was already fixed, and a
built, working transform was shelved on the strength of it. Both had to be
retracted.

**Two things make this worse than an ordinary wrong result.** The verdict was
green, so nothing invited a second look; and it named the id that was asked for,
so even reading the output carefully could not reveal the substitution. Only the
turn count in the transcript would have given it away, and a passing run's
transcript is exactly the one nobody reads - which is lesson one of this file,
biting a second time in one session.

**Fixed in the tool, not in the habit.** `tracerun.py` now refuses to load a
file containing duplicate ids, with a message that says why. A convention that
depends on remembering is not a convention.

The general rule: **when a test harness keys anything by a name, make collisions
an error.** Silent last-write-wins in a test loader does not lose a test, it
substitutes one, and reports the result under the name you trusted.

## The structural half

The routing fault the transcript exposed is written up as anti-patterns 21 and
22 in the flow standard:

- A closing chain gated on repetition (`closing_passes > 1`) but never on
  completeness.
- An unconditional `else_edge` pointed at a terminal chain. From a global node,
  which any turn can enter, that is an unconditional hang-up wearing a
  catch-all's clothes.

And the trap waiting for the obvious fix: the `cap_*` variables that would drive
a completeness gate are populated by an extract node that runs **after** the
router that would read them. An equation written against them today reads the
default `"missing"` on every call, including the good ones. Check that a
variable is set before the branch that reads it — added as QA check B17.

## Checklist lines added

`qa-checklist.md`: B15, B16, B17, I13, I14.

---

## A postscript, 2026-09-03: the trace that passed because it asserted nothing

`T-CU` was written to prove one thing: that a garbled reply now yields
`cap_urgency: unclear` instead of `missing`. Its subject is a VARIABLE, so it
was written with `expect_path: []`, `forbid_path: []` and `say_times: {}`.

It returned **PASS 1/1**, and `VERDICT: GREEN`.

That verdict was worth nothing. A trace with no assertions cannot fail. The
runner only printed the collected variables on a FAILING rep, so the one fact
the trace existed to establish was the one fact never shown.

`tracerun.py` now prints the path walked and the collected variables on every
run, pass or fail. With that, the same trace reported what it was built to
report:

    cap_urgency      : unclear
    uncertain_fields : urgency
    missing_fields   : ""

**The general rule.** Before trusting a green verdict, ask what assertion would
have had to fail. If you cannot name one, the run proved nothing. This is the
same lesson as the body of this file, arriving from the other direction: there
the assertions were real but too narrow, here there were none at all and the
harness still said GREEN.

**And the narrower rule.** A trace whose subject is a variable needs the
variable printed. Assertions on `say_times` cannot reach it, so read the `vars`
line and compare it against the values from the real call the trace reproduces.

Checklist line added: I16.

---

## A renamed node leaves a trace permanently red, and nobody looks again

Found 2026-09-04, on `T-AO`.

`T-AO` asserted `expect_path: ["Sign-off (Incomplete)"]`. That node was renamed
by `transforms/b_v24_rebuild.py` on 2026-08-24. The remap table at the top of
`tests/TRACES.md` lists nine renames and misses this one.

So from 2026-08-24 to 2026-09-04, `T-AO` reported:

    never reached node 'Sign-off (Incomplete)'

on every run, before and after every change. The trace could not pass on any
flow that existed. Its `say_times` line was wrong too: it counted the
`Sign-off & Goodbye` sentence on a path that ends at `Incomplete Intake Exit`,
which speaks a different sentence.

Nobody noticed for eleven days, because a red trace that is *always* red stops
carrying information. It became background noise, and every real run since was
read as "T-AO fails, it always does".

**The rule.** A permanently failing trace is worse than no trace. It is a guard
that stopped guarding while still looking like one. When a trace reports "never
reached node X", check that X exists in the flow BEFORE investigating the flow:

    python -c "import json;print([n['name'] for n in json.load(open('agents/agent-b/exports/vNN.json'))['nodes']])"

**The second rule.** A rename is a change to `tests/TRACES.md`, not only to the
flow. When a transform renames a node, grep every `expect_path`, `forbid_path`
and `say_times` for the old name and for the old sentence, in the same commit.
`flowlint` reads the flow, not the traces, so nothing catches this for you.

---

## A third face of it, 2026-09-05. GREEN because the sentences were never reached.

`T-AL` at 5 reps, `--model gpt-4.1`, run against both live drafts in the same
hour. Two verdicts, and the verdicts are backwards.

| | one example agent v53 | a second example agent v38 |
|---|---|---|
| verdict | **RED 3 of 5** | **GREEN 5 of 5** |
| last node reached | `End Call` | `Service Intake` |
| variables captured | all seven `cap_*` given | none |

`T-AL` asserts six sentence counts and nothing else: `expect_path` and
`forbid_path` are both empty. a second example agent satisfied every count because in nine
caller turns it never left the intake. It never said the closing question, so
the closing question was not said twice. It never read anything back, so it
read nothing back wrongly. A call that collapsed scored a clean pass.

one example agent finished the whole call, captured every field, and leaked two readbacks
doing it. The agent that did the job got the red mark.

**The rule.** A `say_times` count measures sentences NOT said just as happily
when the call never arrived at them. Any trace whose subject is a spoken
sentence must ALSO assert the node the call ended on. One line does it:

    "expect_path": ["Sign-off & Goodbye"]

Without it the runner cannot tell "said it correctly once" from "hung up before
reaching it", and it prints GREEN for both.

**The second rule.** Read the `path walked` line before the verdict line, every
time. `tracerun.py` prints it on every run. It is one line above the count that
everyone reads, and on this run it was the only thing that showed the truth.

## The mirror image, same day

A trace can also be too pessimistic. On 2026-09-05 `T-IE-A` reported a routing
defect 7 times in 8 that real calls showed 3 times in 142. Recorded in
[lessons-sandbox-route-divergence.md](lessons-sandbox-route-divergence.md).

One rule, two faces. **A trace measures exactly what it asserts, on exactly the
input it sends.** Assert more than you think you need, and check the input
against a real call before believing what the assertion tells you.


## A third blind spot, found 2026-09-08: one node, entered twice

`flowlint.py --line "<sentence>"` is the tool this repository uses to prove a
sentence cannot be said twice. Run against a second example agent v38 on the line the audit
had already caught being said twice on two live calls, it reported:

    DOUBLE-SAY CHECK: Let me get that written down....
       no path between two sayers
       0 unguarded of 0 paths

That output is correct and it is useless. The check looks for a path from one
sayer node to a DIFFERENT sayer node. `"Let me get that written down."` has
exactly one sayer, `Gate Pass Counter`. The repeat does not come from two
nodes. It comes from the flow re-entering the same node.

**The general rule.** A double-say check that counts sayers is blind to any
node that is a funnel. If a node can be entered twice on one call, it can say
its line twice, and every static-text check in this repository will still
print zero.

**How to see it instead.** `tracerun.py` prints the path walked and the
collected variables. On T-Y, the same run showed both:

    ... -> Gate Pass Counter -> ... -> Closing Line Said -> Gate Pass Counter -> ...
    vars: {'gate_passes': '2', ...}

The variable is the giveaway. `Gate Pass Counter` exists to COUNT its own
passes, so `gate_passes` reaching `2` is the flow saying out loud that it went
through a speaking node twice. **Any node whose own counter can exceed 1 must
not speak.** a second example agent's other four code nodes already carry
`speak_during_execution: false` and no instruction; this one was the odd one
out.

**Checklist line, qa-checklist.md row B6.** Do not close B6 on a clean
`--line` run. Also list every node that speaks AND has more than one inbound
edge, and say for each whether the flow can return to it.

## A second thing that run proved, about running the baseline

The same three traces were run twice on 2026-09-08: once on `v38`, once on
`v38` plus the one-field change. Both printed `T-W FAIL, T-Y FAIL, T-V PASS`,
with byte-identical `path walked` lines.

Two of the three were ALREADY failing. Had the mutated run been the only run,
those two reds would have been read as damage from the change, and a correct
one-field fix would have been thrown away.

**The rule.** Run the traces on the UNCHANGED export as well, in the same
session, and compare. A red is only evidence about a change when the baseline
is green. It costs one more run: this pair billed 20.1 cents and 22.5 cents.
