# Lessons: deleting a node can strand a guardrail elsewhere in the flow

## Deleting a node leaves a live instruction naming it

a second example agent v30 split `Guardrail Refusals` into two globals and, separately,
deleted `Sign-off (Incomplete)`. `Incomplete Intake Exit` still carries:

> "Do not say a goodbye here; Sign-off (Incomplete) says it on the next turn."

That node no longer exists, and the exit's own mandated line already ends with
"I'll end the call now. Take care." So the instruction now tells the model NOT
to say the words the same instruction orders it to say. Measured on the draft,
the model said the full line anyway (T-U, 1 of 1 verbose run), so this is a
latent contradiction rather than a live defect — but it is exactly the class
recorded in an audit done once when this rule was adopted.

`Guardrail Refusals` carries the same residue in its go-back condition:
"never go back right after speaking the Sales/Spam hard-stop line" — a line
that node no longer speaks.

**Rule.** After deleting or splitting a node, grep every instruction, every
go-back condition, and every edge prompt for that node's NAME, not just its id.
`flowlint.py` checks ids and reported this flow clean.

## A trace that names a deleted node fails without a defect

`T-U` asserts the call reaches `Sign-off (Incomplete)`. It failed 0 of 3 on
v30 because the node was removed on purpose and the path is now
`Incomplete Intake Exit -> End Call`. A RED verdict from `tracerun.py` is not
proof of a regression until you read the path walked.

**Rule.** A structural change that removes a node is not finished until the
traces that name it are rewritten in the same session.

## An n8n `$('Node Name')` lookup fails silently on a renamed node

The Phase 1 recap workflow's `Attach Drive Links1` code node looks up
`$('Upload Audio to Drive')` and `$('Upload Transcript to Drive')`. The nodes
are actually named `Upload Audio to Drive1` and `Upload Transcript to Drive1`.
Both lookups throw, the `try/catch` swallows it, both ids come back empty, and
every recap email reports "recording not archived and transcript not archived"
with two dead Drive links — on calls that archived perfectly.

Duplicating an n8n workflow appends `1` to every node name but does NOT rewrite
the name strings inside code nodes.

**Rule.** After duplicating an n8n workflow, grep every code node for `$('`
and check each name against the node list.

**Measured 2026-08-31.** The node code was extracted and run under plain `node`
against the workflow's own pinned real call, with the referenced nodes stubbed
both ways. Correct names: `drive_archive_ok true`, and both links resolve to
`https://drive.google.com/file/d/<id>/view`. Names carrying the trailing `1`:
`drive_archive_ok false`, both links empty string, and the status line reads
"recording not archived and transcript not archived" — the exact text the client had
been seeing on calls that archived fine. The `try/catch` around the lookup is
what makes this silent; it cannot tell a renamed node from a failed upload.

**A general one worth keeping.** An n8n code node is ordinary JavaScript. It can
be lifted out of the workflow JSON and run under `node` with `$json`,
`$getWorkflowStaticData` and `$('Name')` stubbed, using the workflow's own
`pinData` as the input. That turns "read the code and reason about it" into a
measurement. Eight recap shapes were checked this way in about a minute: real
lead, company transfer, hang-up, roadside drop, sales pitch, a second example agent lead with
the accuracy lists, a wrong event type, and a duplicate retry.
