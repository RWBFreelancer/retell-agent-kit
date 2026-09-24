#!/usr/bin/env python3
"""Run the traces in <client>/tests/TRACES.md against a real conversation flow.

This is the behaviour half of the test suite. `flowlint.py` proves structure:
which edges exist, which variables are read. It cannot prove what the agent
actually says. This can.

Each trace with a ```trace block gets its own throwaway sandbox (see
`retell_chat.py`), a scripted set of caller turns, and three assertions:

    expect_path  node names that must appear, in order
    forbid_path  node names that must never appear
    say_times    exact sentence -> how many times it may be spoken

Only conversation nodes report a transition. Branch and code nodes are
instant and invisible, so `expect_path` is matched as an ordered subsequence,
never as an exact list. `say_times` needs no node data at all, which makes it
the strongest assertion here: a double-say is counted, not inferred.

Testing is probabilistic. Prompt-based edges are a coin weighted by the
prompt, not a switch. `--reps N` runs the same trace N times and reports how
many passed. 9 of 10 is a defect, not a pass.

THE SANDBOX MODEL IS NOT THE PRODUCTION MODEL, AND NEVER gpt-4.1.

Rey, 2026-09-03: "use always gpt 4.1 mini for chat tests. however, prompts and
the contents of the voice ai should be in 4.1 only."
Rey, 2026-09-17: "use gpt 4.1 mini or smaller models, he did not approve for
those tests." the client has not approved the cost of gpt-4.1 test runs.

So `--model` accepts only `retell_chat.TEST_MODELS` (gpt-4.1-mini, the default,
or gpt-4.1-nano), and `retell_chat.Sandbox` enforces it on the in-memory copy.
There is no way to run a trace on gpt-4.1. The export on disk and the flow on
Retell are never touched, and both agents keep running `gpt-4.1` for real
callers.

What that costs you in evidence: a prompt-based edge is a coin weighted by the
prompt AND by the model reading it. A green run on mini proves the wiring, the
node text, and any say-once count. It does NOT prove `gpt-4.1` takes the same
edge, and mini is known to fail prose say-once guards in long nodes that
gpt-4.1 passes (`docs/lessons-sandbox-route-divergence.md`). So for a mini
failure on a prose guard, count real calls first (free), and state the
limit plainly to Rey. Never switch models to settle it.

Usage:
    python tools/tracerun.py --agent b
    python tools/tracerun.py --agent b --trace T-F
    python tools/tracerun.py --file acme-dental/agents/intake/exports/v21.json --trace T-F
    python tools/tracerun.py --agent b --trace T-F --reps 5
    python tools/tracerun.py --help

Nothing here writes to the production flow, and nothing here publishes.
"""
import re
import sys
import json
import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from retellkit import RetellClient, RetellError, agent_config, load_env, clients_root
from retell_chat import (Sandbox, agent_lines, node_hops, flow_object,
                         CENTS_PER_MESSAGE, TEST_MODELS, DEFAULT_TEST_MODEL,
                         force_test_model)


def traces_path(client_name):
    return clients_root() / client_name / "tests" / "TRACES.md"


BLOCK = re.compile(r"```trace\s*\n(.*?)\n```", re.S)


# ---------- loading ----------
def load_traces(path):
    """Every runnable trace block, keyed by id, in file order."""
    text = Path(path).read_text(encoding="utf-8")
    out = {}
    for raw in BLOCK.findall(text):
        try:
            t = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RetellError("bad trace block in {}: {}".format(path, exc))
        if "id" not in t:
            raise RetellError("trace block with no id in {}".format(path))
        if t["id"] in out:
            # A duplicate id used to overwrite silently, and the runner then
            # reported the id you asked for while executing a DIFFERENT trace.
            # That produced a confident 8-of-8 for a scenario never run
            # (2026-08-31). Refuse to load rather than measure the wrong thing.
            raise RetellError(
                "duplicate trace id {!r} in {}. Ids must be unique: the second "
                "block would silently replace the first and the run would "
                "report a result for a trace it never executed.".format(
                    t["id"], path))
        out[t["id"]] = t
    return out


