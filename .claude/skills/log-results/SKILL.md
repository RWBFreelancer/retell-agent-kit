---
name: log-results
description: How to record test runs, measurements, and changes in one consistent format so a later session can find and trust them - the test-log row, the changelog entry, where raw output goes, and what to do when a logged result turns out wrong. Use after any trace run, real-call count, integration probe, harness run, push, apply, or publish.
---

# Log results

Each thing goes in exactly one home, inside the client folder.

| What | Where |
|---|---|
| A test run or measurement | One row in `<client>/docs/test-log.md` |
| A flow or agent change that landed | `<client>/agents/<slug>/CHANGELOG.md`, plus test-log rows for its tests |
| An integration change that landed | The apply tool's docstring, plus a test-log row |
| Something a future session must know | A lesson, via `record-lesson` |
| Raw output | `<client>/results/`, git-ignored |

## Test-log row

Append to the table in `<client>/docs/test-log.md`. Newest at the bottom.

| Column | Rule |
|---|---|
| Date | `YYYY-MM-DD` |
| Target | Agent and version (`intake-agent v39 draft`), or workflow and `updatedAt`, or a call set (`calls v35+ n=56`) |
| What | Trace ids, the count, or the probe. One line |
| Model | The exact model name, or `n/a` |
| Result | PASS, FAIL, or the number. Include the baseline result if one was run |
| Cost | Retell billed cents, or `0` |
| Evidence | The tool, a file in `<client>/results/`, or the changelog entry |

- [ ] One row per run. Never edit an old row's result.
- [ ] If a result turns out wrong, add a new row that says so and names
  the old one. Keep the old row.
- [ ] Log the baseline run next to the candidate run.
- [ ] For a real-call count, put the schema window in Target.

## Changelog entry

Use the template at the bottom of `<client>/agents/<slug>/CHANGELOG.md`.
Fill every field. `unknown` is fine. Empty is not. Newest first.

Name the transform or tool, both export snapshots, the tests and their
results, the cost, and the reversal route. State the status plainly, for
example `PUSHED TO DRAFT, NOT PUBLISHED`.

## Rules

- No caller names, numbers, or addresses, in either repo. Call ids only,
  and only in `retell-clients`.
- Never log a result you did not run. "Not tested" is a valid result.
- `exports/` is read-only history. Never write to a file already there;
  make a new one.
