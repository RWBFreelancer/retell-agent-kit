# Lessons about what a long prompt actually costs on Retell

2026-08-27. Rey asked for a lower cost per call on a second example agent. The first hour went
into counting words. The counting was the wrong model, and Retell's own billing
page and API say so.

Read this before anyone proposes another prompt trim.

## READ FIRST: Lesson 36 below is WRONG about what the surcharge costs. Corrected 2026-09-21.

Measured on 397 real a second example agent calls, 2026-07-31 to 2026-09-21, from the
`call_cost.product_costs` Retell returns on each call.

**The surcharge does NOT scale the whole bill.** Every other product on a call
(voice engine, TTS, telephony, background voice cancellation, guardrail, and the
LLM line itself) is billed on the plain call duration. The surcharge is its own
line item, `llm_token_surcharge`, and it fits this formula on every call:

    surcharge (cents) = duration_seconds x (average_tokens_per_request / 4000 - 1) x 0.075

`0.075` cents a second is the `gpt_4_1` LLM rate. Mean miss 0.06 cents, worst
0.76 cents, across all 214 calls that were over the line. It uses the
**average** per request (`llm_token_usage.average`), not the peak.

So it only ever scales the LLM line, never the voice, TTS or telephony lines.
Lesson 36's "a 1.3x scaling is 30% on the whole bill" is not what Retell bills
today. Retell's own page does not say which number it uses; the bills do.

**What that is worth:**

| | Over 52 days, 397 calls |
|---|---|
| Whole bill | $74.74 |
| LLM line, flat per minute, does not move with tokens | $18.65, 24.9% |
| Token surcharge | $3.89, **5.2%**, about **$2.22 per 30 days** |
| Saved by 500 tokens off every request | $1.71, under $1 per 30 days |
| Saved by removing the surcharge entirely | $3.89, $2.22 per 30 days |

**Tokens also barely move speed.** 181 calls with 5+ requests: LLM p50 latency
correlates 0.20 with average tokens, about **65 ms per 1,000 tokens**. Median
LLM p50 is 604 ms under 4,800 tokens and 681 ms at 5,400 and over. The slow
parts of this agent are elsewhere; see `docs/lessons-silent-node-latency.md`.

**The general rule.** Read `call_cost.product_costs` on real calls before
pricing any prompt work. At this traffic, a prompt trim can save at most about
$2 a month and has broken behaviour four times out of four (lesson 25). Say that
number first. A trim is only worth testing if traffic grows a lot, or if the
point is something other than cost.

**Also found while measuring:** `flowlint.py` scores every
`extract_dynamic_variables` node as 1 word. It does not count variable
descriptions, yet each extract node is its own LLM request. `Capture Check` is
1,083 words, `Intake Gate Check` 527, `Call Type Check` 188. So flowlint's
"always-on" and node packages undercount the requests those nodes make.

## Lesson 36 - Retell bills a long-prompt surcharge above 4,000 tokens, and it scales the WHOLE call

