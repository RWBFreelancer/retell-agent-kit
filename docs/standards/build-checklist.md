# Build Checklist

Use this while you create or edit a Retell conversation flow.

## Reference notation

Brackets below point at a source. There are three kinds. They used to be one
bracket for all of them, which made `[23]` ambiguous between a section number and
a lessons file.

| Form | Means |
|---|---|
| `[§N]` | Section N of [retell-flow-standard.md](retell-flow-standard.md) |
| `[§3a]` | The GPT-4.1 section of the same file. Read it before rewriting any instruction. |
| `[v23]` | A lesson in [../lessons-v23-live-call-defects.md](../lessons-v23-live-call-defects.md) |
| `[fix N]` | Lesson N in [../lessons-v24-fix-selection.md](../lessons-v24-fix-selection.md) |

---

## Before you build

- [ ] Write the brief first: what the agent is, who calls, how it sounds, what
      it must never do. [§0]
- [ ] Confirm a flow is right, not a single prompt. [§1]
- [ ] Decide inbound or outbound. Set `start_speaker`. [§9] [§12]
- [ ] Name the niche. Pull its "never" list. [§13]
- [ ] Name the laws that apply. [§14]
- [ ] Write the traces before the prompts. List every scenario. [§22]
- [ ] Confirm `flex_mode` is off. [§2]

## While you build

### Structure

- [ ] Greeting node and intent-router node are separate. [§9]
- [ ] Every branch reaches an `end` node. [§10]
- [ ] Every `transfer_call` node has a failure path. [§6] [§10]
- [ ] Every function node has a failure path. [§10]
- [ ] After-hours path exists. [§10]
- [ ] Wrong-number path exists. [§10]
- [ ] Voicemail path exists, if outbound. [§12]
- [ ] Every node with `edges` has an `else_edge`, or cannot trap the call. [§6]

### Routing

- [ ] Every edge that could be an equation **is** an equation. [§6]
- [ ] Every multi-equation edge has the right join, `&&` or `||`. [§6]
- [ ] Every node with 3 or more edges has 4 to 5 fine-tune examples. [§8]
- [ ] Every global node has a go-back condition, unless it ends the call. [§7]
- [ ] Every node has ONE exit that cannot fail to match. A node whose only exits
      are prompt edges is a trap: a caller who says "okay" stays in it and hears
      the same line every turn. [§7]
- [ ] Every branch that says "ask nothing" or "add nothing" has its OWN example.
      Examples teach a shape; an unshown shape does not happen. [§8]
- [ ] No go-back edge points at a `static_text` node. [§7]
- [ ] Every named case or track INSIDE a node has at least one example. A node
      that owns a whole track with no example for it will miss that track. [§8]
- [ ] No example contradicts its own node instruction. When a rule changed,
      every example showing the old behaviour was found and changed too. [§8]
- [ ] Every example turn has the right `role`. No agent line is tagged
      `"role": "user"`. [§8]
- [ ] Example ids are unique across the WHOLE flow, not per node. [§8]

### Node text

- [ ] One node, one job. [§4]
- [ ] Node prompts are short. Role, steps, rules, examples. [§4]
- [ ] Every line that must be exact is `static_text`. [§4]
- [ ] The tool-wait line is `static_text`, not a prompt. [§3] [§4]
- [ ] No caller-facing line was reworded without being asked. [§4]
- [ ] No line in any instruction, and no line in the global prompt, starts with
      a number or a numbered label. No `Step 2`, no `(1)`, no `PRIORITY 1`, no
      `RULE 3`. They compete with the node's transition options and can fire an
      edge whose condition never matched. Use dashes, or a named header. [§3a]
- [ ] No rule is written as a loud statement plus a separate exception. Write
      one conditional sentence instead. On gpt-4.1 the loud rule and the later
      rule can each win, so ordering settles nothing. [§3a] [§4]
- [ ] Every `Example:` line either matters word for word, in which case it
      should be `static_text`, or carries an explicit "vary the wording". A
      sample phrase is reused verbatim by this model. [§3a]
- [ ] Every node whose only job is one short announcement uses `static_text`,
      even when the wording is not contractual. A prompt instruction there is
      the documented shape that leaks the prompt to the caller. [§3a]
- [ ] No fill-in slot orders behaviour with no empty branch, e.g.
      `{always ask the next question}`. [§4]
- [ ] Where the flow already records a fact in a variable, the instruction
      points at the variable, not at a description of the situation. [§4]
- [ ] Every closing or goodbye line has ONE owning node, and is banned by name
      in every other node that could reach the end of a call. [§4]
- [ ] Every question the caller hears appears in the instruction as a QUOTED
      sentence, introduced by "Ask exactly, word for word". A described
      question is written by the model, not by you. [§4]
