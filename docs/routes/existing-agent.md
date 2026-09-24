# Route: existing agent — check, test, or modify

Ask which of the three this session needs, if it is not already clear.

## Check only

1. Run `check-agent-info`. Pull the live version. Never trust a version
   number written in a file.
2. Run `check-agent-data` if the question involves real calls.
3. Report what you found, with the version every number came from.

## Test

1. Run `check-agent-info` first, to know what you are testing.
2. Run `test-flow` or `test-single-prompt`, matching the agent's type.
3. State the cost before any sandbox run. See `cost-gate`.
4. Run the unchanged baseline next to anything you are comparing. A red
   only counts if the baseline is green.
5. Log the result with `log-results`.

## Modify

Run `edit-agent`. Its nine steps:

1. Snapshot the flow or prompt, and the agent settings, separately.
2. Check for drift against the last known copy in the repo.
3. Design the smallest change. Trace current behavior first.
4. Edit a local copy. Never in place.
5. Lint.
6. Test what it says, on a throwaway sandbox.
7. Name the reversal route, then get approval for the draft write.
8. Push the draft. Dry run first, always.
9. Confirm what landed with a fresh pull and a diff. This step is the
   whole point.

Never publish from this route. Publishing needs the `publish` skill and
the ladder in `AGENTS.md` section 7.

## Downstream integration involved?

Use `check-integration` and `edit-integration` alongside the steps above,
for any change that touches what a downstream system receives.
