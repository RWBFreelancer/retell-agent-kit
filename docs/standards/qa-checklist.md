# QA Checklist

Use this to check an existing Retell conversation flow.

## Reference notation

Brackets in the tables below point at a source. There are three kinds, because
this file used to use one bracket for all of them and `[23]` meant two different
things on two different rows.

| Form | Means |
|---|---|
| `[§N]` | Section N of [retell-flow-standard.md](retell-flow-standard.md) |
| `[§3a]` | The GPT-4.1 section of the same file. Read it before rewriting any instruction. |
| `[v23]` | A lesson in [../lessons-v23-live-call-defects.md](../lessons-v23-live-call-defects.md) |
| `[fix N]` | Lesson N in [../lessons-v24-fix-selection.md](../lessons-v24-fix-selection.md) |

**Rule: a check passes only on evidence.** "It looks fine" is not a pass. Each
line below says what counts.

Work from a **fresh export** of the flow, not from memory and not from a
filtered view.

---

## A. Structure

| # | Check | Evidence that counts | Section |
|---|---|---|---|
| A1 | No dangling edge | Linter output | [§21] |
| A2 | No dead end | Linter output. Checks `edges`, `else_edge`, `always_edge`. | [§21] |
| A3 | No unreachable node | Linter output | [§21] |
| A4 | Every branch reaches an `end` node | Walk each branch in the export | [§10] |
| A5 | `flex_mode` is off at flow level | The JSON field | [§2] |
| A6 | Every component's own `flex_mode` is off | The JSON field, per component | [§17] |
| A7 | Greeting and intent router are separate nodes | The export | [§9] |
| A8 | `start_speaker` matches inbound or outbound | The JSON field | [§9] [§12] |

## B. Routing

