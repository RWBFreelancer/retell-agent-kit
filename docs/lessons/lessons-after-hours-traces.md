# Lessons: testing after-hours behaviour in a text sandbox

Learned 2026-09-15 while testing `transforms/b_after_hours_wording.py` on a second example agent v42.

## 1. The sandbox reads the real clock

Both agents pick Open or Closed wording from `Now: {{current_time_America/Los_Angeles}}`
in the global prompt. `tracerun.py` has no option to set the time. A trace run
at 4:57 PM Pacific on a Monday gets open-hours wording, whatever the trace means
to test.

**Wrong before:** nothing. No after-hours trace existed, so no run was ever
pinned to closed hours.

**Rule:** for any Open/Closed test, build local copies with the `Now:` line
replaced by a fixed time, one closed and one open, for BOTH the baseline and the
candidate. Run the same trace on each. Never push a clock-fixed copy.

Used: `Now: Monday, September 14, 2026, 9:40 PM Pacific` (closed) and
`Now: Tuesday, September 15, 2026, 10:00 AM Pacific` (open). Traces T-AH-U,
T-AH-P, T-AH-T, T-AH-O in `tests/TRACES.md` say which copy they need.

## 2. "ASAP" as the answer to the urgency question fires Guardrail Refusals only some of the time

The `Guardrail Refusals` condition says to trigger on "ASAP" (case e) AND says
not to trigger for "a caller answering an intake question". "ASAP" answering
"How soon do you need help with the repair?" is both. The model picks either.

Evidence, `gpt-4.1`, unchanged v42: fired 1 of 2 closed, 1 of 2 open.
Candidate: 0 of 4 closed, 1 of 4 open. On a real call it fired:
`call_xxxxxxxxxxxxxxxxxxxxxxxxxxx` (v41), 9:40 PM, "ASAP" to the urgency question.

**Rule:** do not test case (e) with only "ASAP" as the urgency answer. The
result is a coin flip, not the change. Test a caller who ASKS for someone now
(T-AH-T fired 4 of 4 and 2 of 2). If the urgency answer path matters, fix the
conflict in the condition itself, as its own change.

## 3. The Add Detail double-say shows up in these traces

When the caller gives a missing item as the answer to "Anything else I should
include?", `Add Detail` can say "Thank you, I'll add that to the request." and
the goodbye twice. Seen on baseline T-AH-T rep 1 and candidate reps 2 and 3.
Pre-existing. Belongs to step 5 (the loop after a global node returns). Do not
read it as a regression of a wording change.
