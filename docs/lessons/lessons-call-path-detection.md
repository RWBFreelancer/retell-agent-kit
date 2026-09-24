# Lessons: you cannot detect a call path from a header a PBX has already erased

Recorded 2026-09-02, while wiring the Retell-to-the downstream owner handoff.

Read this before promising anyone that a Retell call can report *which line the
caller originally dialled*.

---

## Lesson 49 - a forwarding PBX rewrites the Diversion header, and no Retell feature can recover it

### What we promised, and what we shipped against

`docs/handoff-fields.md`, written 2026-08-23, told the downstream owner this:

> **Do not use `to_number`.** It is always `+18055154026`, the Retell number.
> The number the caller actually dialled is in the SIP `diversion` header.

That was true for the calls it was measured on, and it is still true for **some**
calls. It is not true in general, and the difference is invisible until you look
at a call that took more than one hop.

the downstream owner built his entire receiving end on it. So did
`transforms/example_dual_send.py`.

### The measurement that broke it

the client made a deliberate ENGAGE test call on 2026-09-02 and described the route
himself:

    XXX-XXX-XXXX  ->  XXX-XXX-XXXX (ENGAGE)  ->  XXX-XXX-XXXX (his the phone forwarding service)  ->  Voice Agent

The call is `call_xxxxxxxxxxxxxxxxxxxxxxxxxxx`, a second example agent v31, 2026-09-02 06:12.
Its entire routing evidence:

    to_number : +18055154026
    diversion : <sip:+18055154026@twilio.com>;reason=unconditional

`+18055154026` is the Retell number. **Neither the ENGAGE number nor the client's
the phone forwarding service number appears anywhere in the call object.** The two hops that
matter left no trace at all.

### The pattern, across 60 real calls

Pulled with `POST /v2/list-calls`, 2026-09-02:

| How the call reached Retell | What `diversion` holds | Usable? |
|---|---|---|
| A the call tracking service tracking line forwards straight to Retell | the tracking number | **yes** |
| Anything hops through the phone forwarding service first | the Retell number | **no** |

Every usable value seen was a tracking line already on the client's approved list:
XXX-XXX-XXXX, XXX-XXX-XXXX, XXX-XXX-XXXX, XXX-XXX-XXXX, XXX-XXX-XXXX,
XXX-XXX-XXXX, XXX-XXX-XXXX. **Not one ENGAGE number appeared in 60 calls**, which
is exactly what `handoff-fields.md` line 48 warned about and nobody chased.

### Why, and why it is not a Retell fault

the phone forwarding service treats a forwarded call as a **brand new call**. It writes its own
Diversion header naming the number it is dialling, which is the Retell number,
and the original one is gone. Its own community documents the same behaviour for
caller ID on queue forwards:

> "when an incoming call goes to a call queue and is then answered and forwarded
> to another user, it treats the call as a new call and strips caller ID,
> replacing it with the main company number"

Retell is passing through faithfully what it was handed. There is nothing to fix
on the Retell side.

### The inbound webhook does NOT rescue this. It was checked.

The obvious next idea is Retell's inbound call webhook, which fires before the
agent answers (`/features/inbound-call-webhook`). It sends `from_number`,
`to_number`, and `custom_sip_headers`, and it accepts a reply within 10 seconds
that can `reject` the call, set `dynamic_variables`, or `override_agent_id`.

`custom_sip_headers` forwards `X-` headers plus an allowlist: `Diversion`,
`History-Info`, `P-Asserted-Identity`, `User-to-User`. That allowlist was
genuinely broken for a while; Retell staff closed it on 2026-07-16 with "Its
fixed now"
(`community.retellai.com/t/diversion-sip-header-stripped-missing-from-custom-sip-headers-webhook-payload/3295`).

**It still does not help.** The webhook hands you the same header, a few seconds
earlier. We are not failing to READ the data. The data was never sent.

### The general rule

**A webhook, an earlier hook, or a different field cannot recover information a
carrier or PBX deleted upstream.** Before designing anything on a routing header,
prove the header survives the WHOLE path, hop by hop, on a real call over the
real route. A header measured on a one-hop call says nothing about a two-hop one.

The corollary, and it is the useful half:

**Route identity belongs on something the forwarder cannot rewrite.** The number
Retell was reached on (`to_number`) is exactly that. Give each path its own
inbound number and the question answers itself, with no header, no parsing, and
nothing to strip.

### What to do instead

Ranked. The first one is the only one that is certain.

1. **One Retell number per path.** ENGAGE on one, the direct line on another.
   `to_number` then reports the path with no inference. Costs a number.
2. **A SIP middleware that copies Diversion into `X-Diversion-Number` before
   Retell sees it.** The workaround in the community thread above. Needs a box in
   front of Retell, and it still cannot help when the phone forwarding service never sent the
   value.
3. **Never say `the call tracking service` unless a known tracking line was actually seen.** This is
   free and it is honest. A path we cannot identify must report that it cannot be
   identified, not a guess. A wrong `the call tracking service` sends the receiving side hunting for a
   record that does not exist.

### What was wrong before

The old code took the first `+1` out of `diversion` and mapped anything that was
not an ENGAGE number to `the call tracking service`. On the ENGAGE test call that produces
`dialed_number: +18055154026, call_path: the call tracking service`, which is wrong twice over: it
reports the Retell number as the dialled line, and it claims a the call tracking service path on a call
that never touched the call tracking service.

the downstream owner had also planned around a hop-ordering problem, on the assumption the
header would carry both numbers and he would have to pick the right one. There is
no ordering problem, because there is only ever one value and it is the wrong
one. An assumption two people shared, and neither had measured.

### Checklist line

`qa-checklist.md` J12.