| # | Check | Evidence that counts | Section |
|---|---|---|---|
| B1 | Every prompt edge that could be an equation is flagged | Read each edge. Name each one you would convert. | [§6] |
| B2 | Every multi-equation edge has the right join | Read the `operator` on each | [§6] |
| B3 | Nodes with 3+ edges have fine-tune examples | Count them per node | [§8] |
| B4 | Every global node has a go-back condition | The `global_node_setting` | [§7] |
| B5 | No go-back edge lands on a `static_text` node | Follow each go-back edge | [§7] |
| B6 | No unguarded double-say path | Linter, per exact sentence. A path marked UNGUARDED is a defect. | [§21] |
| B6a | No global node relies on a competing edge to steer its exit | A go-back outranks a matching edge on the same node. Fix the node that speaks, not the node that hands back. | [§7] |
| B6b | Every global node answers: what happens to a caller who gives NOTHING? | Read every edge condition on the node. If they all presuppose progress the caller has not made, and `else_edge` is null, the node can PARK the caller until `max_call_duration_ms`. Fix it in the node that hands them in, never by adding an edge here: that measured 0 of 8. | [§7] [§10] |
| B6c | The parked-caller case was checked on a REAL call record, not a trace | `current_node` and `previous_node` in `collected_dynamic_variables`, plus `disconnection_reason`. A `user_hangup` with two or three node hops and a long duration is a parked call. No flow test shows this. | [§10] [§22] |
| B6d | No say-once guard is phrased against the CALL where the design says the line once per NODE | Two chained nodes each saying the same sentence once: a call-scoped guard silences the second. Phrase it against the node. | [§21] |
| B6e | Every contractual sentence was read in at least one full transcript, by hand | A `say_times` count is blind to a paraphrase of the same message. Green proves the SENTENCE was said once, not that the TOPIC was raised once. | [§22] |
| B6f | Before/after comparisons used 8 reps on at least two traces | 3 reps cannot separate 3-of-3 from 2-of-3, and one 5-of-5 run gave an actively misleading answer. A 1-rep full suite shows spurious failures almost every run. | [§22] |
| B6g | A fresh `flowpull` and `flowdiff` were read immediately before the test result was trusted | Anyone with the UI open can edit the draft mid-session. One hand reformat moved a trace from 3 of 3 to 2 of 5. | [§22] |
| B6h | Every chat-sandbox scenario starts with a filler turn | The sandbox is one turn behind a real call: your first message produces the greeting and its content is discarded. A scenario whose real content is in turn 1 is testing something that cannot happen on a phone call. | [§22] |
| B6h3 | A test that depends on an agent setting built its sandbox agent with production's settings | `retell_chat.Sandbox` makes a bare chat agent, so Retell's default handbook applies (Professional tone and AI disclosure ON), not production's. Pass `handbook_config` and, for analysis tests, `post_chat_analysis_data` and `post_chat_analysis_model` to `create-chat-agent`. NATO never applies to chat. | `docs/lessons-sandbox-route-divergence.md` |
| B6h2 | Any Open/Closed wording test ran on clock-fixed copies | The sandbox reads the real clock, so a run at an open hour tests the open wording whatever the trace means. Replace the `Now:` line with a fixed closed and a fixed open time, for baseline and candidate both. | `docs/lessons-after-hours-traces.md` |
| B6i | Any global-prompt reduction was measured, not assumed | A canary trace at `--reps 3` before and after, same count or better. Redundant text is still load-bearing: cutting 77 provably duplicated words took one trace from 3 of 3 to 1 of 3. | [§22] |
| B6j | If a GLOBAL node is one of the sayers, a trace proved it | The linter walks edges and a global node has none, so it reports "no path between two sayers" and 0 of 0 paths. That is a blind spot, not a pass. Needs a `say_times` trace at `--reps 3`. | [§21] |
| B6k | Every node that SPEAKS and has more than one inbound edge was checked for re-entry | The linter looks for a path between two DIFFERENT sayers, so a funnel node that says its own line twice reports "no path between two sayers" and 0 of 0 paths. A node carrying its own pass counter that can exceed 1 must not speak at all. | [§21] |
| B6l | Any say-once FAILURE on `gpt-4.1-mini` was checked against real calls before it was called a defect | Mini fails prose-guarded say-once rules that `gpt-4.1` passes. Measured 2026-09-08: T-W and T-Y both FAIL on mini and both PASS on 4.1, on the same export, and 38 real calls said the line 0 times twice. Count it on real calls, which is free. Do NOT re-run on `gpt-4.1`: the client had not approved that test cost, and the tools refuse it. If real calls cannot settle it, say so to Rey. | [§22] |
| B6m | Any claim about WHO ended a call was read from `disconnection_reason` AND the node state together | `disconnection_reason` says who hung up, never whether the agent had finished. Read `current_node`, `previous_node`, `gate_next` and any say-once marker beside it. Measured 2026-09-11: a call reading `user_hangup` after an agent callback line looked like the agent closing early, and the node state showed the flow still mid-intake in a global node with `closing_line_said` no. | [§10] [§22] |
| B6n | Any code inserted into an existing node was anchored on a string that appears EXACTLY once, and the node was executed afterwards | Walking back to the nearest `return`, `}` or `const` finds the wrong one. Measured 2026-09-11: a helper landed inside an early-return guard, `node --check` still said SYNTAX OK, and every call would have thrown a ReferenceError. A parser cannot see a scoping bug; one execution against a real payload can. | [§22] |
| B7 | Every node that speaks but asks nothing has a `skip_response_edge` | The node object. An `always_edge` does NOT do this job. | [§6] |
| B8 | No example contradicts its own node instruction | Read every example against its node. The example wins in practice. | [§8] |
| B9 | Every example turn carries the right `role` | An agent line tagged `"role": "user"` is a defect. | [§8] |
| B10 | Example ids are unique across the whole flow | Collect every id in the file and look for repeats. | [§8] |
| B11 | Every named track inside a node has an example | List the node's cases, then its examples. | [§8] |
| B12 | No `else_edge` was added to a global node that already has a go-back | On a global node with NO go-back, an else edge is correct. | [§6] [§7] |
| B13 | Every node has one exit that cannot fail to match | List the exits. All-prompt-edges with no else, no always and no go-back is a trap. | [§7] |
| B14 | Every "ask nothing" branch has its own example | Examples teach a shape. An unshown shape does not happen. | [§8] |
| B15 | The closing chain is gated on COMPLETENESS, not just on repetition | Read every equation on the closing router. `closing_passes > 1` answers "have I closed before?", never "did I collect anything?". A caller reached the goodbye here with four intake items unasked. | [§21] |
| B16 | No `else_edge` points at a closing, a sign-off, or a transfer | An else edge has no condition. From a global node it is an unconditional hang-up. List every else edge and name its destination. | [§6] [§21] |
| B17 | Any equation reads a variable that is already SET at that point | Trace the extract node's position against the branch that reads it. An extract downstream of the router leaves every variable at its default when the decision is made, so the equation fires on every call. | [§11] |

