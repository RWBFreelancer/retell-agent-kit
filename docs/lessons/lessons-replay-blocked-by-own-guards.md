# Every guard on the replay path is untested until a replay actually runs

**Learned 2026-09-07, on the second replay attempt in three days to be stopped
by our own code before it left n8n.**

## The rule

A guard that has only ever seen live traffic has never been tested against a
replay. Replay is a different shape of input, and the guards fire on it in ways
nobody designed for. So a replay is not "a live call again": it is a new code
path through old code.

Before firing a replay, walk **every** early return between the webhook and the
thing being tested, and say out loud which ones the replay will hit.

## Two in a row, same shape, different guard

**2026-09-05 and 2026-09-06.** Rey pushed two live test calls to prove the downstream owner's
async fix. Both came from his own line, XXX-XXX-XXXX. `Build the downstream owner Payload`
carries a `TEST_NUMBERS` guard that returns `[]` on that number, added weeks
earlier when Safrit and Ray were being replayed. The handoff never left n8n.
Rey reported it to the downstream owner on 2026-09-06 as his own fault.

**2026-09-07.** Rey replayed `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx` through
`tools/webhookreplay.py`, with the downstream owner warned and waiting. The tool reported
`HTTP 200 {"message":"Workflow was started"}` and `1 of 1 accepted`.

n8n execution **1247** ran exactly two nodes: `Retell call_analyzed`, then
`Guard and Normalize`, which returned **0 items**. Everything downstream was
skipped. `Send to the downstream owner` never ran. No error, no failure email, status
`success`.

The cause is section 2 of `Guard and Normalize`:

    const store = $getWorkflowStaticData('global');
    store.seen = store.seen || [];
    const dedupeKey = `${event}:${callId}`;
    if (callId && store.seen.includes(dedupeKey)) {
      return [];                       // duplicate retry, already processed
    }

The call was processed normally on 2026-09-04 when it happened. Its key has sat
in `staticData.global.seen` ever since. The replay is, to that guard,
indistinguishable from a retry.

Confirmed by reading the workflow's static data over the n8n public API: the
list is at its 500 cap and contains
`call_analyzed:call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`.

## Why this was hard to see

**A 200 from the webhook proves nothing.** n8n answers `200 {"message":
"Workflow was started"}` the instant it queues the run. Every guard, every
branch and every failure happens after that reply. The sending tool cannot see
any of it.

**A dropped call looks like a healthy one.** The execution status is `success`.
There is no error and no failure email, because returning `[]` is a normal way
for a code node to end a branch. Only the node count gives it away: two nodes
ran where a real call runs twenty.

**The idempotency guard is correct.** It exists so a Retell retry cannot double
up an email, an SMS and a the client CRM record. Nothing about it is a bug. It is
right, and it makes deliberate replay impossible, and both of those are true at
once.

## What to check before firing a replay

- List every `return []`, `if (...) return`, and IF node between the webhook and
  the node under test. Name which ones the replay will hit.
- Ask whether the target call has been through this workflow before. If it has,
  the dedupe guard will drop it.
- After firing, **read the execution, not the HTTP response.** Count the nodes
  that ran. Confirm the node under test appears in `runData`.
- A replay that must reach a specific downstream system is not proven by
  anything the sending tool prints.

## What this cost

Three days of the downstream owner's async fix sitting unproven, across two attempts, with
both parties believing the ball was in the other court. the downstream owner wrote on
2026-09-07: "That call is the one thing on the client's fix list that has never met
real traffic."

## The general shape

This is the same family as
[lessons-webhook-gap.md](lessons-webhook-gap.md) and
[lessons-green-verdict-blindness.md](lessons-green-verdict-blindness.md): a
green signal that was never measuring the thing anyone cared about. It is also
exactly what the downstream owner found on his own side the same day, where his transcript
check passed every test while the live path could not reach the code under
test.

Ask of any green result: **which node did I actually prove ran?**
