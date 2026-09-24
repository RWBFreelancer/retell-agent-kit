# The free test fixture in a live n8n export, and the way it lies

2026-09-01. `Retell Voice AI Phase 1 - Recap Only`, the dual-send to the downstream owner.

Two lessons, one useful and one dangerous, and they arrive in the same object.

---

## The useful half: `pinData` is a real call you already have

An n8n export carries a `pinData` block. On this workflow it holds a **complete
real `call_analyzed` webhook body**, headers and all, from an actual call:

    pinData -> "Retell call_analyzed" -> [0].json.body

Call `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`. A real caller, a real transcript, real
`custom_analysis_data`, real `collected_dynamic_variables`.

That is a free, high-fidelity fixture for any n8n **code node**, and it costs
nothing. No Retell call, no sandbox, no money.

The technique, which took about two minutes:

1. Pull the `jsCode` string out of the node in the export.
2. Pull `pinData[...][0].json` out of the same export.
3. Emulate the one or two n8n globals the node uses. For `Build the downstream owner Payload`
   that is just `$(nodeName)`, returning `{ item: { json: body } }`.
4. `new Function('$', src)` and run it under `node`.

That verified all 44 output keys of the dual-send payload against
`docs/handoff-fields.md` before anything was imported to n8n, and it caught that
two documented names were absent for a *correct* reason: `item_category` and
`service_area_status` are in that document's **fields removed** table, not its
field list.

Use this before importing any code-node change. `Guard and Normalize`,
`Attach Drive Links` and `Build the downstream owner Payload` are all testable this way. The
2026-08-31 session used the same method on `Attach Drive Links`.

---

## The dangerous half: the pinned call may be a web call

The pinned body on this workflow is `"call_type": "web_call"`.

A web call has **no `from_number` and no `to_number`**. So the run came back
green with:

    caller_number   ""
    dialed_number   ""
    call_path       "the call tracking service"

Every one of those is the fallback branch. `call_path` is computed as:

```javascript
const dialedNumber = divMatch ? divMatch[0] : s(call.to_number);
const callPath = ENGAGE_NUMBERS.includes(digits(dialedNumber)) ? 'ENGAGE' : 'the call tracking service';
```

With no diversion header and no `to_number`, `dialedNumber` is `""`, which is
not in `ENGAGE_NUMBERS`, so `call_path` falls to `'the call tracking service'` — the default, reached
by accident rather than by matching anything.

**The run proved the 44-field shape and nothing whatsoever about the header
parsing.** A reviewer skimming "44 keys, all correct" would reasonably conclude
the ENGAGE routing was verified. It was not. It was tested separately, by hand,
in an earlier session.

### The general rule

A fixture exercises only the branches its own data reaches. A green run on one
fixture is evidence about that fixture's path, never about the paths it happens
to skip. **Before trusting a fixture, read what is missing from it, not just
what came out of it.**

The tell here was one field: `call_type: "web_call"`. Everything else about the
body looked like a production phone call.

This is the same defect class as
[lessons-green-verdict-blindness.md](lessons-green-verdict-blindness.md) — a
pass that covers less than it appears to — arriving through a different door.
There the blind spot was everything the trace's `say_times` list did not name.
Here it is every branch the fixture's own data cannot reach.

### What to do about it

When a payload's behaviour depends on fields the fixture lacks, either:

- Synthesise the missing fields onto a copy of the real body and re-run. A web
  call body plus a `to_number` and a `diversion` header is a valid phone-call
  fixture, and it is still real data everywhere else.
- Or state plainly, in the same breath as the green result, which branches the
  run did not touch.

Saying "44 of 44 fields correct" and stopping is how a green verdict becomes a
false one.

---

## Where this was written up

`docs/edit-n8n-dual-send-2026-09-01.md` (removed 2026-09-11; read it with `git show da55696:<path>`), under "Measured, not assumed: the
payload", carries the caveat beside the result so the two cannot be read apart.

---

# The same trap, in a real test call

2026-09-01, later the same day. Call `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`,
a second example agent v31, 104 seconds.

the client had promised a test call on an ENGAGE line. A call arrived. It looked
like the one we were waiting for. It was not.

    from_number   +19492386338    the client's main the phone forwarding service line
    to_number     +18055154026    a second example agent's Retell number
    diversion     <sip:+18055154026@twilio.com>;reason=unconditional

No ENGAGE number anywhere. He rang the Retell number directly and gave his
direct line, XXX-XXX-XXXX, as the spoken callback. Three different numbers on
one call, and it is easy to grab the wrong one.

## A test call only proves the route it actually travels

The header we needed to see is created by the forwarding hop. A call dialled
straight to the Retell number never makes that hop, so its `diversion` header
carries the Retell number and nothing else.