- [ ] Every Ask node bans the narrowing follow-up by name. "Box truck" is the
      vehicle; asking what type of box truck is a re-ask. [§4]
- [ ] No node can be entered with nothing to do. "Say nothing here" does not
      stop the node holding a caller turn; route around it instead. [§4]
- [ ] No counter guard uses `!=`. It matches every value except one, including
      the ones that mean "this has not happened yet". Write the equation so
      the DEFAULT value falls on the safe side. [§6]
- [ ] Every new edge was checked against every edge already on that node:
      which caller satisfies both? Put the exclusion in the NEW edge. [§6]
- [ ] Every quoted question says "Ask exactly, WORD FOR WORD", and separately
      bans personalising it with the caller's own noun and bans opening with
      a restatement of what they just said. [§4]
- [ ] No check that must fire hangs off a node the flow can skip. Attach it
      to a node every call of that type passes through. [§6]
- [ ] No edge condition has to judge more than one or two facts at once,
      where being wrong loses data. [§6]
- [ ] Every extract description was read against the client's own wording,
      and against any post-call field describing the same fact. Two
      descriptions of one fact must not disagree. [§6]
- [ ] No confirmation sentence bundles two facts. One "Is that correct?" can
      answer for one field only. [§18]
- [ ] A name is asked for by letters when the caller gave it in under about a
      second, or when it is not common in the agent's language. A readback
      only catches an error the caller objects to. [§18]

### Global prompt

- [ ] Holds role, personality, hard rules, tone, compliance, speech format,
      current time. [§5]
- [ ] Holds no steps. Steps live in nodes. [§5]
- [ ] **Cleanup pass done.** Every line the flow already enforces is deleted. [§5]
- [ ] Worst case per turn measured: always-on plus the LARGEST node. Cuts were
      made there, not in whichever node had the most duplicated text. [§2]
- [ ] Real token number pulled from `llm_token_usage` on live calls BEFORE any
      trim is proposed. Retell surcharges above 4,000 tokens and scales the
      whole billed duration; under 4,000 a cut saves nothing. [§2]
- [ ] Transcript growth counted in the total. It is charged every turn and
      cannot be cut, so it sets how much prompt room is left. [§2]

### Delivery

- [ ] `webhook_url` is set on the agent, and read back from the PUBLISHED
      version, not the draft. It lives on the agent, not the flow, so no flow
      test can see it. [§21]
- [ ] The recap actually arrived at the far end, checked once by hand after
      publishing. A green flow can still deliver nothing. [§21]
- [ ] Speech formatting block is in. [§18]
- [ ] Standard handlers are in. [§19]

### Variables

- [ ] Every required detail is written to a variable when captured, not worked
      out later. [§11] [§20]
- [ ] Every variable is both written and read. [§21]
- [ ] No variable makes a judgment. It only records one. [§11]
- [ ] `default_dynamic_variables` holds sample values only, never real customer
      data. [§11]

### Settings

- [ ] `tool_call_strict_mode` is `true` at flow level. Transitions are tool
      calls, and this is the documented lever for transition reliability on
      gpt-4.1. Never turn it off to tidy a diff. [§3a]
- [ ] The three silence fields were set on purpose, not inherited. Retell's
      defaults are 10000 / 1 / 600000, and ten minutes of silence is almost
      never what an inbound line wants. [§10]

- [ ] `model_choice` set. [§15]
- [ ] `kb_config` set, if a knowledge base is used. [§15]
- [ ] `guardrail_config` set. Turn on `regulated_professional_advice` for
      medical, legal, and financial. [§14]
- [ ] `pii_config` categories match the data this flow touches. [§14]
- [ ] `post_call_analysis_data` configured. `enum` where the answers are fixed.
      [§15]
- [ ] Silence timer, max duration, and reminder set. [§15]
- [ ] Interruption locked off on any disclosure node. [§15]
- [ ] `handbook_config` toggles: nothing on that the prompt already does. [§16]
- [ ] Every component checked for its own `flex_mode` flag. [§17]

## Routing safety

- [ ] No node has two prompt edges that could both match the same turn. The
      common case is on the else edge; the rare case is the one prompt edge. [§6]
- [ ] Every loop back into the same question node has a counter and an equation
      edge out of it. [§10]
- [ ] `skip_response_edge` appears on no node that asks a question. [§10]
- [ ] Every node that speaks but asks nothing HAS a `skip_response_edge`. Ask
      "what does the caller need to say here?" An `always_edge` does not do
      this job; it still needs a caller turn. [§6]
- [ ] No `else_edge` was added to a global node to stop a stall. The go-back
      condition is that node's fallback; widen it instead. [§6] [§7]