## C. Failure paths

| # | Check | Evidence that counts | Section |
|---|---|---|---|
| C1 | Transfer-failed path exists | The `edge` on each `transfer_call` node | [§10] |
| C2 | Function-failed path exists | The `else_edge` on each `function` node | [§10] |
| C3 | After-hours path exists | The export | [§10] |
| C4 | Silence is handled | `end_call_after_silence_ms` plus a path | [§10] |
| C5 | Wrong number is handled | The export | [§19] |
| C6 | Voicemail is handled, if outbound | The export | [§12] |

## D. Node text

| # | Check | Evidence that counts | Section |
|---|---|---|---|
| D1 | One node, one job | Read each node prompt | [§4] |
| D2 | No node prompt is over-long | Read each node prompt | [§4] |
| D3 | Every exact line is `static_text` | The `instruction.type` per node | [§4] |
| D4 | Tool-wait lines are `static_text` | The `speak_during_execution` text | [§3] |
| D5 | No caller-facing line drifted from the approved wording | Diff against the last approved export | [§4] |
| D6 | Every caller-facing question is a quoted sentence in the instruction, not a description of a question | Read each Ask node; grep for `Ask exactly` | [§4] |
| D7 | Every Ask node bans the narrowing follow-up | Read each Ask node | [§4] |
| D8 | No node is reachable with nothing to do | Walk a call where the caller volunteers everything at once | [§4] |
| D9 | No agent turn is a statement with no question, other than the goodbye and the sales hard stop | Count them over the last 30 calls, not by eye | [§21] |
| D10 | No line in any instruction, and no line in the global prompt, starts with a number or a numbered label | Scan for `Step n`, `(n)`, `n.`, `PRIORITY n`, `RULE n` at line start. Retell documents these as competing with the node's transition options, so an edge can fire whose condition never matched. The wiring looks correct and the linter is clean. | [§3a] |
| D11 | Every `Example:` line either matters word for word, or says to vary the wording | Read the examples. On gpt-4.1 a sample phrase is reused verbatim across turns, so an example meant as a hint becomes a script the caller hears three times. If the words are contractual it should be `static_text`. | [§3a] |
| D12 | Every node whose only job is one short announcement uses `static_text` | The `instruction.type`. A `prompt` instruction at a short announcement node is the documented shape that leaks the prompt aloud to the caller on gpt-4.1. | [§3a] |
| D13 | No rule is written as a loud statement plus a separate exception | Read each instruction for a CAPS or ALWAYS rule and then hunt for its exception elsewhere in the same node. Rewrite as one conditional statement. Ordering is not a reliable control in either direction on this model. | [§3a] |

## E. Global prompt

| # | Check | Evidence that counts | Section |
|---|---|---|---|
| E1 | No steps in the global prompt | Read it | [§5] |
| E2 | **No line the flow already enforces** | For each rule, name the node or edge that makes it redundant, or keep it | [§5] |
| E3 | Speech formatting block present | Read it | [§18] |
| E4 | Standard handlers present | Read it. Check the `NO_RESPONSE_NEEDED` line. | [§19] |
| E5 | Current time present, if the flow uses hours | Read it | [§11] |

## F. Variables

| # | Check | Evidence that counts | Section |
|---|---|---|---|
| F1 | No variable read but never written | Linter | [§21] |
| F2 | No variable written but never read | Linter | [§21] |
| F3 | Every required detail is captured at capture time | Trace one full call | [§20] |
| F4 | Missing and unclear are separate | The recap output | [§20] |
| F5 | No real customer data in `default_dynamic_variables` | Read the field | [§11] |

## G. Settings

| # | Check | Evidence that counts | Section |
|---|---|---|---|
| G0 | `tool_call_strict_mode` is `true` at flow level | The JSON field. Transitions are executed as tool calls, and Retell support names this setting as the lever for transition reliability on gpt-4.1. It is not a tidy-up field. | [§3a] |
| G1 | `guardrail_config` set for the niche | The JSON field | [§14] |
| G2 | `pii_config` categories match the data handled | The JSON field | [§14] |
| G3 | `post_call_analysis_data` configured, `enum` used where fixed | The JSON field | [§15] |
| G4 | No `handbook_config` toggle duplicates the prompt | Compare toggles against the global prompt | [§16] |
| G5 | Interruption locked off on disclosure nodes | Node settings | [§15] |
| G6 | Timers set: silence, max duration, reminder | The JSON fields | [§15] |

