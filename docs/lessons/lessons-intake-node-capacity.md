# A single-node intake has a word budget, and adding a correct rule can spend it

Measured 2026-09-05 and 2026-09-06 on one example agent, `--model gpt-4.1`.

Two guards were ported from a second example agent onto one example agent's `Service Request Intake`.
Both are correct rules. Both restate something the client asked for. Adding them
made the agent abandon more calls.

## The dose-response curve

`T-A2` is an ordinary complete service call: name, number, vehicle, problem,
address, urgency, then "no that's everything". It should reach
`Closing / Anything Else — Normal` and be asked the closing question once.

| `Service Request Intake` | Change | `T-A2` |
|---|---|---|
| **476 words** | live v54, nothing added | **3 of 3**, and **8 of 8** on an earlier run |
| **554 words** | `# SAY THE SENTENCE AS WRITTEN` only | **2 of 5** |
| **619 words** | that plus `# ONE ASK PER TURN` | **0 of 3**, twice |

Every failure is the same shape:

    never reached node 'Closing / Anything Else — Normal'
    reached forbidden node 'Incomplete Intake Exit — Normal'

The intake runs longer, does not finish inside the call, and takes the
abandonment edge. On a real call that is a lead that reaches the client marked
incomplete instead of complete.

Note the 0-of-3 result held for BOTH wordings of the second guard: a second example agent's
"Never ask two items in one turn", and an one example agent rewrite that deferred to
one example agent's global `# Style` for what one goal is. Rewording did not help,
because the words were not the problem. The word COUNT was.

## The mirror already existed in this repository

`docs/lessons-v22-overhaul.md`, on a second example agent: cutting 77 provably duplicated
words took a trace from 3 of 3 to 1 of 3. "Redundant text is still
load-bearing."

This is the same effect measured in the other direction, on a different agent,
a year of drafts later. **Text you add is load-bearing too.** A node instruction
is not a document that gets better as it gets more complete. Past some size the
model stops finishing the job the node exists to do.

## Read the failure, not the score

`T-AL` scored 3 of 5 before the change and 3 of 5 after. Identical numbers,
completely different runs:

    before:  said 1x (wanted 0x): 'Sprinter'                  x2
    after:   said 2x (wanted 1x): 'Can we text you...'        x2

The guard DID stop the agent echoing the caller's vehicle back, which is what
it was for. What surfaced underneath was a second, older defect the same trace
also catches. An unchanged pass rate hid a real fix AND a real remaining fault.

## The rule

**Before adding any text to an intake node, measure a complete-call trace on the
node as it stands, then again after.** Not the trace for the defect being fixed
— a trace for the job the node normally does. The defect trace tells you whether
the rule works. The complete-call trace tells you what the rule cost.

If the completion trace drops, the rule does not ship, however correct it is.
A wording annoyance is cheaper than an abandoned lead.

## What to do instead, when the node is full

Nothing was found that works for free, and this is honest rather than
prescriptive:

- **The global prompt** costs every turn of every call instead of one node's
  turns. That is a different bill, not a smaller one. Measure it the same way.
- **A negative fine-tune example** moves a TRANSITION trigger
  (`docs/lessons-v24-fix-selection.md`) but says nothing about what the node
  speaks, so it does not help with an echoed word.
- **Splitting the node** is what a second example agent does, and it buys room at the cost of
  the empty-handed-node defect recorded in
  `docs/lessons-decider-that-can-speak.md`. one example agent collapsed the intake into
  one node on purpose to avoid exactly that.

So on one example agent the "your Sprinter" echo stays open, documented, and unfixed. It
is a wording annoyance measured at 2 failures in 5, and every fix tried for it
cost more than it was worth.
