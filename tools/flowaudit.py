#!/usr/bin/env python3
"""Grade a flow export against the rows of docs/standards/qa-checklist.md
that a machine can judge from the export alone.

WHY THIS EXISTS

A full grade against `docs/standards/qa-checklist.md` by hand produces a
document that is out of date the next time anyone edits a node. About half
the rows are mechanical: they ask whether a field is set, whether an id
repeats, whether a line starts with a number. Those should be a command,
not a reading exercise.

WHAT IT DOES NOT DO

It does not replace the checklist. Every row that needs a trace run, a real call
transcript, or a judgement about meaning is printed as MANUAL with the evidence
the checklist asks for, so the human half of the audit is a short list rather
than a rediscovery of the whole file.

`flowlint.py` and this tool do different jobs. The linter proves the wiring is
sound. This one grades the wiring against the standard.

EXIT CODE

Non-zero if any automated row FAILS, so it can gate a push.

USAGE

    python tools/flowaudit.py --client acme-dental --agent intake
    python tools/flowaudit.py --file acme-dental/agents/intake/exports/v54.json
    python tools/flowaudit.py --client acme-dental --agent intake --md acme-dental/docs/flow-audit.md
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

PASS, FAIL, WARN, MANUAL, NA = "PASS", "FAIL", "WARN", "MANUAL", "n/a"

# Variable names this client's downstream recap or webhook reads, so R7 can
# check they are set before every call-ending exit. Empty by default; fill
# per client, never in the shared kit copy of this file.
RECAP_VARIABLES = set()


class Audit:
    def __init__(self, flow, label):
        self.flow = flow
        self.label = label
        self.rows = []
        self.nodes = flow.get("nodes", [])
        self.by_id = {n["id"]: n for n in self.nodes}
        self.by_name = {n.get("name"): n for n in self.nodes}

    def add(self, rid, verdict, check, evidence=""):
        self.rows.append((rid, verdict, check, evidence))

    # ---------------------------------------------------------- helpers
    def exits(self, n):
        out = []
        for e in (n.get("edges") or []):
            out.append(("edge", e))
        for k in ("else_edge", "always_edge", "skip_response_edge"):
            if n.get(k):
                out.append((k, n[k]))
        return out

    def dests(self, n):
        d = []
        for kind, e in self.exits(n):
            t = e.get("destination_node_id")
            if t:
                d.append((kind, t))
        return d

    def speaks(self, n):
        return n.get("type") == "conversation"

    def instr_text(self, n):
        return (n.get("instruction") or {}).get("text") or ""

    # ------------------------------------------------------------ A
    def section_a(self):
        f = self.flow
        # A4: every branch reaches an end node
        ends = {n["id"] for n in self.nodes if n.get("type") == "end"}
        if not ends:
            self.add("A4", FAIL, "Every branch reaches an end node", "no end node in the flow")
        else:
            radj = defaultdict(set)
            for n in self.nodes:
                for _, t in self.dests(n):
                    radj[t].add(n["id"])
            seen, stack = set(ends), list(ends)
            while stack:
                u = stack.pop()
                for v in radj[u]:
                    if v not in seen:
                        seen.add(v)
                        stack.append(v)
            stranded = [n.get("name") for n in self.nodes if n["id"] not in seen]
            self.add("A4", PASS if not stranded else FAIL,
                     "Every branch reaches an end node",
                     "all %d nodes reach an end" % len(self.nodes) if not stranded
                     else "cannot reach an end: " + ", ".join(map(str, stranded)))

        fm = f.get("flex_mode")
        self.add("A5", PASS if not fm else FAIL, "flex_mode is off at flow level",
                 "flex_mode = %r" % fm)

        start = self.by_id.get(f.get("start_node_id"))
        sname = (start or {}).get("name", "?")
        router = any(n.get("type") == "branch" for n in self.nodes)
        self.add("A7", PASS if start and router else WARN,
                 "Greeting and intent router are separate nodes",
                 "start node is %r; flow has %d branch nodes"
                 % (sname, sum(1 for n in self.nodes if n.get("type") == "branch")))

        ss = f.get("start_speaker")
        self.add("A8", PASS if ss == "agent" else WARN,
                 "start_speaker matches inbound", "start_speaker = %r (inbound wants 'agent')" % ss)

    # ------------------------------------------------------------ B
    def section_b(self):
        # B2 / I23: every equation condition carries the outer operator key
        bad = []
        for n in self.nodes:
            for kind, e in self.exits(n):
                c = e.get("transition_condition") or {}
                if c.get("type") == "equation" or c.get("equations"):
                    if "operator" not in c:
                        bad.append("%s -> %s" % (n.get("name"), kind))
        self.add("B2/I23", PASS if not bad else FAIL,
                 "Every equation condition carries the outer 'operator' key",
                 "clean" if not bad else "; ".join(bad))

        # B3: nodes with 3+ edges have fine-tune examples
        thin = []
        for n in self.nodes:
            ne = len(n.get("edges") or [])
            ex = len(n.get("finetune_transition_examples") or [])
            if ne >= 3 and ex == 0:
                thin.append("%s (%d edges, 0 examples)" % (n.get("name"), ne))
        self.add("B3", PASS if not thin else WARN,
                 "Nodes with 3+ edges have fine-tune examples",
                 "clean" if not thin else "; ".join(thin))

        # B4: every global node has a go-back
        # The field is `go_back_conditions`, plural. Reading the singular reported
        # all four global nodes as missing it, which is false.
        withgo, without = [], []
        for n in self.nodes:
            g = n.get("global_node_setting")
            if not g:
                continue
            has = bool(g.get("go_back_conditions") or g.get("go_back_condition"))
            (withgo if has else without).append(n.get("name"))
        # A global node with NO go-back is correct when it routes onward instead
        # of handing the caller back. Checklist B12 says so explicitly. So this
        # is only a finding if such a node has no reliable exit either.
        stuck = []
        for name in without:
            n = self.by_name[name]
            if not self.exits(n):
                stuck.append(name)
        self.add("B4", PASS if not stuck else FAIL,
                 "Every global node either hands back or routes onward",
                 "go-back: %s | routes onward instead: %s%s"
                 % (", ".join(withgo) or "none", ", ".join(without) or "none",
                    "" if not stuck else "  <- NO EXIT AT ALL: " + ", ".join(stuck)))

        # B9 / B10: example roles and unique ids
        ids, badrole = [], []
        for n in self.nodes:
            for ex in (n.get("finetune_transition_examples") or []) + \
                      (n.get("finetune_conversation_examples") or []):
                if ex.get("id"):
                    ids.append(ex["id"])
                for t in (ex.get("transcript") or []):
                    r, c = t.get("role"), (t.get("content") or "")
                    # Only flag a user turn that repeats a line this flow OWNS.
                    # A looser "starts with I'm" test flagged a real sales
                    # caller saying "I'm help with answering your phone system."
                    # Needs to be long enough to be a real quotation. A 25-char
                    # floor stops it firing on a caller saying "Yes", which
                    # appears inside plenty of node instructions.
                    if r == "user" and len(c.strip()) >= 25 and any(
                            c.strip()[:40] in self.instr_text(m) for m in self.nodes):
                        badrole.append("%s: %r" % (n.get("name"), c[:44]))
        dup = [i for i, c in Counter(ids).items() if c > 1]
        self.add("B10", PASS if not dup else FAIL,
                 "Example ids are unique across the whole flow",
                 "%d ids, all unique" % len(ids) if not dup else "repeated: " + ", ".join(dup))
        self.add("B9", PASS if not badrole else WARN,
                 "Every example turn carries the right role",
                 "no agent-looking line tagged user" if not badrole else "; ".join(badrole[:4]))

        # B13: every node has one exit that cannot fail to match
        trap = []
        for n in self.nodes:
            if n.get("type") == "end":
                continue
            kinds = [k for k, _ in self.exits(n)]
            unconditional = any(k in ("else_edge", "always_edge") for k in kinds)
            isglobal = bool(n.get("global_node_setting"))
            if not unconditional and not isglobal:
                trap.append("%s (%d prompt/equation edges, no else, no always)"
                            % (n.get("name"), len(kinds)))
        self.add("B13", PASS if not trap else WARN,
                 "Every node has one exit that cannot fail to match",
                 ("clean" if not trap else
                  "%d node(s) rely on Retell's documented STAY fallback when no edge matches, "
                  "which re-prompts rather than dead-ends. Read each against B6b: the risk is a "
                  "caller PARKED until max_call_duration_ms, not a crash. " % len(trap)
                  + "; ".join(trap)))

        # B16: no else_edge points at a closing, sign-off, transfer or end
        # The concern is an UNCONDITIONAL hang-up: an else edge has no condition,
        # so from a global node it ends the call whatever the caller said. The
        # ordinary closing chain uses else edges by design and is not a finding.
        hits = []
        for n in self.nodes:
            e = n.get("else_edge")
            if not e:
                continue
            dst = self.by_id.get(e.get("destination_node_id"))
            dn = (dst or {}).get("name", "?")
            ends_call = (dst or {}).get("type") == "end"
            if ends_call and (n.get("global_node_setting") or self.speaks(n)):
                hits.append("%s -> %s (else edge into an end node)" % (n.get("name"), dn))
        self.add("B16", PASS if not hits else WARN,
                 "No else_edge points at a closing, sign-off or transfer",
                 "clean" if not hits else "; ".join(hits))

        # B7 / R3: skip_response_edge placement
        speaks_no_ask, question_with_skip = [], []
        for n in self.nodes:
            if not self.speaks(n):
                continue
            txt = self.instr_text(n)
            asks = "?" in txt
            has_skip = bool(n.get("skip_response_edge"))
            if asks and has_skip:
                question_with_skip.append(n.get("name"))
            if not asks and not has_skip:
                speaks_no_ask.append(n.get("name"))
        self.add("B7", PASS if not speaks_no_ask else WARN,
                 "Every node that speaks but asks nothing has a skip_response_edge",
                 "clean" if not speaks_no_ask else "no skip edge: " + ", ".join(map(str, speaks_no_ask)))
        self.add("R3", PASS if not question_with_skip else WARN,
                 "No question node carries skip_response_edge",
                 "clean" if not question_with_skip
                 else "question node with a skip edge: " + ", ".join(map(str, question_with_skip)))

        # B17: an equation reads a variable that is written upstream
        writes = defaultdict(set)
        for n in self.nodes:
            for v in (n.get("variables") or []):
                if v.get("name"):
                    writes[v["name"]].add(n.get("name"))
            code = n.get("code") or ""
            for m in re.finditer(r"(?:dv|out)\.([A-Za-z_][A-Za-z0-9_]*)\s*=", code):
                writes[m.group(1)].add(n.get("name"))
            # A Retell code node writes by RETURNING an object, so the keys of
            # every return literal are writes too. Missing this reported
            # closing_passes and gate_passes as never set, which is false.
            for m in re.finditer(r"return\s*\{([^}]*)\}", code, re.S):
                for k in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*:", m.group(1)):
                    writes[k.group(1)].add(n.get("name"))
        unread = []
        for n in self.nodes:
            for kind, e in self.exits(n):
                c = e.get("transition_condition") or {}
                for q in (c.get("equations") or []):
                    for m in re.finditer(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}", str(q.get("left", ""))):
                        if m.group(1) not in writes:
                            unread.append("%s reads {{%s}}" % (n.get("name"), m.group(1)))
        self.add("B17", PASS if not unread else WARN,
                 "Every equation reads a variable that is SET somewhere",
                 "clean" if not unread else "; ".join(sorted(set(unread))))

    # ------------------------------------------------------------ D
    def section_d(self):
        # D10: no instruction line starts with a number or numbered label
        pat = re.compile(r"^\s*(?:\(?\d+[\).:]|Step\s+\d|PRIORITY\s+\d|RULE\s+\d)", re.I)
        hits = []
        for n in self.nodes:
            for i, ln in enumerate(self.instr_text(n).split("\n"), 1):
                if pat.match(ln):
                    hits.append("%s line %d: %r" % (n.get("name"), i, ln.strip()[:52]))
        gp = self.flow.get("global_prompt") or ""
        for i, ln in enumerate(gp.split("\n"), 1):
            if pat.match(ln):
                hits.append("GLOBAL PROMPT line %d: %r" % (i, ln.strip()[:52]))
        self.add("D10", PASS if not hits else FAIL,
                 "No instruction line starts with a number or a numbered label",
                 "clean" if not hits else "; ".join(hits[:8]) +
                 ("  (+%d more)" % (len(hits) - 8) if len(hits) > 8 else ""))

        # D2: node prompt length, against the measured capacity finding
        big = []
        for n in self.nodes:
            w = len(self.instr_text(n).split())
            if w >= 470:
                big.append("%s (%d words)" % (n.get("name"), w))
        self.add("D2", PASS if not big else WARN,
                 "No node prompt is over-long",
                 "largest under 470 words" if not big else "; ".join(big) +
                 "  [lessons-intake-node-capacity: 476 scored 3/3, 554 scored 2/5, 619 scored 0/3]")

        # D12: a short announcement node should be static_text
        leaky = []
        for n in self.nodes:
            if not self.speaks(n):
                continue
            it = (n.get("instruction") or {}).get("type")
            w = len(self.instr_text(n).split())
            if it == "prompt" and w <= 45:
                leaky.append("%s (%d words, prompt)" % (n.get("name"), w))
        self.add("D12", PASS if not leaky else WARN,
                 "Short announcement nodes use static_text",
                 "clean" if not leaky else "; ".join(leaky))

        # D3: how much of the flow is static_text at all
        types = Counter((n.get("instruction") or {}).get("type")
                        for n in self.nodes if self.speaks(n))
        self.add("D3", MANUAL, "Every exact line is static_text",
                 "conversation nodes by instruction type: %s" % dict(types))

    # ------------------------------------------------------------ E/F/G
    def section_efg(self):
        gp = self.flow.get("global_prompt") or ""
        self.add("E3", PASS if re.search(r"#\s*Style", gp, re.I) else WARN,
                 "Speech formatting block present in the global prompt",
                 "found a # Style section" if re.search(r"#\s*Style", gp, re.I) else "no # Style section")
        self.add("E4", PASS if "NO_RESPONSE_NEEDED" in gp else WARN,
                 "Standard handlers present, including NO_RESPONSE_NEEDED",
                 "NO_RESPONSE_NEEDED present in the global prompt" if "NO_RESPONSE_NEEDED" in gp
                 else "NO_RESPONSE_NEEDED not in the global prompt")
        self.add("E5", PASS if "current_time" in gp else WARN,
                 "Current time present, since the flow uses office hours",
                 "current_time template found" if "current_time" in gp else "no current_time")

        dv = self.flow.get("default_dynamic_variables") or {}
        looks_pii = [k for k, v in dv.items()
                     if re.search(r"\d{3}[-.\s]?\d{3}[-.\s]?\d{4}", str(v))]
        self.add("F5", PASS if not looks_pii else FAIL,
                 "No real customer data in default_dynamic_variables",
                 "%d defaults, none look like a phone number" % len(dv) if not looks_pii
                 else "phone-like default: " + ", ".join(looks_pii))

        strict = self.flow.get("tool_call_strict_mode")
        self.add("G0", PASS if strict else FAIL,
                 "tool_call_strict_mode is true at flow level",
                 "tool_call_strict_mode = %r  [Retell names this as the transition-reliability "
                 "lever on gpt-4.1]" % strict)

        mc = self.flow.get("model_choice") or {}
        self.add("G0b", PASS if mc.get("model") == "gpt-4.1" else WARN,
                 "Flow model is gpt-4.1, per Rey's rule",
                 "model_choice = %s" % json.dumps(mc))

    # ------------------------------------------------------------ R
    def section_r(self):
        # R5: branch equations read enum values that the extract actually offers
        choices = {}
        for n in self.nodes:
            for v in (n.get("variables") or []):
                if v.get("choices"):
                    choices[v["name"]] = set(v["choices"])
        bad = []
        for n in self.nodes:
            if n.get("type") != "branch":
                continue
            for kind, e in self.exits(n):
                c = e.get("transition_condition") or {}
                for q in (c.get("equations") or []):
                    m = re.match(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}$", str(q.get("left", "")).strip())
                    if not m:
                        continue
                    var, right = m.group(1), str(q.get("right"))
                    if var in choices and q.get("operator") in ("==", "!=") \
                            and right not in choices[var] and not right.isdigit():
                        bad.append("%s: {{%s}} %s %r not in %s"
                                   % (n.get("name"), var, q.get("operator"), right,
                                      sorted(choices[var])))
        self.add("R5", PASS if not bad else FAIL,
                 "Branch equations read enum values the extract actually offers",
                 "clean" if not bad else "; ".join(bad))

        # R11g / R11h: three-value enums
        three, boolish = [], []
        for n in self.nodes:
            for v in (n.get("variables") or []):
                ch = v.get("choices") or []
                if len(ch) == 3:
                    d = (v.get("description") or "").lower()
                    tight = re.search(r"never|forbidden|only if|do not answer", d)
                    three.append("%s.%s %s%s" % (n.get("name"), v["name"], ch,
                                                 "" if tight else "  <- middle value not tightly defined"))
        for n in self.nodes:
            for kind, e in self.exits(n):
                c = e.get("transition_condition") or {}
                for q in (c.get("equations") or []):
                    m = re.match(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}$", str(q.get("left", "")).strip())
                    if m and m.group(1) in choices and len(choices[m.group(1)]) >= 3 \
                            and q.get("operator") == "!=":
                        boolish.append("%s: {{%s}} != %r merges the other two values"
                                       % (n.get("name"), m.group(1), q.get("right")))
        self.add("R11g", MANUAL if three else NA,
                 "A three-value enum has its MIDDLE value defined as tightly as its ends",
                 "; ".join(three) if three else "no three-value enum in this flow")
        self.add("R11h", PASS if not boolish else FAIL,
                 "No enum is read with a boolean test",
                 "clean" if not boolish else "; ".join(boolish))

        # R17: a prompt edge relied on for a route that MUST hold
        absolutes = []
        for n in self.nodes:
            for kind, e in self.exits(n):
                c = e.get("transition_condition") or {}
                p = c.get("prompt") or ""
                for w in ("always", "never", "regardless"):
                    if re.search(r"\b%s\b" % w, p, re.I):
                        absolutes.append("%s: prompt edge says %r" % (n.get("name"), w))
                        break
        self.add("R17", MANUAL if absolutes else PASS,
                 "No prompt edge is relied on for a route that MUST hold",
                 "; ".join(sorted(set(absolutes))) if absolutes
                 else "no prompt edge uses always/never/regardless")

        # R7: recap variables set on every call-ending exit. Empty by
        # default; set RECAP_VARIABLES below to the variable names this
        # client's downstream recap or webhook actually reads.
        recap = RECAP_VARIABLES
        setters = set()
        for n in self.nodes:
            code = n.get("code") or ""
            if any(r in code for r in recap):
                setters.add(n["id"])
        ends = [n for n in self.nodes if n.get("type") == "end"]
        radj = defaultdict(set)
        for n in self.nodes:
            for _, t in self.dests(n):
                radj[t].add(n["id"])
        risky = []
        for e in ends:
            for pred in radj[e["id"]]:
                p = self.by_id[pred]
                # one hop back: did anything on the way set a recap list?
                if pred not in setters:
                    ok = any(pp in setters for pp in radj[pred])
                    if not ok:
                        risky.append("%s -> %s" % (p.get("name"), e.get("name")))
        if recap:
            self.add("R7", MANUAL, "Recap variables set on every call-ending exit",
                     "recap setters: %s. Paths into an end node with no setter within two hops: %s"
                     % (sorted(self.by_id[s].get("name") for s in setters),
                        "; ".join(sorted(set(risky))) or "none"))
        else:
            self.add("R7", NA, "Recap variables set on every call-ending exit",
                     "RECAP_VARIABLES is empty; set it to this client's recap "
                     "variable names to enable this check")

    # ------------------------------------------------------------ C
    def section_c(self):
        gp = (self.flow.get("global_prompt") or "").lower()
        alltxt = " ".join(self.instr_text(n).lower() for n in self.nodes) + " " + gp
        self.add("C3", PASS if "office is closed" in alltxt or "next business day" in alltxt
                 else WARN, "After-hours path exists",
                 "found after-hours wording" if "office is closed" in alltxt else "none found")
        sil = [k for k in ("still there", "difficulty hearing") if k in alltxt]
        self.add("C4", PASS if sil else WARN, "Silence is handled in the flow",
                 "found: " + ", ".join(repr(k) for k in sil) if sil else "none found")
        self.add("C5", FAIL if "wrong number" not in alltxt else PASS,
                 "Wrong number is handled",
                 "no 'wrong number' wording anywhere in the flow or the global prompt"
                 if "wrong number" not in alltxt else "found wrong-number wording")

    # ------------------------------------------------------------ manual
    def manual_rows(self):
        for rid, what, why in [
            ("B6", "No unguarded double-say path",
             "flowlint.py --line \"<sentence>\" per contractual sentence"),
            ("B6c", "The parked-caller case was checked on a REAL call record",
             "current_node / previous_node in collected_dynamic_variables, plus disconnection_reason"),
            ("B6e", "Every contractual sentence read in a full transcript by hand",
             "callreview.py on recent calls"),
            ("B6j", "If a GLOBAL node is one of the sayers, a trace proved it",
             "the linter is blind here; needs a say_times trace at --reps 3"),
            ("D5", "No caller-facing line drifted from the approved wording",
             "flowdiff.py against the last approved export"),
            ("D9", "No agent turn is a statement with no question",
             "count over the last 30 calls, not by eye"),
            ("I1", "Every scenario traced", "tracerun.py report"),
            ("I2", "Prompt-edge behaviour repeated", "--reps, 9 of 10 is a defect"),
            ("I4", "Voice, interruption and speech-to-text checked on a real call",
             "a live call; text testing cannot see these"),
            ("I17", "Any silent node chain timed on a real call",
             "time_sec on node_transition in transcript_with_tool_calls"),
            ("R11a", "The agent's REAL token number read before any prompt trim",
             "llm_token_usage from ~30 real calls"),
            ("R11d", "The DELIVERY setting checked separately from the flow",
             "deliverycheck.py; webhook_url lives on the AGENT"),
        ]:
            self.add(rid, MANUAL, what, why)

    def run(self):
        self.section_a()
        self.section_b()
        self.section_c()
        self.section_d()
        self.section_efg()
        self.section_r()
        self.manual_rows()
        return self.rows


def report(rows, label, version, nodes):
    counts = Counter(v for _, v, _, _ in rows)
    print("=" * 78)
    print("QA AUDIT  %s  |  flow v%s  |  %d nodes" % (label, version, nodes))
    print("=" * 78)
    order = {FAIL: 0, WARN: 1, MANUAL: 2, PASS: 3, NA: 4}
    for rid, v, check, ev in sorted(rows, key=lambda r: (order.get(r[1], 9), r[0])):
        print("\n[%-6s] %-8s %s" % (v, rid, check))
        if ev:
            for i, chunk in enumerate([ev[i:i + 96] for i in range(0, len(ev), 96)][:6]):
                print("           %s" % chunk)
    print("\n" + "-" * 78)
    print("  ".join("%s=%d" % (k, counts[k]) for k in (FAIL, WARN, MANUAL, PASS, NA) if counts[k]))
    return counts


def to_md(rows, label, version, nodes):
    out = ["# QA audit - %s" % label, "",
           "Flow version **%s**, %d nodes. Produced by `tools/flowaudit.py`, which grades the"
           % (version, nodes),
           "mechanical rows of [qa-checklist.md](../retell-flow-standard/qa-checklist.md).",
           "Rows marked MANUAL need a trace run, a real call, or a judgement and are listed",
           "with the evidence the checklist asks for.", "",
           "| Row | Verdict | Check | Evidence |", "|---|---|---|---|"]
    order = {FAIL: 0, WARN: 1, MANUAL: 2, PASS: 3, NA: 4}
    for rid, v, check, ev in sorted(rows, key=lambda r: (order.get(r[1], 9), r[0])):
        ev = ev.replace("|", "\\|")
        out.append("| `%s` | **%s** | %s | %s |" % (rid, v, check, ev))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--client", help="client folder name")
    ap.add_argument("--agent", help="agent slug under <client>/agents/")
    ap.add_argument("--file")
    ap.add_argument("--md", help="also write a markdown table here")
    a = ap.parse_args()

    if a.file:
        path, label = a.file, os.path.basename(a.file)
    elif a.client and a.agent:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit"))
        from retellkit import agent_config
        cfg = agent_config(a.client, a.agent)
        exports = sorted(Path(cfg["exports"]).glob("v*.json"))
        if not exports:
            raise SystemExit(f"no exports found under {cfg['exports']}")
        path, label = str(exports[-1]), f"{a.client}/{a.agent}"
    else:
        raise SystemExit("pass --file, or --client and --agent")

    flow = json.load(open(path, encoding="utf-8"))
    rows = Audit(flow, label).run()
    counts = report(rows, label, flow.get("version"), len(flow.get("nodes", [])))

    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        open(a.md, "w", encoding="utf-8").write(
            to_md(rows, label, flow.get("version"), len(flow.get("nodes", []))))
        print("wrote", a.md)
    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    raise SystemExit(main())
