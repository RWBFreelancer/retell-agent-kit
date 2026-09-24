# sandbox/

A sandbox is a throwaway copy of a flow or a chat agent, used to test
behavior over text without touching a live agent. See `docs/reference/retell-platform.md`
for why a copy is needed instead of talking to the real flow.

## What it costs

Every sandbox run is billed by Retell, even though it never touches the
production flow. It is "local" in the sense that it never touches
production, not in the sense that it is free. Run `cost-gate` before any
sandbox run, and state the estimate first.

## What is in here

| File | Purpose |
|---|---|
| `config.json` | `test_models`, cheapest first, and `max_reps_default`. The one place the model policy lives |
| `run.py` | Runs `<client>/tests/TRACES.md` against a flow in a throwaway sandbox. Thin wrapper over `tools/tracerun.py` |
| `cleanup.py` | Deletes any leftover throwaway agents and flows. Thin wrapper over `tools/retell_chat.py cleanup` |
| `mock-webhook/` | A local HTTP receiver that saves a posted payload to `results/`, for testing an integration with no real n8n, Make, or GHL workflow |

## Cleanup

Every sandbox object is named with the prefix `zz-sandbox-`. `cleanup.py`
matches only that prefix, so it can never delete something it did not
create. Run it at the end of every session that ran a sandbox test, and
always after a crash.

## Model policy

`config.json` lists the only models a sandbox may run, cheapest first.
`tools/retell_chat.py` and `tools/tracerun.py` both read this file and
refuse any other model. Never edit a flow's own `model_choice` to make a
test cheaper; that changes what real callers get. Widen the list only with
the client's OK for the added cost.
