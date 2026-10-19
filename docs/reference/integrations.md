# Integration notes: n8n, Make, Modal, GHL, Zapier, HubSpot, Cal.com, Twilio

## Accounts

Every key below can exist once per account, as `KEY__<ACCOUNT>` in the kit
`.env`. The selector `<SERVICE>_ACCOUNT` picks one (kit/accounts.py). A
client's `.env.local` holds its selectors: `python tools/accounts.py use
--client <name> n8n=<account>`. Confirm the active account before any write:
a correct change in the wrong account is still a wrong change.

| Platform | Kit tool | MCP |
|---|---|---|
| Retell | `kit/*.py`, `tools/*.py` | `tools/mcpgen.py retell=<acct>` |
| n8n | `kit/n8nkit.py` | claude.ai connector (one instance), or `mcpgen.py n8n=<acct>` |
| Make | `kit/makekit.py` | claude.ai connector (one org), or `mcpgen.py make=<acct>` |
| Modal | `kit/modalkit.py` | none |

See `mcp/README.md` for which account each connector reaches.

## The one fact every integration shares

`webhook_url` and `webhook_events` live on the Retell **agent**, not the
flow or the prompt. No flow lint, no sandbox trace, no prompt check can
see whether they are set. Run `delivery-check` after every publish and
after any edit made in the Retell dashboard, which is where the setting
is most often lost by accident.

## n8n

- Public API: `N8N_BASE_URL`, `N8N_API_KEY`. Pull the live workflow before
  trusting any saved snapshot: `python kit/n8nkit.py pull <id> --client <name>`.
- Before go-live, walk `docs/reference/n8n-production-checklist.md`.
- A PUT to an active workflow can reach the next real execution.
  `n8nkit.py push` refuses an active workflow without `--live-ok`.
- A credential (an auth token, a header secret) is never visible through
  the workflow API. Test it live with a throwaway probe, never by reading
  JSON.
- Anchor any code-node edit on a literal string that appears exactly once
  in that node, and refuse to apply if it does not. See `edit-integration`.

## Make

- `MAKE_API_TOKEN`, `MAKE_ZONE` (e.g. `us1.make.com`), `MAKE_TEAM_ID`.
  Tool: `kit/makekit.py`.
- A scenario's modules are the equivalent of n8n's nodes. Read a
  scenario's execution history the same way you would read an n8n
  execution: which modules ran, what each one received.
- The blueprint is the scenario's JSON. `makekit.py push` sends it back as a
  string inside `PATCH /scenarios/{id}`. Make may reformat metadata on save,
  so diff the after-snapshot rather than trusting a byte match.
- Free plans: about 1,000 operations a month and 30 API calls a minute.

## Modal

- `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`, optional `MODAL_ENVIRONMENT`.
  Tool: `kit/modalkit.py`, which wraps the `modal` CLI (`pip install modal`).
- Use it for a webhook receiver or a custom-function endpoint written in
  Python. Template: `templates/integrations/modal/retell_app.py`. It
  verifies `x-retell-signature` against the raw body with the Retell SDK.
- `serve` gives a temporary URL that dies with the process. Point an agent
  only at a `deploy` URL.
- Compute is billed per second while a function runs.

## GoHighLevel (GHL)

- `GHL_API_KEY` (a private integration token, not the legacy API key),
  `GHL_LOCATION_ID`.
- Workflows and custom fields live under one location. Confirm the
  agent's post-call fields map onto the exact custom field the client's
  GHL workflow reads.

## Zapier

- `ZAPIER_WEBHOOK_URL`. A "Webhooks by Zapier" trigger has no execution
  API on most plans, so read the Zap's run history in the dashboard, or
  replay a saved payload against a mock endpoint with
  `tools/webhookreplay.py --url`.

## HubSpot

- `HUBSPOT_PRIVATE_APP_TOKEN`. Map post-call fields onto HubSpot contact
  or deal properties; confirm the property exists before assuming a
  write will succeed.

## Cal.com and Google Calendar

- `CALCOM_API_KEY` for Cal.com booking.
- `GOOGLE_CALENDAR_CREDENTIALS_PATH` points at a service-account JSON
  file kept outside both repos. Never commit that file.
- Confirm the agent's timezone setting matches the calendar's, or a
  booking can land on the wrong day.

## Twilio

- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`. Needed when a number is
  bought or managed through Twilio and connected to Retell by SIP trunk,
  rather than bought directly through Retell.

## Testing any of the above offline

Use `sandbox/mock-webhook/receiver.py` to receive a real payload shape
with no live workflow behind it, before wiring a client's real endpoint.
