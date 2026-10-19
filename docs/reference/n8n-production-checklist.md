# n8n production checklist (for workflows a Retell agent feeds)

Ported from the `n8n-projects` repo (`resources/production-checklist.md` and
`.claude/rules/n8n-workflows.md`), with the Retell items added. Walk every
line before calling a workflow done, fixed, or safe.

`python kit/n8nkit.py lint <file>` checks the lines marked (auto).

## Retell first

- [ ] The agent's `webhook_url` equals the workflow's Production webhook URL exactly. Not the Test URL. (`delivery-check`)
- [ ] The workflow reads `body.event` and ignores events it does not handle (`call_started`, `call_ended`) instead of failing on them.
- [ ] Post-call fields are read from `body.call.call_analysis.custom_analysis_data`, by the exact names in the agent's `post_call_analysis_data`.
- [ ] Every field handles absent, `null`, `""`, and `"unknown"`. A caller who hangs up early sends almost nothing.
- [ ] Caller ID (`from_number`) and the number the caller stated are different fields. Pick the right one on purpose.
- [ ] The webhook checks `x-retell-signature`, or uses header auth. (auto notes)
- [ ] A replay of the same `call_id` makes no second email, row, or handoff. Retell retries a webhook that does not answer fast.

## Start and stop

- [ ] Exactly one clear trigger per entry point. (auto)
- [ ] No Start node. Removed in n8n 2.0. (auto)
- [ ] Schedule triggers do not run every few seconds. (auto)
- [ ] Webhook paths are unique and not easy to guess. (auto)
- [ ] The workflow ends cleanly on 0 items. Check "Always Output Data".

## Loops and sub-workflows

- [ ] Every loop has an exit. Prefer Loop Over Items. (auto)
- [ ] An IF or Switch loop has a max try count. (auto warns)
- [ ] An Execute Workflow node never calls its own workflow. (auto)
- [ ] The workflow does not trigger itself (a webhook calling its own URL, a "row added" trigger adding a row to the same sheet).

## Duplicates

- [ ] Every create, insert, append, or send step checks for an existing record first: Remove Duplicates, an upsert, or a lookup plus IF. (auto warns)
- [ ] A second run with the same input makes no new records.
- [ ] Test data was removed, or never written to live systems.

## Data

- [ ] Field names match the previous node's output. Check each node in a test run.
- [ ] Lists handle paging. Large runs batch and respect rate limits.

## Errors

- [ ] An error workflow is set, so someone is told. (auto warns)
- [ ] Calls to outside services use Retry On Fail with a wait. (auto notes)
- [ ] "On Error" is set on purpose for each risky node.
- [ ] Error messages name the failed item by id (a `call_id`, never a caller name).

## Security

- [ ] No keys, tokens, or passwords typed into node fields. Use credentials. (auto)
- [ ] Code nodes do not read environment variables. Blocked in n8n 2.x. (auto)
- [ ] No `$evaluateExpression`. Removed in n8n 2.x. (auto)
- [ ] No Execute Command node unless agreed. (auto)

## Structure and clean-up

- [ ] Node names say what they do ("Build CRM Payload", not "Code1").
- [ ] A sticky note at the start: purpose, trigger, owner, last change date.
- [ ] A Set node named "Settings" right after the trigger holds the values other nodes use (sheet names, recipients, thresholds, labels).
- [ ] Every Code node opens with a plain-language comment on what it does and why.
- [ ] `settings.executionOrder` is `"v1"`. (auto)
- [ ] Pin data removed. No disabled nodes left by accident. (auto)
- [ ] A dated snapshot is saved: `python kit/n8nkit.py pull <id> --client <name>`.
