# Integration notes: n8n, Make, GHL, Zapier, HubSpot, Cal.com, Twilio

## The one fact every integration shares

`webhook_url` and `webhook_events` live on the Retell **agent**, not the
flow or the prompt. No flow lint, no sandbox trace, no prompt check can
see whether they are set. Run `delivery-check` after every publish and
after any edit made in the Retell dashboard, which is where the setting
is most often lost by accident.

## n8n

- Public API: `N8N_BASE_URL`, `N8N_API_KEY`. Pull the live workflow before
  trusting any saved snapshot.
- A credential (an auth token, a header secret) is never visible through
  the workflow API. Test it live with a throwaway probe, never by reading
  JSON.
- Anchor any code-node edit on a literal string that appears exactly once
  in that node, and refuse to apply if it does not. See `edit-integration`.

## Make

- `MAKE_API_TOKEN`, `MAKE_ZONE` (e.g. `us1.make.com`), `MAKE_TEAM_ID`.
- A scenario's modules are the equivalent of n8n's nodes. Read a
  scenario's execution history the same way you would read an n8n
  execution: which modules ran, what each one received.

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
