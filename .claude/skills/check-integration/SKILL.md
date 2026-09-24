---
name: check-integration
description: Checklist for reading a client's post-call integration workflow and its executions - pulling the live workflow, reading one execution node by node, finding which nodes ran, reading a code node's input and output, and tracing why a call got a label, an email, or a handoff refusal. Covers n8n first, with stubs for Make, GoHighLevel, and Zapier. Use when given an execution id, when asked why a call got a status, about a recap email, or about a handoff failure or alert.
---

# Check integration

Read the client's `CLIENT.md` for which platform this client uses, and its
workflow id or scenario id.

## n8n

`N8N_BASE_URL` and `N8N_API_KEY` come from `.env`. The workflow id lives in
the client's `AGENT.md` or `CLIENT.md`, never hard-coded here.

- [ ] **Pull the live workflow. Never trust a snapshot.** `GET /api/v1/workflows/<id>`. Note `updatedAt` and the node count.
- [ ] **Read one execution with its data.** `GET /api/v1/executions/<id>?includeData=true`. Save the raw output to `<client>/results/`, never to a docs file.
- [ ] **List which nodes ran.** The keys of `data.resultData.runData`. A 200 from the webhook means queued, not processed. A dropped call can end `success` after two nodes.
- [ ] **Read the input, not only the output.** Find the node that receives the raw Retell `call_analyzed` payload and read its `data.main[0][0].json.body.call`. Analysis fields are under `call_analysis.custom_analysis_data`.
- [ ] **Walk each decision in order.** For a label or a routing choice, read the code that set it, then the exact values it read. Quote line numbers.
- [ ] **When a phone number matters, check both numbers.** See `check-agent-data`.
- [ ] **Say who ended the call** from the Retell body and node state, not the transcript. See `check-agent-data`.

## Auth failures

- A downstream token is usually **not** in the workflow JSON. It lives in a
  credential object no snapshot or diff can see.
- n8n never returns a credential value. Test connectivity with a probe that
  runs a few checks and deletes itself. Report header names only, never a
  value.

## Make, GoHighLevel, Zapier

Stubs. Extend these as a client needs them.

- **Make**: pull a scenario with `MAKE_API_TOKEN`, `MAKE_ZONE`,
  `MAKE_TEAM_ID`. Read its execution history the same way: which modules
  ran, what each module received.
- **GoHighLevel**: workflows and their triggers live under the location
  set by `GHL_LOCATION_ID`. Check the custom field mapping that receives
  each Retell analysis field.
- **Zapier**: a Zap fed by `ZAPIER_WEBHOOK_URL` has no execution API in
  the free tier. Read the Zap history in the dashboard, or replay a saved
  payload with `webhookreplay.py` against a mock endpoint.

## Traps

- Before firing a replay, walk every early guard or idempotency check
  between the webhook and the node you care about.
- Fixture or pinned test data can be missing fields a real call always
  has, such as `from_number`. A green run on a fixture proves nothing
  about phone routing.
- Two branches fed by the same trigger do not automatically share values.
  Check whether each branch reads the raw Retell payload or a value some
  earlier node computed. A fix to one does not reach the other.