## H. Compliance

| # | Check | Evidence that counts | Section |
|---|---|---|---|
| H1 | Every niche "never" line is enforced somewhere | Name the node or global line for each | [§13] |
| H2 | Identity is verified before any private detail | Walk the path | [§12] [§13] |
| H3 | Nothing private is said to a third party | Walk the third-party path | [§12] |
| H4 | Nothing private goes on voicemail | Walk the voicemail path | [§12] |
| H5 | A stop-calling request is honored at once | Walk it | [§12] [§14] |
| H6 | AI disclosure available when asked | The export | [§14] |
| H7 | Recording notice present, if the jurisdiction needs it | The greeting node | [§14] |
| H8 | No card number is ever spoken or stored | Search the export | [§13] [§14] |

## I. Behavior

| # | Check | Evidence that counts | Section |
|---|---|---|---|
| I1 | Every scenario traced | A trace run report, pass per scenario | [§22] |
| I2 | Prompt-edge behavior repeated | More than one run. Nine of ten is a defect. | [§22] |
| I3 | Silence cases walked on paper | Written path, per case | [§22] |
| I4 | Voice, interruption, and speech-to-text checked on a real call | A live call | [§22] |
| I5 | An improvising-caller test was run, not only scripted turns | The run report. Scripted turns miss a caller who says four things in one breath. | [§22] |
| I6 | Every failure was read in the TRANSCRIPT, not just the verdict | The agent's exact sentence, and which node owns it | [§22] |
| I7 | Every failing criterion was checked for being a bad test | Quote the criterion and say why it is right or wrong before changing the agent | [§22] |
| I8 | No test in the suite is permanently red | A red suite stops carrying information. Fix it or retire the runnable part. | [§22] |
| I9 | The thing tested was the object about to be pushed | A throwaway copy is fine; the live draft is not a test bed. | [§22] |
| I10 | Each exact-sentence count names the line the node actually owns for that path | A node with several lines can pass or fail a count for the wrong reason. | [§22] |
| I11 | Anything the agent paraphrases was checked by reading, not counting | Invented questions and improvised goodbyes cannot be counted. | [§22] |
| I12 | No case was called stable on one batch | Two cases flipped in one batch here and passed 4 of 4 alone. Sample before believing. | [§22] |
| I13 | At least one PASSING trace per change was read in the transcript | A green verdict is only as wide as its assertions. One here passed 3 of 3 while the intake collapsed and the goodbye was said five times, because no assertion named the goodbye. `--verbose`. | [§22] |
| I14 | Every trace that reaches the close counts the closing AND sign-off lines | A repeated goodbye is the visible symptom of a routing loop, and it is free to assert. | [§22] |
| I24 | Every `say_times` sentence was COPIED out of the export, not retyped | `say_times` is an exact substring count. 2026-09-05: `T-AD` read 0 of 1 on a greeting the agent said perfectly, because the trace had an ASCII apostrophe and the node has a typographic one (U+2019). The same class catches curly quotes, en-dashes and non-breaking spaces. A red run for this reason looks exactly like a real defect. | [§22] |
| I24 | Any text ADDED to an intake node was measured with a complete-call trace, not only the defect trace | 2026-09-05/06, one example agent `Service Request Intake`: `T-A2`, an ordinary complete call, scored 3 of 3 at 476 words, 2 of 5 at 554, and 0 of 3 at 619, failing the same way every time - the intake ran long and took the abandonment edge. Both wordings of the added rule gave 0 of 3, so the words were not the problem, the word COUNT was. The mirror is in `docs/lessons-v22-overhaul.md`, where CUTTING 77 words took a trace 3 of 3 to 1 of 3. If the completion trace drops, the rule does not ship however correct it is. See `docs/lessons-intake-node-capacity.md`. | [§22] |
| I23 | Every equation transition_condition carries the outer `"operator"` key, even with a single equation | 2026-09-05: a new branch edge built as `{"type":"equation","equations":[...]}` without `"operator":"&&"` linted CLEAN, passed `flowapply`, and then failed `create-conversation-flow` with HTTP 400 `edges/0/transition_condition must have required property 'prompt'` — which reads as a prompt-edge complaint and is not one. `flowlint` does not check it and a draft PATCH may accept it, so the first sign is a sandbox that will not build. Copy the shape from an existing equation edge on the same flow. | [§22] |
| I22 | A ROUTE problem seen only in the text sandbox was counted on real calls before any transform was written | 2026-09-05: `T-IE-A` scored 1 of 8 on two different one example agent flows, saying 7 of 8 ordinary callers were closed as an incomplete intake. Real calls said 3 in 142, and all three were a solicitation, a joke caller, and one that recovered. The sandbox sends one clean scripted turn where a real caller rambles, and a prompt-judged edge reads those differently. Sentence counts and variables transfer from the sandbox; which edge fires does not always. See `docs/lessons-sandbox-route-divergence.md`. | [§22] |
| I21 | Any claim that a live setting is missing, wrong, or absent was checked with a live GET, not a repo file | 2026-09-05, twice in one session: a second example agent was reviewed from `exports/v35` while live at v38, producing a whole plan on a false premise; and one example agent was reported to have no `uncertain_fields` analysis field, read from a stale `agent-settings.json`, when the live agent already had one. `flowpull.py` for a flow, `agentpull.py` for agent settings. A file under `exports/` is a record of a moment, and Rey edits both agents by hand between sessions. | [§22] |
| I19 | Every trace whose subject is a spoken sentence also asserts the node the call ended on | A `say_times` count is satisfied by a call that never REACHED the sentence. 2026-09-05: a second example agent scored GREEN 5 of 5 on `T-AL` while ending in `Service Intake` with nothing captured, and one example agent scored RED while finishing the call and capturing all seven fields. One `expect_path` entry naming `Sign-off & Goodbye` or `End Call` separates them. Read the `path walked` line before the verdict line. | [§22] |
| I20 | No agent-level or before/after claim rests on a single 5-rep run | 2026-09-05: `T-AL` on the SAME unchanged one example agent flow scored 5 of 5 one day and 3 of 5 the next, `--model gpt-4.1` both times (no longer allowed for tests, Rey 2026-09-17), `flowdiff` clean between them. A 5-rep run is a sample of a weighted coin. Run it on two days, or at 10 reps, and report the range. | [§22] |
| I16 | For every green trace, name the assertion that could have failed | A trace with empty `say_times`, `expect_path` and `forbid_path` cannot fail, and the runner still prints GREEN. If the subject is a variable, read the `vars` line instead and compare it with the real call. | [§22] |
| I17 | Any silent node chain on a caller-facing path was timed on a real call | `time_sec` on `node_transition` entries in `transcript_with_tool_calls`. `code` and `branch` nodes cost ~0.02s and are free; each `extract_dynamic_variables` node is a full LLM round trip at ~0.65s median, 2.6s max. a second example agent's closing chain measured a 4.01s median gap with nothing audible in it. See `docs/lessons-silent-node-latency.md`. | [§22] |
| I18 | A slow turn was split into think / compute / speak before the flow was blamed | End of caller's last word to first `node_transition` is the routing LLM (median 1.64s, p90 2.69s); the node chain after it is usually the smaller half. If `think` dominates, the fix is the edge set, not the chain. | [§22] |
| I15 | Every trace id in the file is unique | A duplicate id used to overwrite silently and the runner reported a PASS for a trace it never executed. `tracerun.py` now errors, but check after adding a trace: a new id that collides is the easiest mistake to make. | [§22] |