**To observe a routing header, the call has to traverse that route.** Asking
for "a test call" is not specific enough. Ask for a call dialled *to* the
particular line under test.

This is the fixture lesson again in a different costume. Above, the fixture was
a web call missing `from_number` and `to_number`. Here it is a phone call that
skipped the hop that produces the evidence. Both ran green. Neither proved what
it appeared to.

## Two guards, two different scopes, and only one covers the handoff

The same call exposed a real gap.

`Guard and Normalize` holds `COMPANY_NUMBERS`, the client's four the phone forwarding service
lines. When `from_number` matches, it rewrites `caller_id_number` to
'Company Transfer' so the recap email never shows an internal line as the
customer.

**That guard does not protect the handoff.** `Build the downstream owner Payload` reads the
raw webhook body on purpose, because the downstream owner needs the true `from_number` to
match his own records. So the masking is bypassed by design, and the downstream owner
receives `+19492386338` as `caller_number`.

Had the dual-send been live, this call would have gone to the downstream owner looking like
an ordinary caller on the client's own line.

The general rule: **a guard protects the path it sits on, not the system.**
When a second consumer is added downstream of a normalising node, list every
protection that node performs and ask, one at a time, whether the new consumer
inherits it. Here the answer was no, for a deliberate and correct reason, and
the deliberateness is exactly what made it easy to miss.

the client gave the downstream owner his three personal numbers on 2026-09-01. The four
the phone forwarding service numbers went to Rey on 2026-08-30, for the n8n guard. Nobody has
confirmed the downstream owner holds all four.

## Do not read a test caller's behaviour as a defect

The transcript showed the agent cut off mid-question, resuming with a sentence
fragment after the caller talked over it twice. Read cold, that is the
interruption defect class this repository has chased before.

It was not. Rey: the client cut the call off deliberately. He was testing, not
using.

**Before filing a defect from a transcript, establish who the caller was and
what they were trying to do.** A test caller pushes on things a real caller
never touches, and their behaviour is not evidence about the product. The cost
of getting this wrong is a session spent fixing something that was never
broken.

## A fixture you invented agrees with the code you invented it for

2026-09-05. the downstream owner asked for the handoff-failure email to carry the refusal
sentence in plain words at the top. `transforms/n8n_readable_failure_email.py`
adds a code node that digs that sentence out of the error.

It was tested against six error shapes written from imagination: an AxiosError
with an escaped JSON `description`, a `response.data` object, a 401, a timeout,
a 502, and a junk string. **All six passed.** The change was reported as tested
and the file was handed over.

Then n8n's public API produced ten REAL failures, executions 1174 to 1213.
**All ten failed.** Every one printed the whole unreadable blob, which is the
exact fault the node existed to remove.

Two things were wrong, and neither was guessable:

- The real reason lives in a `problems` ARRAY, not in any of `message`,
  `error`, `reason` or `detail`. The parser had no array branch at all.
- n8n's HTTP Request node reports a rejected POST as
  `error.message = '400 - "{\"status\":\"rejected\",\"problems\":[...]}"'`.
  The status is a text prefix, and the body is a JSON string that was
  JSON-encoded a second time. Nothing in the invented fixtures had either
  shape, because the author did not know either shape existed.

**The rule.** A fixture you wrote yourself tests your idea of the world, not
the world. It cannot fail in a way you did not already think of, so a green run
on invented fixtures is worth close to nothing. Before claiming a parser,
guard, or classifier works, get real inputs. This repository already had ten,
sitting in n8n, free.

**Where the real inputs are, so nobody has to search again.** The n8n Cloud
public API. `N8N_API_KEY`, `N8N_BASE_URL` and `N8N_WORKFLOW_ID` are in `.env`.

```
GET {base}/api/v1/executions?limit=60&workflowId={id}
GET {base}/api/v1/executions/{n}?includeData=true
```
header `X-N8N-API-KEY: {key}`

An execution's `data.resultData.runData` is keyed by NODE NAME. A node with an
error output puts the failing item in `main[1]`, and `main[1][0].json.error`
is what the next node receives. Read `main[1]` of the FAILING node. Reading the
alert node's own entry gives you its Gmail receipt, not the error.

The same call answered a second question for free: execution 1217 is a live
v37 call that proves what the fixed "it is personal" path produces. No sandbox
run was needed, and no sandbox run could have produced it, because post-call
analysis does not run in the text sandbox.

Related: the pinned `call_analyzed` body above is the same trap from the other
side. That fixture is real, and it still lies, because it is a web call.

## 2026-09-11: anchor on the thing you mean, not the nearest thing that looks like it