Source: [Exceptions to Our Per-Minute Pricing](https://docs.retellai.com/accounts/billing-exceptions).

    Scaling Factor  = Prompt LLM Tokens / 4,000
    Billed Duration = Original Duration x Scaling Factor (rounded up)

Retell's own worked example: a 60-second call using 4,800 tokens is billed as
72 seconds.

What counts toward the token total, quoted from that page:

- global prompt
- functions (tool descriptions)
- state / node prompt
- **transcript between agent and user**
- tool call history and results
- retrieved knowledge base content

**Two things follow, and both were missed by every trim attempt in this repo.**

1. **The surcharge scales BILLED DURATION, not just the LLM line.** Every
   per-minute product on the call is multiplied: voice engine, TTS, telephony,
   background voice cancellation, guardrail. A 1.3x scaling is 30% on the whole
   bill, not 30% of the ~22% that LLM represents.

2. **Below 4,000 tokens the scaling factor floors at 1.0, so a cut is worth
   NOTHING.** Above it, a cut is worth real money, proportionally. This is a
   threshold, not a slope. Before proposing a trim, first find out which side
   of 4,000 the agent is on. A saving of 300 tokens is worth everything at
   4,300 and nothing at 3,900.

**The general rule.** A prompt-size change is a billing question with a
threshold in it, not a "smaller is cheaper" question. Get the agent's real
token number first, then decide whether any cut is worth testing at all.

A Retell staff answer in
[Token Surcharge Calculation](https://community.retellai.com/t/token-surcharge-calculation/2814)
gives the same formula against 3,500. The docs now say 4,000, described
elsewhere as a recent increase. Use 4,000 and re-check the page; the number
has moved once already.

**Re-checked 2026-08-29.** The billing page still says 4,000. The threshold
question is settled for now, and the page still gives the same worked example: a
60-second call at 4,800 tokens is billed as 72 seconds.

The same re-check pinned the full input list, which matters more than the
threshold does. Retell counts six things, quoted verbatim:

> global prompt, functions (tool descriptions), state / node prompt, transcript
> between agent and user, tool call history and results, retrieved knowledge base
> content

Source: <https://docs.retellai.com/accounts/billing-exceptions>.

Two of those six are outside your control once the call starts. The transcript
grows every turn, and so does tool call history. That is the mechanism behind
Lesson 39 below, and it is why a call that starts under the threshold can cross
it partway through.

## Lesson 37 - `llm_token_usage` on a real call is the measurement. Stop estimating.

`GET /v2/get-call/{call_id}` returns:

```json
"llm_token_usage": {"values": [...], "average": 4621, "num_requests": 15}
```

That is the authoritative number, per request, for a real call. Nothing in this
repo was reading it. Sixty recent a second example agent calls, read on 2026-08-27:

| Call shape | requests | average tokens | peak tokens | scaling on peak |
|---|---|---|---|---|
| caller hangs up in the greeting | 1 | 2,443 | 2,443 | under threshold |
| short call | 2-3 | 2,861 - 3,737 | 3,279 - 5,170 | at the line |
| completed call | 10-18 | **4,044 - 5,274** | **5,066 - 7,142** | **1.27x - 1.79x** |

**So a second example agent pays a real surcharge on every completed call, and none at all on
a short one.** The long calls are the ones being taxed, and they are also the
ones that collect the intake.

**The general rule.** Before any prompt work, pull `llm_token_usage` across
thirty real calls and read the distribution. One number from one test call is
not the picture: this agent ranges from 0.61x to 1.79x depending only on how
long the caller stayed.

## Lesson 38 - on this flow, flowlint's word count IS the token count

Measured, not assumed. A caller who hung up during the greeting produces
exactly one LLM request, so its token count is the whole per-turn prompt with
no transcript in it:

    always-on (flowlint)      2,136 words
    Greeting node package       304 words
    -------------------------------------
    total                     2,440 words

    llm_token_usage.values    [2,443]

2,440 words against 2,443 tokens. Near enough 1 : 1.

The usual 1.33 tokens-per-word rule is wrong here, and it would have
overstated the prompt by a third. The cause is the writing style this repo
already enforces: short common words, `# HEADER` lines, no markdown, heavy
repetition of the same phrases. Those tokenise close to one token per word.

**The general rule.** `flowlint.py`'s "always-on" and node package numbers can
be read directly as tokens on this flow. Confirm the 1:1 again after any large
rewrite, using a one-request call, before trusting it.

**And the technique.** To measure a prompt's true size with no transcript in
it, find a call with `num_requests == 1`. That is the cleanest instrument
available and it costs nothing.

## Lesson 39 - the transcript is most of the growth, and you cannot cut it

a second example agent's per-turn prompt is 2,136 always-on + roughly 250-2,100 for the node.
Yet completed calls average 4,000-5,300 tokens per request. The difference is
the conversation history, which grows every turn and is charged every turn.

So on a 15-request call, roughly:

    2,136   always-on          - cuttable, and charged on EVERY request
      ~800  active node        - cuttable, charged only on its own requests
    ~1,700  transcript so far  - NOT cuttable
    ------
    ~4,600  average

**Two consequences for where to spend effort.**

1. **An always-on word is worth many times a node word.** Cutting one word of
   always-on lowers every request by one token. Cutting one word from
   `Ask Vehicle` lowers only the one or two requests spent in that node. On a
   15-request call that is a 15:1 ratio. `flowlint`'s DUPLICATE PARAGRAPHS
   report lists blocks repeated across eight Ask nodes; they are charged once
   per turn, not eight times, so that report is not a savings list.

2. **The target is a number, not a percentage.** To pull a 4,600-token average
   under 4,000 needs about **600 tokens** off the per-turn prompt. On a second example agent
   the only single block that big is the 887-word `global_prompt`. The three
   `global_node_setting` blocks together are 1,249 words and are almost
   entirely the product of measured fixes (T-AB, T-AE, T-AF, T-AI), which
   lesson 32 says are the most dangerous words in the flow to touch.

**The general rule.** Work out the token target first, then check whether any
block you are allowed to touch is big enough to reach it. If it is not, say so
before spending test money, instead of delivering a 1% cut that had no chance
of crossing the threshold.

## Lesson 40 - measure the SUPPLY of removable words before planning a cut

2026-08-27. The token arithmetic said always-on was the place to cut: it is
charged on every request, so one word there is worth about fifteen words of node
text on a 15-request call. The arithmetic was right. The words were not there.

`transforms/b_trim_always_on_v2.py` compressed the wording in place across
`# Style`, `# Never`, `# Coverage`, `# Routing`, the Guardrails condition, and
two duplicate positive fine-tune examples. It removed **48 words** out of 2,136.

Then the supply was measured directly:

| Block | Words | Sentences | Words per rule |
|---|---|---|---|
| `global_prompt` | 887 | 48 | **18.5** |
| the three global conditions | 614 | 21 | **29.2** |

112 of the global prompt's words are inside quotes, so they are contractual and
cannot be touched at all.

Fifty-odd distinct rules at 18.5 words each is already dense technical prose.
There is no padding, no preamble, and no repetition worth the name. Compression
reaches about 5% of it; the other 95% IS the rules, and removing a rule is a
behaviour change.

**This also re-reads lesson 25.** Those four failed trims were not only unlucky.
Three of them had to MOVE or DELETE precisely because there was nothing to
compress. The prompt was already at its floor before anyone started.

**The general rule.** Before planning a prompt reduction, measure words per
rule and the share inside quotes. Under about 20 words per rule the block is
already compressed, and the only remaining lever is deleting rules. Say that
before promising a percentage, not after building the transform.

**And the related rule about testing.** A change smaller than the test suite's
own noise cannot be checked. T-P on this flow flaps by three runs in eight with
no change at all, so a 48-word change is unmeasurable at any rep count.
Do not spend test money to produce a number that cannot mean anything; report
the size and say why it was not run.

## What this means for lesson 25

Lesson 25 in `docs/lessons-v24-simplification.md` says removing text from the
global prompt costs behaviour, proved four times by measurement. That still
stands, and nothing here withdraws it.

What is new is the other half of the trade. Those four attempts were judged
only on "did the trace still pass", and the saving they were chasing was never
priced. Now it can be: always-on is charged on every request, the threshold is
4,000 tokens, and a second example agent's completed calls sit at 1.27x to 1.79x.

**So the honest framing for the next attempt is a trade, not a tidy-up.**
Cutting the global prompt is worth real money on every long call AND has broken
behaviour four times out of four. Both halves are now measured. That is a
decision for Rey and the client, not a housekeeping task.