# ---------- assertions ----------
def subsequence_miss(expected, actual):
    """First expected name that does not appear in order. None if all do."""
    i = 0
    for want in expected:
        while i < len(actual) and actual[i] != want:
            i += 1
        if i == len(actual):
            return want
        i += 1
    return None


def check(trace, spoken, path_names):
    """Return a list of failure strings. Empty list means PASS."""
    fails = []

    miss = subsequence_miss(trace.get("expect_path") or [], path_names)
    if miss:
        fails.append("never reached node {!r}".format(miss))

    for bad in trace.get("forbid_path") or []:
        if bad in path_names:
            fails.append("reached forbidden node {!r}".format(bad))

    blob = "\n".join(spoken)
    for line, want in (trace.get("say_times") or {}).items():
        got = blob.count(line)
        # want is an exact count, or [min, max] inclusive for "at most" rules.
        if isinstance(want, list):
            ok = want[0] <= got <= want[1]
            shown = "{}-{}".format(want[0], want[1])
        else:
            ok = got == want
            shown = want
        if not ok:
            fails.append("said {}x (wanted {}x): {!r}".format(
                got, shown, line[:60] + ("..." if len(line) > 60 else "")))

    return fails


# ---------- one run ----------
def run_once(client, flow, trace, label, verbose=False, model=DEFAULT_TEST_MODEL):
    """Stand up a sandbox, walk the turns, tear it down. Returns a result dict."""
    spoken, path_names = [], []
    with Sandbox(client, flow, "{}-{}".format(label, trace["id"]), model=model) as sb:
        chat_id = sb.start(trace.get("seed"))
        for turn in trace["turns"]:
            try:
                msgs = sb.send(chat_id, turn)
            except RetellError as exc:
                # The agent can hang up before the script runs out, which is
                # often the RIGHT behaviour: a sales hard-stop, or an incomplete
                # exit. Retell then answers create-chat-completion with HTTP 400
                # "Chat already ended". Treating that as a crash killed a whole
                # run on 2026-08-23. The turns already walked still get checked.
                if "already ended" not in str(exc).lower():
                    raise
                if verbose:
                    print("    CALLER: {!r}".format(turn))
                    print("      -> agent had already ended the call")
                break
            hops = node_hops(msgs)
            path_names.extend(n for _, n, _ in hops)
            lines = agent_lines(msgs)
            spoken.extend(lines)
            if verbose:
                print("    CALLER: {!r}".format(turn))
                for _, nname, ttype in hops:
                    print("      -> {} [{}]".format(nname, ttype))
                for ln in lines:
                    print("      AGENT: {}".format(ln))
        sb.end(chat_id)
        rec = sb.record(chat_id)

    return {"fails": check(trace, spoken, path_names),
            "path": path_names,
            "spoken": spoken,
            "vars": rec.get("collected_dynamic_variables") or {},
            "cost": (rec.get("chat_cost") or {}).get("combined_cost")}


