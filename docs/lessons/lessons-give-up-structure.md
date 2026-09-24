# Lessons: a call-ending edge needs a structural guard, not a prompt clause

Learned 2026-09-16 building step 5b on a second example agent (`transforms/b_repeat_rule_give_up.py`).

## 1. An exclusion clause in an edge prompt still misfires

The give-up edge on `Guardrail Refusals` had to end the call only for a stuck
caller who gave no name and no callback number (Rey's option B). Four drafts,
same test pair, `gpt-4.1`:

| Draft | Where the name-or-number test lived | T-RP (caller gives nothing) | T-RP-C (caller gave name and number) |
|---|---|---|---|
| v1 | not at all | 4 of 4, but closed after two DIFFERENT questions on 3 | not run |
| v2 | not at all, "SAME item" wording | 4 of 4 | closed the caller, rep 1 |
| v3 | in the edge prompt: "only when the caller has not given a name or a callback number" | 4 of 4 | 3 of 4; rep 2 closed a caller who gave name and number two turns earlier |
| v4, v5 | extract node `Give-up Check` + branch `Give-up Router` | 6 of 6 | 6 of 6; the edge fired 5 times, the branch sent all 5 back to intake |

**Wrong before:** writing the condition that protects a real customer into the
edge prompt, with "Do NOT take it if...". It held 3 of 4. One in four is a hung-up
customer.

**Rule:** when an edge can end a call, put the "is this caller worth keeping"
test in structure: an extract node that answers it as an enum, then a branch
equation. Let the edge prompt only say when the caller is stuck. Same shape as
`Call Type Check` -> `Call Type Router`. This is root `CLAUDE.md` hard rule 10,
measured. See also lesson 6 in `docs/lessons-v24-simplification.md`.

**Test that proves it:** a control trace where the edge SHOULD fire but the
branch must send the caller back (T-RP-C). Check the node hops, not only
PASS: `Give-up Router -> Gate Pass Counter`.

## 2. Extract variables must be declared, or `flowlint.py` flags them

`flowlint.py` counts only code nodes as variable writers. Every extract
variable in this flow (`call_type`, `cap_name`, ...) is declared in
`default_dynamic_variables` with a default. A new extract variable without a
declaration shows "read but never written or declared".

**Rule:** a transform that adds an extract variable also adds it to
`default_dynamic_variables`, with a default that is the safe branch outcome if
the extract never writes. Here `giveup_has_contact: "no"`: the stuck caller
closes, which is the case the step was built for.

## 3. A trace can be wrong about which question is "the same"

T-RP-C's first version assumed each question would be asked once. The flow asked
"What kind of service do you need help with?" and then the guardrail asked the
vehicle question: the same item twice, by the rule. The control then expected the
wrong thing under a literal repeat rule. Read the walked transcript before
deciding whether the flow or the trace is wrong (lesson 8 in
`docs/lessons-v24-simplification.md`).