`n8n_apply_service_request_null.py` had to insert a helper at the TOP LEVEL of
`Build the downstream owner Payload`, after `cad` and `yn` exist and before the payload object
is built. The first version found the insertion point like this:

    idx = code.index("  // 34 intake fields from post-call analysis.")
    ret = code.rindex("return [", 0, idx)      # nearest return ABOVE the anchor

`Build the downstream owner Payload` has TWO `return [` statements. Line 215 is the real one,
`return [{ json: payload }];`. Line 85 is `return [];` inside the test-number
guard, which drops Rey's own line before anything else runs.

`rindex` found line 85. The helper landed INSIDE that `if` block, so the `const`
was scoped to a branch that almost never executes, and `serviceRequestValue`
would have been undefined at the real return. **Every single call would have
thrown a ReferenceError**, and the handoff would have stopped dead.

**The dry run caught it**, because `flowapply`-style tools in this repo print a
unified diff and stop. Reading that diff is the whole point; it showed the
helper wedged above `return [];` in the wrong block.

**The fix.** Anchor on the statement that actually opens the payload, matched as
a two-line literal so it cannot collide:

    ANCHOR = ("// --- the payload ---------------------------------------------------------\n"
              "const payload = {")

**The general rule.** Never locate an insertion point by walking backwards to
the nearest token of a common shape. `return`, `}`, `const` and `//` all repeat.
Anchor on a literal string that appears exactly once, and assert the count is 1
before touching anything.

**And run it.** A syntax check would NOT have caught this: the broken version
parses fine. `node --check` said SYNTAX OK on it. What caught it was reading the
diff, and what would have caught it second was executing the node against a real
`call_analyzed` body, which this file already recommends and which was done
afterwards on four `service_request` shapes:

    listed missing + analysis false  -> null
    NOT listed + analysis false      -> "no"
    NOT listed + analysis true       -> "yes"
    recap_never_ran only             -> "no"

A scoping bug is invisible to a parser and obvious to one execution.

## 2026-09-14: a new helper name can already be taken, and `const` twice throws on every call

`tools/n8n_apply_wrong_number_email.py` first added this to `Guard and Normalize`:

    const isYes = v => v === true || ['yes', 'true'].includes(...);

`Guard and Normalize` is 572 lines and already declares `isYes` at line 165
(`const isYes = v => yn(v) === 'yes';`). A second `const` of the same name in
the same scope is a SyntaxError, so n8n would have thrown before the first line
ran, on every call. The recap email would have stopped for all calls, not only
wrong numbers. The tool's own dry run printed a clean-looking diff, because the
diff only shows the lines added, never the name clash 300 lines away.

`node --check` on the node wrapped in `async function __n(){ ... }` caught it
before anything was applied: `Identifier 'isYes' has already been declared`.
Renamed to `wnYes`, and the tool now refuses if `wnYes` already exists.

### The general rule

Before adding any top-level `const`, `let` or `function` to an n8n code node,
search the WHOLE live node for that exact name. A tidy diff proves nothing
about names declared elsewhere. Then run `node --check` on the full node, not
on the snippet.

## 2026-09-15: `$('Node').first()` read the empty error output

### What happened

`tools/n8n_apply_alert_email_fixes.py` (2026-09-11) put the posted body back in
the handoff failure alert with `$('Build the downstream owner Payload').first().json`. Every
alert since then printed "Could not read the posted body: Cannot read
properties of undefined (reading 'json')". the downstream owner reported seven in a row,
the client CRM group, 2026-09-15 2:45 AM. Executions 1475 and 1479 show it.

### Why

n8n docs, "Output of other nodes": if `branchIndex` is not given, `first()`
uses the output that connects the named node to the node running the code.
`Build the downstream owner Payload` has `onError: continueErrorOutput`, and its link to
`Explain Handoff Failure` is its ERROR output, index 1. On a the downstream owner refusal the
payload node succeeded, so output 1 is empty and `.first()` is undefined. The
payload sits on output 0.

The 2026-09-11 harness stubbed `$()` with one output, so it could not see this.
It passed and the alert shipped broken.

### The fix

`.first(0)`. `tools/n8n_apply_posted_body_first0.py`. A harness that models
both outputs and the linked index reproduces the live error with the old code
and posts the real body with the new one.

### The general rule

When a code node reads another node with `$('X').first()`, `.all()` or
`.last()`, check which output of X links to this node. If it is not output 0,
or X has an error output, pass the branch index. A harness `$()` stub must model
every output of X and the linked one as the default, or it will pass code that
throws live.

Also: `Guard and Normalize` calls `$getWorkflowStaticData('global')` for its
duplicate guard. A harness must stub it with a fresh object per run, or every
body throws (first harness run, 2026-09-15, 40 of 40).