# ---------- CLI ----------
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Run <client>/tests/TRACES.md against a real flow in a throwaway "
                    "sandbox. Never touches the production flow.")
    ap.add_argument("--client", required=True, help="client folder name")
    ap.add_argument("--agent", required=True, help="agent slug under <client>/agents/")
    ap.add_argument("--version", type=int, default=None,
                    help="flow version to pull (default: latest draft)")
    ap.add_argument("--file", default=None,
                    help="test a local export instead of pulling from Retell")
    ap.add_argument("--trace", action="append", default=None,
                    help="trace id to run, e.g. T-F (repeatable; default: all)")
    ap.add_argument("--reps", type=int, default=1,
                    help="run each trace N times and report the pass rate")
    ap.add_argument("--verbose", action="store_true",
                    help="print every turn as it happens")
    ap.add_argument("--model", default=DEFAULT_TEST_MODEL, choices=TEST_MODELS,
                    help="model for the throwaway SANDBOX only. Default "
                         "gpt-4.1-mini. gpt-4.1 is not allowed: the client has not "
                         "approved that test cost (Rey, 2026-09-17).")
    ap.add_argument("--yes", action="store_true",
                    help="skip the cost confirmation")
    a = ap.parse_args(argv)

    env = load_env()
    client = RetellClient(env)
    traces = load_traces(traces_path(a.client))

    wanted = a.trace or list(traces)
    missing = [t for t in wanted if t not in traces]
    if missing:
        raise RetellError("no runnable block for: {}. Have: {}".format(
            ", ".join(missing), ", ".join(traces)))
    selected = [traces[t] for t in wanted]

    if a.file:
        flow = flow_object(a.file)
        label = Path(a.file).stem
        source = a.file
    else:
        cfg = agent_config(a.client, a.agent)
        flow = client.get_flow(cfg["flow_id"], a.version)
        label = "{}-v{}".format(a.agent, flow.get("version"))
        source = "{} version {}".format(f"{a.client}/{a.agent}", flow.get("version"))

    # --- the sandbox model ---------------------------------------------------
    # Rey, 2026-09-03 and 2026-09-17: chat tests run gpt-4.1-mini or smaller,
    # never gpt-4.1; the client has not approved that cost. `force_test_model` is
    # the same guard `Sandbox` applies, run here first so the header shows it.
    # It works on an in-memory COPY; nothing is written back.
    flow, overrides = force_test_model(flow, a.model)
    print("  model  : {} for the SANDBOX ONLY ({} overrides). "
          "The flow on disk and on Retell is unchanged.".format(
              a.model, overrides))

    turns = sum(len(t["turns"]) for t in selected) * a.reps
    print("=" * 72)
    print("tracerun")
    print("  source : {}  ({} nodes)".format(source, len(flow.get("nodes", []))))
    print("  traces : {}".format(", ".join(wanted)))
    print("  reps   : {}".format(a.reps))
    print("  cost   : {} messages, about ${:.2f}".format(
        turns, turns * CENTS_PER_MESSAGE / 100))
    print("=" * 72)

    if not a.yes:
        try:
            if input("run? [y/N] ").strip().lower() not in ("y", "yes"):
                print("cancelled")
                return 0
        except EOFError:
            print("\nno tty; re-run with --yes to confirm the cost")
            return 2

    overall_pass, results = True, []
    for trace in selected:
        passes, last = 0, None
        print("\n{}  ({} turns)".format(trace["id"], len(trace["turns"])))
        for rep in range(a.reps):
            last = run_once(client, flow, trace, label, a.verbose, a.model)
            if not last["fails"]:
                passes += 1
                print("  rep {}: PASS".format(rep + 1))
            else:
                print("  rep {}: FAIL".format(rep + 1))
                for f in last["fails"]:
                    print("     - {}".format(f))
        if passes < a.reps:
            overall_pass = False
        # Always report the path and the collected variables, not only on a
        # failure. A trace whose subject IS a variable - T-CU and T-AR assert
        # on `uncertain_fields` - passes vacuously when it has no say_times,
        # so a green verdict with nothing printed proves nothing. See
        # docs/lessons-green-verdict-blindness.md.
        print("  path walked: {}".format(" -> ".join(last["path"]) or "(none)"))
        print("  vars       : {}".format(last["vars"]))
        # The BILLED figure, from Retell's own chat_cost, not the pre-run
        # estimate above. The estimate counts messages; this is what the run
        # actually cost, and it moves with the model the flow declares.
        if last.get("cost") is not None:
            print("  billed     : {} (Retell chat_cost.combined_cost)".format(
                last["cost"]))
        results.append((trace["id"], passes, a.reps))

    print("\n" + "=" * 72)
    for tid, passes, reps in results:
        mark = "PASS" if passes == reps else "FAIL"
        print("  {:<6} {}  {}/{}".format(tid, mark, passes, reps))
    print("=" * 72)
    print("VERDICT: {}".format("GREEN" if overall_pass else "RED"))
    print("Sandboxes torn down. Nothing was written to the production flow.")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        sys.exit(2)