## Routing safety

Row ids here are `R`. They used to be `J`, which collided with section J below.

| # | Check | Evidence | Section |
|---|---|---|---|
| R1 | No two prompt edges on one node can match the same turn | Both edge conditions, read in full | [§6] |
| R2 | Every loop back into a question node has a counter and an equation exit | The counter node and the cap edge | [§10] |
| R3 | No question node carries `skip_response_edge` | The node object | [§10] |
| R4 | The three silence fields are set explicitly on the agent | The agent settings | [§10] |
| R5 | Branch equations read `enum` values, not free-form strings | The extract node `variables` array | [§11] |
| R6 | Every destination node was read, not assumed from its name | The destination node's code or instruction | [§21] |
| R7 | Recap variables are set on every call-ending exit | The list of exits, and which set the variable | [§21] |
| R8 | No edge shortcuts past a builder or marker code node | Walk each edge that lands on a sign-off or end node and list what it skips | [§21] |
| R9 | "Ask only if missing" rules are phrased as "if NOT YET ASKED" | The rule text. A refused item is still missing and will be re-asked. | [§21] |
| R10 | An explicit refusal is recorded BEFORE the gate that asks | The extract node that runs ahead of the gate | [§21] |
| R11 | Worst case per turn measured as always-on plus the largest node | The linter token report. A repository-wide duplicate count is not a token bill. | [§2] |
| R11a | The agent's REAL token number was read before any prompt trim was proposed | `llm_token_usage` from ~30 real calls via `GET /v2/get-call/{id}`. Below the 4,000-token threshold a cut is worth nothing; above it the surcharge scales the WHOLE billed duration. | [§2] |
| R11b | The token target is stated as a NUMBER, and a block big enough to reach it is actually in scope | Tokens needed to cross 4,000, against the word count of the blocks allowed to be touched. Word counts on this repo's flows read ~1:1 as tokens. | [§2] |
| R11c | Savings were sized per REQUEST, not per repository | An always-on word is charged on every request; a node word only on its own. On a 15-request call that is 15:1. | [§2] |
| R11d | The DELIVERY setting is checked separately from the flow | `webhook_url` on the AGENT object, not the flow. No flow test can see it. Ask "what would still be broken if every test passed?" | [§21] |
| R11e | The drift mirror shows a cleared setting as a CHANGED value, never as a deleted line | Retell omits null fields, so a lost setting silently disappears. `agentpull.py` `REQUIRED` renders it as `_not set_`. | [§21] |
| R11f | After any publish, the live version's `webhook_url` was read back | `list_agent_versions`. A version can be published with it unset, and calls are analysed then forwarded nowhere. | [§21] |
| R11g | A three-value enum has its MIDDLE value defined as tightly as its ends | Read the description. "unknown if not clear" makes abstaining the safe choice, and the field stops discriminating. Say when `unknown` is FORBIDDEN. | [§6] |
| R11h | No enum is read with a boolean test | `!= "yes"` merges `no` and `unknown`, which are opposite facts. Count the three values separately. | [§6] |
| R11i | A rule solved in the FLOW was ported to the analysis field describing the same fact | They are two independent classifiers of one question. One being empty IS a disagreement. | [§6] |
| R11j | Every `{{variable}}` named in an analysis-field description is actually SET by THAT agent's flow | grep the agent's own export for each variable. A description saying "copy `{{x}}`" is a contract with one specific flow, and no flow test and no agent test can see the mismatch. | [§21] |
| R11k | Before running an agent-level tool against a SECOND agent, every block was checked against that agent's flow | The tool encodes one agent's design. It must report what it SKIPPED, not skip silently: "already absent" and "forgotten" must not print the same. | [§21] |
| R11l | No runnable trace reaches its target edge through SILENCE | An empty turn is still a turn, so the sandbox measures the stall, not the flow. If the edge also fires on "refuses to continue", drive it with a refusal. Otherwise walk it on paper and confirm on a real call. | [§22] |
| R11m | A before/after pair that reads IDENTICAL was checked for whether the trace reaches the changed path at all | Read `path walked`. Same number twice usually means the trace never got there, not that the fix did nothing. | [§22] |
| R11n | Every NEW edge that decides whether an intake item was given restates that item's definition IN FULL, including what does NOT count | Read the edge condition beside the destination node's own rule for the same item. An edge does not inherit the node's guards | [fix 41] |
| R11o | A fan-out added to route around a node was measured against the traces that guard the SKIPPED node, not only the trace that motivated it | The two run reports side by side. A fan-out multiplies the places a judgement can go wrong | [fix 41] |
| R11p | Before deleting a rule the runtime cannot honour literally, it was checked for whether it is ALSO acting as a speech instruction | Delete it, then run the traces guarding the node's OTHER behaviours. "End the call immediately" cannot end a call but does suppress a further turn | [fix 42] |
| R11q | No global node is told to answer nothing and go back | A `go_back` is an EDGE, evaluated AFTER the node speaks and AFTER the caller responds. Entered means spoken. Write what it should SAY on a wrong trigger | [fix 43] |
| R12 | Every inverse round-trips byte-for-byte | A diff against the snapshot. `null` versus removed, and `[]` versus missing, both break it. | [§22] |
| R13 | Every variable that gates a SPOKEN line is re-read wherever the caller could supply it | The extract nodes on each path. One extract node early in the call is not enough. | [v23] |
| R14 | No rule depends on a flag written on the way OUT of a node a global node can fire from | The global node conditions, and where the flag is set | [v23] |
| R15 | Trigger conditions built from keywords carry the SHAPE in fine-tune examples too | The positive examples. Speech-to-text drops the keyword. | [v23] |
| R16 | One question covering two items has one "have" check per item | The retry rule and the exit edge. A caller who gives one of the two must not spend the ask for both. | [v23] |
| R17 | No prompt edge is relied on for a route that MUST hold | Search edge prompts for "always", "never" and "regardless". Each one needs a variable and a branch behind it. | [v23] |
| R18 | Every new trace was run against the UNFIXED export first | The before-and-after counts. A trace that passes on the broken flow is a guard, not proof. | [v23] |
| R19 | No trace asserts a probabilistic transition in expect_path | The reps. A global node firing is a judgement, not a fact. Count spoken lines instead. | [v23] |
| R20 | EVERY edge that can reach a call-ending node was walked for what it skips | The full edge list of that node, not the one edge under review. A skipped recap builder empties the recap. | [v23] |
| R21 | A guard is on the choke point, not on one edge into it | The inbound edges of the destination. If more than one thing reaches it, guard the destination. | [v23] |
| R22 | Every Ask node assumes its Mark code node may never run | The global node conditions. An interruption loses the item AND the asked flag. | [v23] |

