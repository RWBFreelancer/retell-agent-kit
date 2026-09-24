---
name: cost-gate
description: Estimates the cost of a billed action and asks the client or Rey to continue before it runs. Every billed tool calls this first. Use before any sandbox run, trace run, simulation, live call, or other action that costs money.
---

# Cost gate

State the cost. Ask. Every time, until told otherwise in `CLIENT.md`.

## Steps

1. **Name the action.** What runs, on which model, how many turns or
   reps.
2. **State the estimate.** Use the per-minute or per-message price from
   `$K/docs/reference/model-choice.md`. Say the number, not "a small
   amount".
3. **Ask to continue.** Use `AskUserQuestion` when interactive, or
   otherwise state the estimate and wait for an explicit go-ahead before
   the billed call runs.
4. **Cheapest model first.** Use the first entry in
   `$K/sandbox/config.json` `test_models` unless the client already named
   a different one for this agent.
5. **If the cheap model fails**, do not silently retry on a stronger one.
   Report the failure, recommend the next model up with the reason and
   the new cost, and wait for the OK before running it.

## What is billed

Every Retell sandbox run, even against a local export. A trace run, a
chat sandbox turn, a simulation, and any real call all cost money. Lint
and diff tools do not; they read local files only.

## Refuse, don't guess

If `sandbox/run.py` or another billed tool is called without a prior
go-ahead in this session, stop and run this skill first. A go-ahead for
one action does not cover the next one.
