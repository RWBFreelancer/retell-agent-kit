#!/usr/bin/env python3
"""Static check of a Retell single-prompt (or multi-prompt) agent. NO API KEY.

WHAT THIS IS FOR

A conversation flow can be linted structurally: nodes, edges, dead ends. A
single-prompt agent has no structure to lint. It is one block of prose, and
almost every defect in it is invisible until a real caller hears it. This
tool reads the prose and reports the defects that are findable on paper.

It runs fully offline. It is the tool to reach for when there is no API key,
when all you have is a prompt in a document, or before spending a cent on a
test call.

WHAT IT CHECKS, AND WHY EACH CHECK EXISTS

  A. Structure     Retell's prompt engineering guide prescribes a sectional
                   prompt: Identity, Style Guardrails, Response Guidelines,
                   Task, Objection Handling. A prompt missing Identity or
                   Task drifts. docs.retellai.com/build/prompt-engineering-guide

  B. Speech        The model speaks what it writes. "1/15" is read as "one
                   slash fifteen". "$1,250" as "dollar one comma two five
                   zero". Retell's guide: return dates in spoken form. This
                   check finds every literal that will be mispronounced.

  C. Size          Retell surcharges an agent above roughly 4,000 LLM tokens
                   and scales the whole billed duration. Below that line a
                   trim is worth nothing; above it, real money. Characters
                   over four is the working estimate.

  D. Turn-taking   One question per turn. Two questions in one sentence make
                   a caller answer one and drop the other, and the agent
                   then believes it asked both.

  E. Safety        A voice agent that guarantees, promises, quotes a price,
                   or diagnoses creates liability. It must also be told what
                   to do when it does not know, and how to end the call.

  F. Variables     Every {{variable}} the prompt reads must be supplied, or
                   the caller hears the braces.

  G. Examples      An example outranks the rule it contradicts. Example
                   blocks are listed so a human re-reads them after any
                   rule change. This is the single most common cause of an
                   agent ignoring a rule that is plainly written above it.

WHAT IT CANNOT PROVE

It cannot prove the agent behaves. Only a call can do that. A clean report
here means the prompt is well formed, not that it works. Run
`sp.py chat` next.

INPUT

Accepts any of:
    a .md / .txt file holding the prompt
    a Retell LLM export .json (reads general_prompt, begin_message, states)
    a full agent .json that embeds one of the above

Usage:
    python promptlint.py my-prompt.md
    python promptlint.py llm.json
    python promptlint.py llm.json --json
    python promptlint.py my-prompt.md --strict     # warnings become failures
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

TOKEN_SURCHARGE = 4000       # Retell's billed-duration surcharge line
TOKEN_QUALITY = 2000         # Amplify Voice's real-time quality ceiling
CHARS_PER_TOKEN = 4          # working estimate for English prose

# Two accepted section structures. Retell's own prompt engineering guide
# prescribes five sections; the Amplify Voice practitioner method prescribes
# eight. They say the same thing under different names, so the linter detects
# which one is in use and grades against THAT one, instead of demanding both.
# See reference/amplify-voice-prompt-engineer.md for the mapping table.
#
# Each entry is (label, a loose heading regex). Loose, because people write
# "## Identity", "# ROLE", and "Identity & Purpose" and all mean the same.
RETELL_SECTIONS = [
    ("Identity",           r"identity|role|persona|who you are|about you"),
    ("Style Guardrails",   r"style|tone|voice|guardrail|personality|how you speak"),
    ("Response Guidelines", r"response guideline|response rule|formatting|"
                            r"speech|how to respond|output|instruction"),
    ("Task",               r"task|steps|instruction|workflow|process|stage|"
                           r"conversation flow|script|objective|goal|routing|"
                           r"call flow|procedure"),
    ("Objection Handling", r"objection|edge case|difficult|pushback|"
                           r"unhappy|escalat|if the caller|error handling|"
                           r"fallback|unknown|important reminder"),
]

AMPLIFY_SECTIONS = [
    ("Role and Objective", r"role|objective|identity|purpose"),
    ("Personality",        r"personality|style|tone|voice|persona"),
    ("Context",            r"context|background|situation|what you know"),
    ("Instructions",       r"instruction|rule|guideline|behaviour|behavior"),
    ("Stages",             r"stage|step|conversation flow|call flow|"
                           r"process|script|procedure|routing"),
    ("Example Interactions", r"example|sample dialog|sample interaction"),
    ("Important Reminders", r"important reminder|reminder|critical|"
                            r"edge case|never|do not|must not"),
]

# Sections that are not optional under either structure.
CRITICAL = {"Identity", "Task", "Role and Objective", "Stages"}

# ---- B. speech formatting. Each is (id, regex, message, example fix) ----
SPEECH_CHECKS = [
    ("date-slash", r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
     "numeric date is read as 'one slash fifteen'",
     "write 'January fifteenth'"),
    ("money", r"\$\s?\d[\d,]*(?:\.\d+)?",
     "currency symbol is read literally",
     "write 'one hundred and twenty dollars'"),
    ("big-number", r"\b\d{1,3}(?:,\d{3})+\b",
     "a comma inside a number is read as a pause or as 'comma'",
     "write the number in words"),
    ("phone", r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",
     "a phone number in digits is read at machine speed",
     "space the digits, or tell the agent to read them one at a time"),
    ("time-colon", r"\b\d{1,2}:\d{2}\s?(?:[ap]\.?m\.?)?\b",
     "a colon time can be read as 'nine colon zero zero'",
     "write 'nine o'clock' or 'nine thirty in the morning'"),
    ("percent", r"\b\d+\s?%",
     "the percent sign is read inconsistently",
     "write 'twenty percent'"),
    ("url", r"\b(?:https?://|www\.)\S+",
     "a URL is read character by character",
     "spell it out in words, or do not have the agent say it"),
    ("email", r"\b[\w.+-]+@[\w-]+\.[\w.]+\b",
     "an email address is read badly",
     "write 'name at company dot com'"),
    ("abbrev", r"\b(?:Dr|Mr|Mrs|Ms|St|Ave|Rd|Blvd|Apt|approx|etc|vs|Inc|Ltd)\.",
     "an abbreviation may be read as letters",
     "write the full word"),
    ("range-dash", r"\b\d+\s?[-–]\s?\d+\b",
     "a dash between numbers is read as 'minus'",
     "write 'between two and four'"),
    ("time-24-7", r"\b24/7\b",
     "'24/7' is read as 'twenty four slash seven'",
     "write 'twenty four hours a day, seven days a week'"),
]

# ---- E. safety. Phrases a voice agent should not commit to. ----
RISK_PHRASES = [
    ("guarantee",  r"\bguarantee(?:d|s)?\b"),
    ("promise",    r"\bpromise(?:d|s)?\b"),
    ("definitely", r"\b(?:definitely|certainly) (?:will|can)\b"),
    ("diagnose",   r"\bdiagnos(?:e|is|ing)\b"),
    ("quote-price", r"\b(?:the price is|it will cost|the cost is|we charge)\b"),
]

# ---- E. rules a prompt is incomplete without.
# Each entry is (id, regex, why it matters, severity). The four
# marked FAIL break a call outright. The rest degrade it.
REQUIRED_BEHAVIOURS = [
    ("unknown-answer",
     r"do not (?:know|make|guess|invent)|don't (?:know|make|guess|invent)|"
     r"never (?:make up|invent|guess)|if you are unsure|if you do not know|"
     r"if you don't know|not sure",
     "no rule for what to say when the agent does not know. "
     "Without it the model invents an answer.", "FAIL"),
    ("end-call",
     r"end (?:the )?call|hang up|end_call|say goodbye|finish the call|"
     r"terminate the call|end the conversation",
     "no rule for how and when to end the call. "
     "Calls then run until the caller hangs up, and you pay for it.", "FAIL"),
    ("one-question",
     r"one question at a time|a single question|only one question|"
     r"ask one thing|never ask two",
     "no 'one question at a time' rule. "
     "Retell's guide calls for it; without it the agent stacks questions.", "FAIL"),
    ("stay-on-topic",
     r"stay on topic|do not discuss|only (?:discuss|talk|answer|help)|"
     r"politely (?:decline|redirect)|off-topic|out of scope|refuse",
     "no scope limit. The agent will answer anything it is asked.", "FAIL"),
    # ---- the rules below come from the Amplify Voice practitioner method.
    # See reference/amplify-voice-prompt-engineer.md.
    ("ai-question",
     r"are you (?:an? )?(?:ai|robot|bot|human|real)|if (?:they |the caller )?"
     r"ask(?:s|ed)? (?:if|whether) you are|ai question|admit.{0,20}\bai\b",
     "no answer prepared for 'are you an AI?'. Every caller asks it "
     "eventually. Handle it with humour, then redirect.", "WARN"),
    ("no-repeat-question",
     r"never ask (?:for )?the same|do not ask twice|don't ask twice|"
     r"already (?:told|gave|provided|answered)|track (?:what|the information)|"
     r"do not repeat (?:a |the )?question",
     "no 'never ask twice' rule. The agent will re-ask something the "
     "caller already answered, which reads as not listening.", "WARN"),
    ("wrong-person",
     r"wrong person|not the right person|someone else answers|"
     r"ask (?:politely )?(?:for|to speak)|is .{0,15}available",
     "no rule for the wrong person answering. Outbound calls need it; "
     "inbound calls need it when a household shares a line.", "WARN"),
    ("transcription-errors",
     r"transcription error|mis(?:heard|transcri)|wrong word|"
     r"unclear audio|did not (?:catch|hear)|didn't (?:catch|hear)|"
     r"broken.{0,10}up|lag",
     "no rule about lag and transcription errors. This is a voice call: "
     "words arrive wrong and messages arrive split in two. Say so, so "
     "the agent uses context instead of taking the text literally.", "WARN"),
]

EXAMPLE_MARKERS = re.compile(
    r"^\s*(?:#+\s*)?(?:example|examples|sample|for example|e\.g\.|"
    r"good response|bad response|caller:|agent:|user:|assistant:)",
    re.IGNORECASE | re.MULTILINE)

VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][\w.]*)\s*\}\}")


class Report:
    """Collects findings. FAIL breaks the build; WARN is judgement."""

    def __init__(self):
        self.rows = []

    def add(self, level, check, message, detail=None, line=None):
        self.rows.append({"level": level, "check": check, "message": message,
                          "detail": detail, "line": line})

    def fails(self):
        return [r for r in self.rows if r["level"] == "FAIL"]

    def warns(self):
        return [r for r in self.rows if r["level"] == "WARN"]


# --------------------------------------------------------------------------
# input
# --------------------------------------------------------------------------
def extract(path):
    """Return (prompt_text, meta dict) from a prompt file or a Retell export."""
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    meta = {"source": str(path), "kind": "text", "begin_message": None,
            "states": [], "default_dynamic_variables": {}, "model": None,
            "tools": []}
    if not raw.lstrip().startswith(("{", "[")):
        return raw, meta

    try:
        obj = json.loads(raw)
    except ValueError:
        return raw, meta
    if isinstance(obj, list):
        obj = obj[0] if obj else {}

    # a full agent export may embed the llm object
    for nest in ("response_engine", "llm", "retell_llm"):
        if isinstance(obj.get(nest), dict) and obj[nest].get("general_prompt"):
            obj = obj[nest]
            break

    meta["kind"] = "retell-llm-json"
    meta["begin_message"] = obj.get("begin_message")
    meta["states"] = obj.get("states") or []
    meta["default_dynamic_variables"] = obj.get("default_dynamic_variables") or {}
    meta["model"] = obj.get("model")
    meta["tools"] = obj.get("general_tools") or []

    parts = [obj.get("general_prompt") or ""]
    for st in meta["states"]:
        parts.append(f"\n\n# STATE: {st.get('name', '?')}\n"
                     f"{st.get('state_prompt') or ''}")
    return "\n".join(parts), meta


def strip_code(text):
    """Remove fenced code blocks so JSON samples do not trip speech checks."""
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def line_of(text, index):
    return text.count("\n", 0, index) + 1


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------
def _headings(text):
    return "\n".join(
        l for l in text.splitlines()
        if l.lstrip().startswith("#")
        or re.match(r"^\s*\*{0,2}[A-Z][A-Za-z /&,'-]{2,45}:?\*{0,2}\s*$", l))


def check_structure(text, rep):
    """Grade against whichever of the two accepted structures fits better."""
    hay = _headings(text).lower() or text[:2000].lower()

    def missing(spec):
        return [label for label, pat in spec
                if not re.search(pat, hay, re.IGNORECASE)]

    r_missing, a_missing = missing(RETELL_SECTIONS), missing(AMPLIFY_SECTIONS)
    # Score by how much of each structure is present, as a fraction, so the
    # eight-section method is not penalised for being longer.
    r_score = 1 - len(r_missing) / len(RETELL_SECTIONS)
    a_score = 1 - len(a_missing) / len(AMPLIFY_SECTIONS)
    if a_score > r_score:
        name, gaps, spec = "Amplify Voice (8 section)", a_missing, AMPLIFY_SECTIONS
    else:
        name, gaps, spec = "Retell guide (5 section)", r_missing, RETELL_SECTIONS

    rep.add("OK", "structure", f"reading it as: {name}")
    for label in gaps:
        rep.add("FAIL" if label in CRITICAL else "WARN", "structure",
                f"no '{label}' section found",
                f"The {name} structure is "
                f"{', '.join(l for l, _ in spec)}.")
    if not gaps:
        rep.add("OK", "structure", f"all {len(spec)} sections present")


def check_size(text, rep):
    """Two different lines, for two different reasons. Report both.

    TOKEN_QUALITY (2000) is Amplify Voice's real-time ceiling: past it the
    agent gets slower and follows instructions less reliably.
    TOKEN_SURCHARGE (4000) is Retell's BILLING line: past it Retell
    surcharges and scales the whole billed duration.
    Below 2000, a trim buys nothing. Above 4000, a trim buys money.
    """
    tokens = len(text) // CHARS_PER_TOKEN
    if tokens > TOKEN_SURCHARGE:
        rep.add("WARN", "size",
                f"about {tokens} tokens, over BOTH lines "
                f"({TOKEN_QUALITY} quality, {TOKEN_SURCHARGE} billing)",
                "Retell surcharges above 4000 and scales the whole billed "
                "duration, so a trim here is worth real money as well as "
                "latency. Move reference material into a knowledge base "
                "rather than deleting rules.")
    elif tokens > TOKEN_QUALITY:
        rep.add("WARN", "size",
                f"about {tokens} tokens, over the {TOKEN_QUALITY} "
                f"quality line (billing line is {TOKEN_SURCHARGE})",
                "Amplify Voice keeps a real-time agent under 2000 tokens "
                "excluding the knowledge base. Past it the agent is slower "
                "and follows instructions less reliably. No extra billing "
                "yet.")
    else:
        rep.add("OK", "size",
                f"about {tokens} tokens, under both the {TOKEN_QUALITY} "
                f"quality line and the {TOKEN_SURCHARGE} billing line")
    return tokens


# A speech-check hit sitting on a line that FORBIDS that literal is not a
# defect, it is the rule working. "Say 'three dollars', not '$3'" tripped
# the money check on the kit's own template. Suppress that class.
NEGATION = re.compile(
    r"\b(?:not|never|do not|don't|avoid|instead of|rather than|wrong|bad)\b"
    r"|->|→", re.IGNORECASE)


def check_speech(text, rep):
    body = strip_code(text)
    lines = body.splitlines()

    def forbidden_here(index):
        """True when the match sits on a line that is banning the literal."""
        return bool(NEGATION.search(lines[line_of(body, index) - 1]))

    hits = 0
    suppressed = 0
    for check_id, pat, why, fix in SPEECH_CHECKS:
        found = [m for m in re.finditer(pat, body)
                 if not forbidden_here(m.start())]
        suppressed += len(list(re.finditer(pat, body))) - len(found)
        if not found:
            continue
        hits += len(found)
        sample = ", ".join(sorted({m.group(0) for m in found})[:5])
        rep.add("WARN", f"speech/{check_id}",
                f"{len(found)} literal(s) the agent will mispronounce: {sample}",
                f"{why}. Fix: {fix}.", line_of(body, found[0].start()))
    if not hits:
        rep.add("OK", "speech",
                "no mispronounced literals found"
                + (f" ({suppressed} sat on a line forbidding them)"
                   if suppressed else ""))


def check_amplify(text, meta, rep):
    """The Amplify Voice technical-precision rules that a regex can find.

    Source: reference/amplify-voice-prompt-engineer.md. These are the rules
    a practitioner learned from transcripts, not from a docs page, so they
    catch a different class of defect from the Retell checks above.
    """
    body = strip_code(text)
    low = body.lower()

    # 1. the em dash. Read aloud, or stumbled over. Use a hyphen.
    ems = body.count("—")
    if ems:
        first = body.index("—")
        rep.add("WARN", "amplify/em-dash",
                f"{ems} em dash character(s) in the prompt",
                "Amplify Voice: never use the em dash, always use a hyphen. "
                "The model reads it aloud or stumbles on it.",
                line_of(body, first))
    else:
        rep.add("OK", "amplify/em-dash", "no em dash characters")

    # 2. filler words. One per sentence at most, one every two at least.
    if re.search(r"\bfiller\b|\bumm?\b|\buh-huh\b|\bso,|natural.{0,15}pause",
                 low):
        rep.add("OK", "amplify/fillers", "filler-word guidance present")
    else:
        rep.add("WARN", "amplify/fillers", "no filler-word guidance",
                "Amplify Voice: use natural fillers ('umm', 'so'), at most "
                "one per sentence and at least one every two sentences. "
                "Without it the agent reads like written text.")

    # 3. at most three options.
    if re.search(r"three (?:options|choices)|3 (?:options|choices)|"
                 r"(?:no more than|maximum of|at most) three|limit.{0,20}choices",
                 low):
        rep.add("OK", "amplify/three-options", "option limit stated")
    else:
        rep.add("WARN", "amplify/three-options", "no limit on how many "
                "options the agent offers",
                "Amplify Voice: three maximum. A caller cannot hold more "
                "than three spoken choices in their head.")

    # 4. timezone said once, not every time.
    if re.search(r"time ?zone", low):
        if re.search(r"time ?zone.{0,60}(?:once|not repeat|don't repeat|"
                     r"do not repeat)|(?:once|only once).{0,30}time ?zone",
                     low):
            rep.add("OK", "amplify/timezone", "timezone-once rule present")
        else:
            rep.add("WARN", "amplify/timezone",
                    "timezone is mentioned but not the 'say it once' rule",
                    "Amplify Voice: state the timezone once. Repeating it "
                    "every turn is the most-reported annoyance in booking "
                    "transcripts.")

    # 5. variable naming: ALL_CAPS with underscores.
    used = set(VAR_RE.findall(text))
    predefined = {"current_time", "user_number"}
    bad = sorted(v for v in used
                 if v not in predefined and v != v.upper())
    if bad:
        rep.add("WARN", "amplify/var-naming",
                f"variable(s) not in ALL_CAPS: {', '.join(bad[:8])}",
                "Amplify Voice: name variables in all caps with "
                "underscores, {{LIKE_THIS}}. A lowercase name is easy to "
                "confuse with ordinary prose when auditing a long prompt.")
    elif used:
        rep.add("OK", "amplify/var-naming", "variable names follow ALL_CAPS")

    # 6. number and symbol reading format.
    if re.search(r"group(?:s|ed|ing)? of three|groups of 3|"
                 r"one (?:digit|number) at a time|spell(?:ed)? out|"
                 r"read.{0,25}(?:digit|letter)s?|"
                 r"write out symbols|symbols as words", low):
        rep.add("OK", "amplify/number-format", "number or spelling format given")
    else:
        rep.add("WARN", "amplify/number-format",
                "no format for reading digits, names, or emails aloud",
                "Amplify Voice: phone numbers in groups of three, names and "
                "emails spelled in letter groups, symbols written as words. "
                "Without a rule the model reads a phone number at machine "
                "speed and the caller cannot follow it.")

    # 7. tools need a verbal bridge, or the caller hears dead air.
    if meta.get("tools"):
        if re.search(r"let me (?:check|look|pull|find)|one moment|"
                     r"bear with me|give me (?:one|a) (?:second|moment)|"
                     r"verbal bridge|while (?:i|the system)", low):
            rep.add("OK", "amplify/tool-bridge", "verbal bridge phrase present")
        else:
            rep.add("WARN", "amplify/tool-bridge",
                    f"{len(meta['tools'])} tool(s) but no verbal bridge phrase",
                    "Amplify Voice: say 'Let me check that for you...' "
                    "before a tool runs. Otherwise the caller hears silence "
                    "and starts talking over the answer.")

    # 8. no sense of time.
    if re.search(r"\b(?:a moment ago|earlier in (?:this|the) call|"
                 r"(?:few|couple of) (?:minutes|seconds) ago|"
                 r"how long (?:we|you)(?:'ve| have) been)\b", low):
        rep.add("WARN", "amplify/time-awareness",
                "the prompt refers to elapsed time",
                "Amplify Voice: a voice agent has no sense of time. Its only "
                "sense of time is the earlier turns. Any phrase about how "
                "long something took will be made up.")


def check_turn_taking(text, rep):
    bad = []
    for i, line in enumerate(strip_code(text).splitlines(), 1):
        if line.count("?") >= 2:
            bad.append((i, line.strip()[:90]))
    for i, line in bad[:8]:
        rep.add("WARN", "turn-taking",
                "two or more questions in one line", line, i)
    if not bad:
        rep.add("OK", "turn-taking", "no line stacks two questions")


def check_required(text, rep):
    low = text.lower()
    for check_id, pat, why, level in REQUIRED_BEHAVIOURS:
        if re.search(pat, low):
            rep.add("OK", f"required/{check_id}", "rule present")
        else:
            rep.add(level, f"required/{check_id}", why)


def check_risk(text, rep):
    body = strip_code(text).lower()
    found_any = False
    for label, pat in RISK_PHRASES:
        found = list(re.finditer(pat, body))
        if found:
            found_any = True
            rep.add("WARN", f"risk/{label}",
                    f"{len(found)} use(s) of '{label}' language",
                    "A voice agent that commits to an outcome, a price, or a "
                    "diagnosis creates liability. Confirm each one is a rule "
                    "FORBIDDING it, not an instruction to say it.",
                    line_of(body, found[0].start()))
    if not found_any:
        rep.add("OK", "risk", "no commitment or diagnosis language")


def check_variables(text, meta, rep):
    used = sorted(set(VAR_RE.findall(text)))
    supplied = set(meta.get("default_dynamic_variables") or {})
    if not used:
        rep.add("OK", "variables", "no dynamic variables used")
        return used
    unsupplied = [v for v in used if v not in supplied]
    rep.add("OK", "variables", f"{len(used)} used: {', '.join(used)}")
    if unsupplied and meta["kind"] == "retell-llm-json":
        rep.add("WARN", "variables",
                f"no default for: {', '.join(unsupplied)}",
                "If the call does not supply one, the caller hears the "
                "braces. Give every variable a default_dynamic_variables "
                "entry, even an empty-sounding one.")
    return used


def check_examples(text, rep):
    found = list(EXAMPLE_MARKERS.finditer(text))
    if not found:
        rep.add("WARN", "examples", "no examples found",
                "A worked example moves behaviour where more prose does not. "
                "One good and one bad example beat a paragraph of rules.")
        return
    lines = sorted({line_of(text, m.start()) for m in found})
    rep.add("OK", "examples",
            f"{len(found)} example marker(s) at lines "
            f"{', '.join(str(l) for l in lines[:12])}"
            + (" ..." if len(lines) > 12 else ""))
    rep.add("WARN", "examples",
            "re-read every example after any rule change",
            "An example outranks the rule it contradicts. A stale example "
            "showing old behaviour will beat the new rule above it. This is "
            "the most common cause of an agent ignoring a rule.")


def check_greeting(meta, text, rep):
    if meta["kind"] != "retell-llm-json":
        return
    begin = str(meta.get("begin_message") or "")
    # TRAP seen live: a dashboard paste can store the two-character string
    # '""' -- quote marks, not an empty string. The API reports it as set,
    # and the agent then SPEAKS a pair of quote marks or nothing at all.
    if begin.strip().strip('"').strip("'").strip():
        rep.add("OK", "greeting", f"begin_message set: {begin[:60]!r}")
    elif begin:
        rep.add("FAIL", "greeting",
                f"begin_message is {begin!r}, which is quote marks, not text",
                "Someone pasted quotes into the dashboard field. The API "
                "reports it as set, so no check that asks 'is it empty' will "
                "catch it. Clear the field, or put the real opening line in.")
    else:
        rep.add("WARN", "greeting", "begin_message is empty",
                "With no begin_message the agent improvises its opening line, "
                "so every call starts differently. Set it, or confirm the "
                "prompt tells it exactly what to open with.")


def check_states(meta, rep):
    states = meta.get("states") or []
    if not states:
        return
    names = [s.get("name") for s in states]
    rep.add("OK", "states", f"{len(states)} state(s): {', '.join(map(str, names))}")
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        rep.add("FAIL", "states", f"duplicate state names: {', '.join(map(str, dupes))}")
    targets = set()
    for st in states:
        for edge in st.get("edges") or []:
            if edge.get("destination_state_name"):
                targets.add(edge["destination_state_name"])
    unreachable = [n for n in names if n not in targets]
    if len(unreachable) > 1:
        rep.add("WARN", "states",
                f"state(s) no edge points at: {', '.join(map(str, unreachable))}",
                "Only the starting state should have no inbound edge.")
    if len(states) > 6:
        rep.add("WARN", "states",
                f"{len(states)} states is past the point a flow is clearer",
                "Retell's own guidance: once stages branch, use a "
                "conversation flow instead of prompt states.")


def check_duplication(text, rep):
    seen = {}
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if len(s) < 40 or s.startswith("#"):
            continue
        seen.setdefault(s, []).append(i)
    dupes = {s: ls for s, ls in seen.items() if len(ls) > 1}
    if dupes:
        for s, ls in list(dupes.items())[:5]:
            rep.add("WARN", "duplication",
                    f"line repeated {len(ls)} times (lines "
                    f"{', '.join(map(str, ls[:6]))})", s[:90])
    else:
        rep.add("OK", "duplication", "no repeated instruction lines")


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------
ORDER = {"FAIL": 0, "WARN": 1, "OK": 2}
GLYPH = {"FAIL": "FAIL", "WARN": "WARN", "OK": "ok  "}


def render(rep, meta, tokens, path):
    print(f"promptlint  {path}")
    print(f"  source kind : {meta['kind']}")
    if meta.get("model"):
        print(f"  model       : {meta['model']}")
    if meta.get("tools"):
        print(f"  tools       : {len(meta['tools'])}")
    print(f"  size        : ~{tokens} tokens")
    print()
    for row in sorted(rep.rows, key=lambda r: (ORDER[r["level"]], r["check"])):
        loc = f" (line {row['line']})" if row.get("line") else ""
        print(f"  {GLYPH[row['level']]}  {row['check']:<22} {row['message']}{loc}")
        if row.get("detail") and row["level"] != "OK":
            for chunk in _wrap(row["detail"], 66):
                print(f"        {chunk}")
    print()
    f, w = len(rep.fails()), len(rep.warns())
    print(f"  {f} fail, {w} warn, "
          f"{len(rep.rows) - f - w} ok")
    if f == 0:
        print("  Clean on paper. That is NOT proof it behaves. "
              "Run sp.py chat next.")
    return f


def _wrap(text, width):
    words, line, out = text.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out


def lint(path):
    text, meta = extract(path)
    rep = Report()
    if not text.strip():
        rep.add("FAIL", "input", "prompt is empty")
        return rep, meta, 0
    check_structure(text, rep)
    tokens = check_size(text, rep)
    check_speech(text, rep)
    check_turn_taking(text, rep)
    check_amplify(text, meta, rep)
    check_required(text, rep)
    check_risk(text, rep)
    check_variables(text, meta, rep)
    check_examples(text, rep)
    check_greeting(meta, text, rep)
    check_states(meta, rep)
    check_duplication(text, rep)
    return rep, meta, tokens


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Static check of a Retell single-prompt agent. "
                    "Runs fully offline. No API key needed.")
    ap.add_argument("path", help="prompt .md/.txt, or a Retell LLM .json export")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on warnings too")
    a = ap.parse_args(argv)

    if not Path(a.path).exists():
        print(f"ERROR: no such file: {a.path}", file=sys.stderr)
        return 2

    rep, meta, tokens = lint(a.path)
    if a.json:
        print(json.dumps({"source": a.path, "tokens": tokens,
                          "findings": rep.rows}, indent=2, ensure_ascii=False))
        fails = len(rep.fails())
    else:
        fails = render(rep, meta, tokens, a.path)
    if fails:
        return 1
    return 1 if (a.strict and rep.warns()) else 0


if __name__ == "__main__":
    sys.exit(main())
