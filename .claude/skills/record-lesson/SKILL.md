---
name: record-lesson
description: How to record a lesson learned about building or testing Retell voice agents — what counts as crucial, where the lesson goes, and how to write it. Use when you have just learned something a future session would waste time or ship a defect without.
---

# Recording a lesson

Write it down **in the same session you learned it**, without being
asked. A lesson recalled later is usually recalled wrong.

## What counts as crucial

Something is crucial when a future session would waste time or ship a
defect without it. In practice that means any of these:

- A platform behaviour that is not in the docs, or contradicts them.
  Example: an `always_edge` still needs a caller turn, so it cannot
  rescue a node from a silent caller.
- An API rule found by hitting an error. Example: fine-tune example ids
  must be unique across the whole flow, and a rejected PATCH is
  all-or-nothing.
- A defect class, not just one defect. Write the shape, so the next one
  is recognised. Example: a rule phrased "ask if still missing" will
  always re-ask a refusal.
- A fix that looked obvious and was wrong, and why.
- A test that could not pass, or passed for the wrong reason.
- A measurement that changes how work is prioritised. Example: cost is
  per turn, not per repository.
- Anything a real call transcript shows that no test caught.

## Where it goes

| What kind | Where |
|---|---|
| General to any Retell agent, any client | `$K/docs/lessons/`, plus a line in `$K/docs/lessons/index.md` saying what to read it before |
| Something that also belongs in a standard or checklist | The right file in `$K/docs/standards/`, plus a line there |
| Specific to one client's agent | that agent's `<client>/agents/<slug>/AGENT.md` and `CHANGELOG.md` |

Never put a client name, id, or fact into a kit lesson. A kit lesson must
read the same for every client.

## How to write it

- **Keep the evidence.** Quote the call id, the error message, or the
  test counts. A claim with no evidence is not a lesson. A call id from
  a client is evidence only inside that client's own folder.
- **Write the general rule AND a worked example.** The rule is what
  transfers; the example is what makes it believable. Scrub the example
  of any client fact before it goes in the kit.
- **Say what was wrong before**, not only what is right now. The wrong
  version is what the next person will otherwise try.
- A lesson that changes how work is done also gets a checklist line. A
  rule nobody checks is a rule nobody follows.
- Do not wait for the end of a task. Do not wait to be asked.
