---
name: test-environments
description: Checklist for creating throwaway test environments and clearing them afterwards - Retell trace runs and chat sandboxes, simulation tests, throwaway integration workflows and probes, code-node harnesses, and where raw results go. Use before running any test that creates something outside the client folder, and at the end of any session that ran tests.
---

# Test environments

Anything you create outside the client folder, you delete before you
finish.

## Retell

Point everything at `sandbox/`. See `sandbox/README.md`.

| Environment | Create | Clear |
|---|---|---|
| Trace run | `python $K/sandbox/run.py --client <name> --agent <slug> --file <export> --trace T-X` | Tears itself down. Confirm "Sandboxes torn down" in the output |
| Chat sandbox | `python $K/kit/retell_chat.py` (via `sandbox/run.py`) | `python $K/sandbox/cleanup.py`. Always, after any crash |
| Simulation test | Blocked by default. It runs the flow's own live model, which the cost gate has not cleared. Only run it after the client says yes to that specific cost |

- [ ] Test a **local export** with `--file`, never the live flow or prompt.
- [ ] Tests run on the cheapest model in `sandbox/config.json` by default.
  Never change `model_choice` in a transform just to make a test cheaper;
  that changes what real callers get.
- [ ] Every sandbox run is billed by Retell, even on a local export.
  "Local" means the flow copy, not the cost. State the estimated cost
  before a run and ask before a large one. See `cost-gate`.
- [ ] The sandbox can swallow turn 1 into the greeting. Start every
  scripted trace with a filler turn.

## Integration platform (n8n, Make, GHL, Zapier)

- [ ] Name throwaway workflows `ZZ TEMP - <purpose> - DELETE ME`, and
  delete them in a `finally` block.
- [ ] Use a unique webhook path per run.
- [ ] A probe must write nothing real. Send a test endpoint an empty body
  `{}`. A real payload can create a real record in the client's CRM.
- [ ] Never print a credential value. Report header names only.
- [ ] At the end, run the tool's `--cleanup` and confirm "nothing left
  over".

## Code-node harness

- [ ] Build it in the session scratchpad, not the repo.
- [ ] Feed it a real payload saved from an execution.
- [ ] Delete scratch files you will not reuse.

## Results

- [ ] Raw output (JSON dumps, trace logs, harness output) goes to
  `<client>/results/`. It is git-ignored. Clear it any time.
- [ ] Anything you will quote or decide on goes in
  `<client>/docs/test-log.md`. See `log-results`.
- [ ] Never leave test output in a docs file meant to be kept.

## Before you finish a session

- [ ] `python $K/sandbox/cleanup.py --client <name>` is clean.
- [ ] Any credential probe reports nothing left over.
- [ ] No `ZZ TEMP` workflow remains on the integration platform.