---

## J. Evidence discipline

| # | Check | Evidence that counts | Section |
|---|---|---|---|
| J1 | Every `simtest` failure was checked against the TRANSCRIPT before any change | The AGENT lines from `get_test_run`, not the grader's summary | [§21] |
| J2 | Every code node is proven to have run AND produced the right value | `transcript_snapshot.dynamicVariables` from a simulation run | [§21] |
| J3 | No tool calls a deprecated Retell endpoint | The current deprecation pages, checked against every path in `tools/` | [§21] |
| J4 | No counter guard uses `!=`; the default value falls on the safe side | Read every equation edge that reads a counter | [§6] |
| J5 | A suite showing several traces at 1 of 2 was RE-RUN at 3 reps before anything was changed | The two run reports side by side | [§22] |
| J6 | Every question the caller heard matches the quoted sentence word for word | Read the AGENT lines of the last few real calls | [§4] |
| J7 | No extract description contradicts the client's stated rule or another field describing the same fact | Read each description against the client thread | [§6] |
| J8 | After any run that crashed or timed out, `retell_chat.py cleanup` was run | Its output says 0 chat agents remain | [§22] |
| J9 | Every probabilistic trace result is reported as a PAIR: the same trace, at the same rep count, against the export being replaced | The two run reports side by side. A red verdict alone is not a decision | [fix 37] |
| J10 | After changing a rule inside a node instruction, the WHOLE instruction was searched for templates, format lines, and worked examples stating the old rule | Read the node instruction end to end, not just the block you edited | [fix 38] |
| J11 | No caller-facing sentence has two sayers unless the residual double-say rate was measured and written into the changelog | `flowlint.py --line` CANNOT see this when one sayer is a global node | [fix 39] |
| J12 | No routing decision reads a SIP header without proof the header survives the WHOLE call path, measured on a real call over the real route | The raw `diversion` value from a real multi-hop call, not a one-hop one. A forwarding PBX rewrites it | [lesson 49] |
| J13 | No confirmation sentence bundles two facts | Read every readback line. A "yes" to "Thanks, Tim. Just to confirm, six two six..." answers the NUMBER only, and the name rides through wrong | [§18] |
| J14 | No field is treated as verified because a readback happened | Read every confidence rule and every extract description. A silent caller has confirmed nothing | [§18] |

## Reporting

For every failed check, record:

1. The check number.
2. The node or edge, by name **and** id, and the direction.
3. What the export actually shows.
4. What it should show.

A finding that does not survive a full look at the node and its edges is not a
finding.
