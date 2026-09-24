# A trace block cannot see a variable, so a GREEN run can hide a moved payload

2026-09-19. a second example agent, live v48 / draft v49. Building the client's item 4, the split
of the missing reason into Not captured, Caller doesn't know and Declined.

Read this before testing any change that touches an `extract_dynamic_variables`
node or a code node.

---

## Lesson 62 - `expect_path`, `forbid_path` and `say_times` say nothing about what the call reports

### What was built

The obvious build. The seven `cap_*` descriptions on `Capture Check` and
`Capture Check (Close)` each define one bucket called `missing`. the client wants
three reasons, so split that one word into `not_captured`, `does_not_know` and
`declined`, and let the code node put all three on the missing list exactly as
before. `missing_fields` still gets the same fields. Descriptive only, as asked.

Offline it looked perfect. Lint matched the baseline. Four nodes changed and no
others. The inverse round-tripped byte-identical. The old and new code node were
run side by side in node on nine inputs and `missing_fields` came out identical
on all nine.

### What the sandbox said

T-U, two reps, `gpt-4.1-mini`, against the unchanged v49 as the baseline.

    baseline  PASS 2/2    VERDICT: GREEN
    candidate PASS 2/2    VERDICT: GREEN

Both green. Every rule in the checklist was satisfied. The change was ready to
push.

### What the sandbox actually showed, in a line nobody has to read

`tracerun.py` prints the collected dynamic variables under the verdict. It is
not part of the pass or fail. Side by side:

| | baseline | candidate |
|---|---|---|
| `cap_name` | `unclear` | `declined` |
| `cap_callback` | `unclear` | `declined` |
| `missing_fields` | 5 fields | **7 fields** |
| `uncertain_fields` | 2 fields | **empty** |

The nine-input harness could not catch it, because the harness feeds the code
node fixed inputs. The thing that moved was what the MODEL puts into those
inputs, and only a real run produces that.

### Why it moved

Today's description says `missing` covers a caller who "refused, or said they
did not know", and then the very next sentence says "A reply that fails to
answer the question is still a reply, so it is unclear, not missing." A refusal
is a reply. The second sentence wins, so a refusal lands in `uncertain_fields`
today. Give `declined` its own bucket and it stops losing that argument.

`incomplete_intake` has been read off the flow's own missing list since
2026-09-17, and it is true when the name or the callback number is on it. So a
caller who simply declined to give a name would have started arriving at the downstream owner
as an incomplete intake. That is the one gate the client named in writing as the
gate that must not move.

### The rule

**A trace block asserts a path and some sentences. It asserts nothing about a
variable. A change that alters what a payload reports can be GREEN on every
trace in `tests/TRACES.md`.**

So, for any change touching an extract node or a code node:

1. Run the trace on the baseline and on the candidate, and **diff the `vars`
   line**, not the verdict. The verdict is not the measurement here.
2. Run it at least three times on each. See below.
3. An offline harness over a code node proves the code. It cannot prove what
   the model will feed the code. Both are needed and neither substitutes.

### Also measured, and it is a live defect in its own right

Three separate one-rep T-U runs on the **unchanged** v49:

    run 1  cap_name unclear    run 2  cap_name missing    run 3  cap_name unclear

The live agent flaps. A caller who refuses their name and number lands in
`uncertain_fields` about two times in three and in `missing_fields` about one
time in three. Since `incomplete_intake` comes off that list, **a refusing
caller already reaches the downstream owner as an incomplete intake roughly one call in
three.** Nothing this session caused it. It is not yet raised with the client or
the downstream owner.

Two reps would have called the candidate's 7-field result "the change" and the
baseline's 5-field result "the baseline". Three reps on each showed the same
distribution on both, which is what proved the rebuilt version safe. **On a
prompt-judged value, two runs is a coin, not a measurement.**

### The build that is safe, and why it is safe differently

The reason now rides on its own variable, `cap_reasons`, and the seven `cap_*`
descriptions are byte-identical to v49. The bucket decision cannot move because
nothing that feeds it changed. That is a guarantee from the shape, not a result
from a sample, and it is the only kind worth having on a field somebody's
business rules read.

Compare `docs/lessons-green-verdict-blindness.md`, which is the same shape of
mistake about spoken behaviour rather than reported values.

### The gap

`tests/TRACES.md` has no way to assert a variable. There is no `expect_vars`.
Every trace that cares about a payload is checked by a human reading a printed
dict, which is exactly how this nearly shipped. Naming it here rather than
building it: it is a `tracerun.py` change and nobody has asked for one.
