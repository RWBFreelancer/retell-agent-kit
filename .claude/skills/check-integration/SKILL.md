---
name: check-integration
description: Checklist for reading a client's post-call integration workflow and its executions - pulling the live workflow, reading one execution node by node, finding which nodes ran, reading a code node's input and output, and tracing why a call got a label, an email, or a handoff refusal. Covers n8n, Make, and Modal, with stubs for GoHighLevel and Zapier. Account-aware. Use when given an execution id, when asked why a call got a status, about a recap email, or about a handoff failure or alert.
---

# Check integration

Read the client's `CLIENT.md` for which platform this client uses, and its
workflow id or scenario id.

**First, the account.** Run `python tools/accounts.py list --client <name>`
and confirm the active n8n, Make, or Modal account is this client's. Every
command below reaches whichever account is active. Run them from the client
folder, or prefix a one-off selector (`$env:N8N_ACCOUNT='acme'` in
PowerShell).

## n8n

Tool: `kit/n8nkit.py`. Keys: `N8N_BASE_URL__<ACCT>`, `N8N_API_KEY__<ACCT>`.
The workflow id lives in the client's `AGENT.md` or `CLIENT.md`, never
hard-coded here. The claude.ai n8n connector reaches one instance only; see
`mcp/README.md`.

```bash
python kit/n8nkit.py workflows --name recap
python kit/n8nkit.py pull <workflow-id> --client <name>
python kit/n8nkit.py show <snapshot> list
python kit/n8nkit.py show <snapshot> code "Build Payload"
python kit/n8nkit.py executions <workflow-id> --errors
python kit/n8nkit.py execution <execution-id> --node "Webhook" --save --client <name>
python kit/n8nkit.py lint <snapshot>
```

- [ ] **Pull the live workflow. Never trust a snapshot.** `pull` prints `updatedAt` and the node count, and saves a new numbered file.
- [ ] **Read one execution with its data.** `execution <id> --save` puts the raw output in `<client>/integrations/n8n-executions/`. It holds real call data: never copy it into a docs file.
- [ ] **List which nodes ran.** `execution` prints them in order with item counts. A 200 from the webhook means queued, not processed. A dropped call can end `success` after two nodes.
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

## Make

Tool: `kit/makekit.py`. Keys: `MAKE_API_TOKEN__<ACCT>`, `MAKE_ZONE__<ACCT>`,
`MAKE_TEAM_ID__<ACCT>`. For execution detail module by module, the claude.ai
Make connector's `executions_get-detail` is richer than the REST logs, when
the connector reaches this client's org.

```bash
python kit/makekit.py scenarios --name recap
python kit/makekit.py pull <scenario-id> --client <name>
python kit/makekit.py show <snapshot>
python kit/makekit.py logs <scenario-id>
python kit/makekit.py hooks
```

- [ ] `hooks` shows each webhook URL and its scenario. The agent's `webhook_url` must equal one of them exactly.
- [ ] A Free plan has a low operation quota. A scenario that stops mid-month may be out of operations, not broken.

## Modal

Tool: `kit/modalkit.py` (needs `pip install modal`). Keys:
`MODAL_TOKEN_ID__<ACCT>`, `MODAL_TOKEN_SECRET__<ACCT>`.

```bash
python kit/modalkit.py apps
python kit/modalkit.py logs <app-name>
```

- [ ] The agent's `webhook_url`, or a custom function's URL, must point at the deployed app's URL, not a `serve` dev URL, which dies when `serve` stops.
- [ ] A 401 from the app on every call means signature verification fails: the app's Modal secret holds a different Retell workspace's key.

## GoHighLevel, Zapier

Stubs. Extend these as a client needs them.

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