- [ ] No edge shortcuts past a code node that computes a recap variable or marks
      state. Route through the builder, not around it. [§21]
- [ ] Every "ask only if missing" rule is phrased as "ask only if NOT YET
      ASKED". A refusal counts as asked and is recorded before the gate. [§21]
- [ ] `reminder_trigger_ms`, `reminder_max_count`, and
      `end_call_after_silence_ms` are all set on purpose, not inherited. [§10]
- [ ] Every branch equation reads an `enum` with `choices`, not a free-form
      `string`. [§11]
- [ ] Every destination node was opened and read, not chosen by its name. A node
      named for one path may set variables that change another. [§21]
- [ ] Any variable the recap depends on is set on **every** exit that can end a
      call, not only the happy path. [§21]
- [ ] No `extract_dynamic_variables` node is expected to ask the caller
      anything. It cannot speak. [§11]

## Before you push

- [ ] Structure check clean: no dangling edges, no dead ends, no unreachable
      nodes, no unguarded double-say. [§21] [§22]
- [ ] For any sentence a GLOBAL node can say, the double-say was proved by a
      trace, not by the linter. The linter walks edges; a global node has no
      inbound edges, so it reports 0 of 0 paths and looks clean. [§21]
- [ ] If the global prompt shrank, a canary trace was run at `--reps 3` before
      and after, and the count did not drop. Removing text that is provably
      duplicated elsewhere still moves routing that has nothing to do with it.
      [§22]
- [ ] To stop a global node firing, a NEGATIVE fine-tune example was added, not
      another clause in the condition. Put the distinguishing context in the
      AGENT turns: the user turn is usually identical either way. [§8]
- [ ] No fix relies on an edge competing with a global node's go-back. The
      go-back wins. [§7]
- [ ] Every global node was asked: what does it do with a caller who has
      given nothing and will give nothing? If no edge answers and `else_edge`
      is null, it can PARK the caller until `max_call_duration_ms`. Fix it in
      the node that hands callers in, never by adding an escape edge to the
      parked node itself: that measured 0 of 8. [§7] [§10]
- [ ] `end_call_after_silence_ms` was NOT treated as the backstop for a stuck
      caller. It only measures silence; a caller who keeps talking resets it
      every turn. `max_call_duration_ms` is the real ceiling. [§10] [§15]
- [ ] `flowpull` and `flowdiff` were re-read immediately before trusting the
      test results, not only at the start. [§22]
- [ ] Traces run and green. [§22]
- [ ] An improvising-caller test was run too, not only scripted turns. They
      catch different defects. [§22]
- [ ] The thing tested was the flow object about to be pushed. If the tooling
      can only test what is already on the server, a throwaway copy was stood
      up and tested instead. [§22]
- [ ] Any test that failed was checked for being a bad test before the agent was
      changed. [§22]
- [ ] Anything that hinges on silence was walked on paper. [§22]
- [ ] Any prompt-edge behavior was run more than once. Nine of ten is a defect.
      [§22]
- [ ] A reversal route exists: an inverse change, or a snapshot of the old
      version.
- [ ] If it is an inverse, the round trip was proved BYTE-FOR-BYTE against the
      snapshot. Watch for a key set to `null` versus removed, and an empty list
      versus a missing key.
- [ ] The target is a draft, never the version taking live calls.
- [ ] Every variable that gates a spoken line is re-read wherever the caller
      could supply it, not only where you expected them to. [v23]
- [ ] No behaviour depends on a flag set on the way OUT of a node that a global
      node can fire from. Count arrivals at a branch instead. [v23]
- [ ] A trace that passes on the BROKEN flow proves nothing. Run every new
      trace against the unfixed export first. [v23]
- [ ] Any route that MUST hold is held by a variable and a branch, not by the
      word "always" inside a prompt edge. [v23]
- [ ] `python tools/retell_chat.py cleanup` was run after any crashed or
      interrupted trace run. A dropped connection leaks a sandbox. [v23]
- [ ] Any NEW node object was built by copying the key set from a node of the
      same type in that same flow, never written from scratch. A code node
      needs eleven keys, and `flowlint.py` passes a node missing every one of
      them. [§3]
- [ ] Every new code node has `response_variables`. Without it the node
      computes the value and discards it, silently, with no error anywhere. [§3]
- [ ] At least one `tracerun.py` was run AFTER adding any node. It is the
      first thing that checks the object against Retell's schema. [§3]
- [ ] Approval received for this specific change.

## After you push

- [ ] Pull a fresh copy and diff it. Confirm what landed matches the intent.
- [ ] Test sandboxes cleaned up.
- [ ] Changelog written.
