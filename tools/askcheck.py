#!/usr/bin/env python3
"""Did the agent ASK every required question, and ask the closing line
exactly once?

Other tools answer a different question:

  flowlint.py   proves the wiring. It cannot know what was said on a call.
  tracerun.py   counts exact sentences, but only the ones a trace author
                thought to list, one scenario at a time.

The gap this fills: a field can be captured because the caller volunteered
it, and a question can be skipped silently. Both look fine downstream. This
walks a whole call and reports, question by question, whether it was asked,
skipped, or asked twice.

Every required question, and which set applies to which call, comes from
<client>/tests/ask-questions.json. Nothing here is hard-coded, because every
client's questions and wording differ. See templates/ask-questions.example.json.

WHAT IT CHECKS

Every required question is an exact sentence the flow is supposed to speak
word for word. For each one:

  ASKED     said exactly once. What you want.
  TWICE+    said more than once. Always a defect - the flow's whole design is
            one owner and one ask per item.
  SKIPPED   never said. NOT automatically a defect: the caller may have
            volunteered the answer, in which case the node is meant to stay
            quiet. So every SKIPPED row is cross-checked against the
            client's missing-fields variable, and the ones that are both
            skipped AND missing are the real finding: nobody asked, and
            nothing was captured.

The closing line, if configured, gets its own rule: SKIPPED is a defect
there too, on any call that reaches the closing.

WHICH SET APPLIES

Decided from the call itself, using the config's `route_marker`, not from a
flag. A call that ends early is graded on what it reached.

Usage:
    python tools/askcheck.py --client acme --agent intake --all
    python tools/askcheck.py --file acme/agents/intake/exports/v24.json --all
    python tools/askcheck.py --client acme --agent intake --scenario normal
    python tools/askcheck.py --client acme --agent intake --list
    python tools/askcheck.py --client acme --agent intake --message "hi" --message "..."

Costs money: every scenario is a simulated chat. Requires --yes for --all.
Never writes to the production flow and never publishes.
"""
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

from retellkit import RetellClient, RetellError, agent_config, load_env
from retell_chat import (Sandbox, agent_lines, node_hops, flow_object,
                         CENTS_PER_MESSAGE)

# ---------------------------------------------------------------- config
# Every client's required questions and test scenarios differ, so nothing is
# hard-coded here. Load them from <client>/tests/ask-questions.json.
# See templates/ask-questions.example.json for the schema:
#
#   {
#     "missing_fields_var": "missing_fields",
#     "question_sets": {
#       "default": [
#         {"label": "name", "sentence": "Can I get your name", "field": null},
#         {"label": "callback", "sentence": "a good callback number",
#          "field": "preferred_callback_number"}
#       ],
#       "alt_path": [ ... ]
#     },
#     "route_marker": {"set": "alt_path", "sentence": "the exact line that "
#                      "means this call is on the alt path"},
#     "closing_line": "Anything else I should include?",
#     "scenarios": {
#       "normal": ["hi", "caller turn 1", "caller turn 2", "bye"]
#     }
#   }
#
# "route_marker" is optional: omit it if every call uses the same question
# set. Every scenario should open with a filler "hi": the chat sandbox is one
# turn behind a real call, so the first message only produces the greeting
# and its content is discarded.

def load_config(client_name, path=None):
    cfg_path = Path(path) if path else (
        clients_root() / client_name / "tests" / "ask-questions.json")
    if not cfg_path.exists():
        raise RetellError(
            f"no question config at {cfg_path}. Copy "
            f"templates/ask-questions.example.json there and fill it in "
            f"for this client.")
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def clients_root():
    here = Path.cwd().resolve()
    for d in [here, *here.parents]:
        if (d / ".kit-path").exists():
            return d
    return Path.cwd()


def run_scenario(client, flow, label, turns, verbose=False):
    with Sandbox(client, flow, label) as sb:
        chat_id = sb.start()
        said, hops, ended_early = [], [], False
        for turn in turns:
            try:
                msgs = sb.send(chat_id, turn)
            except RetellError as e:
                # The agent hung up before we ran out of caller turns. That is
                # a legitimate outcome, not a tool failure: a sales hard-stop
                # and the incomplete exit both end the call early. Grade what
                # was actually said and stop sending.
                if "already ended" in str(e).lower():
                    ended_early = True
                    break
                raise
            said.extend(agent_lines(msgs))
            hops.extend(n for _, n, _ in node_hops(msgs))
            if verbose:
                print("    CALLER: {}".format(turn))
                for line in agent_lines(msgs):
                    print("      AGENT : {}".format(line))
        if not ended_early:
            sb.end(chat_id)
        rec = sb.record(chat_id)
    return said, hops, (rec.get("collected_dynamic_variables") or {})


def grade(said, dvars, config):
    blob = "\n".join(said)
    marker = config.get("route_marker")
    if marker and marker["sentence"] in blob:
        set_name = marker["set"]
    else:
        set_name = "default"
    questions = [(q["label"], q["sentence"], q.get("field"))
                 for q in config["question_sets"][set_name]]
    missing_var = config.get("missing_fields_var", "missing_fields")
    missing = [f.strip() for f in (dvars.get(missing_var) or "").split(",") if f.strip()]

    rows, defects = [], []
    for label, sentence, field in questions:
        n = blob.count(sentence)
        if n == 1:
            rows.append(("ASKED  ", label, ""))
        elif n > 1:
            rows.append(("TWICE+ ", label, "said {}x".format(n)))
            defects.append("{} asked {} times".format(label, n))
        else:
            if field and field in missing:
                rows.append(("SKIPPED", label,
                             "and {} came back missing".format(field)))
                defects.append(
                    "{} never asked AND {} not captured".format(label, field))
            elif field:
                rows.append(("skipped", label,
                             "caller volunteered {}".format(field)))
            else:
                # No recap field feeds this one, so there is nothing to
                # cross-check it against. It is skipped either because the
                # caller volunteered the answer or because the flow never
                # asked. Only a human reading the turns can tell which.
                rows.append(("skipped", label,
                             "no recap field to cross-check - verify by hand"))

    closing = config.get("closing_line")
    if closing:
        n = blob.count(closing)
        if n == 1:
            rows.append(("ASKED  ", "closing", ""))
        elif n > 1:
            rows.append(("TWICE+ ", "closing", "said {}x".format(n)))
            defects.append("closing line asked {} times".format(n))
        else:
            rows.append(("MISSING", "closing", "never asked"))
            defects.append("closing line never asked")

    return set_name, rows, defects, missing


def main():
    p = argparse.ArgumentParser(
        description="Check that every intake question was asked, once.")
    p.add_argument("--client", required=True, help="client folder name")
    p.add_argument("--agent", required=True, help="agent slug under <client>/agents/")
    p.add_argument("--version", type=int, default=None)
    p.add_argument("--file", default=None,
                   help="test a local export instead of pulling from Retell")
    p.add_argument("--scenario", action="append", default=None,
                   help="scenario name (repeatable). Default: all of them")
    p.add_argument("--message", action="append", default=None,
                   help="drive your own caller turns instead of a scenario")
    p.add_argument("--config", default=None,
                   help="path to the question config, default "
                        "<client>/tests/ask-questions.json")
    p.add_argument("--list", action="store_true", help="show the scenarios")
    p.add_argument("--all", action="store_true", help="run every scenario")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--yes", action="store_true", help="skip the cost prompt")
    a = p.parse_args()

    config = load_config(a.client, a.config)
    scenarios = config.get("scenarios", {})

    if a.list:
        for name, turns in scenarios.items():
            print("  {:16s} {} turns".format(name, len(turns)))
        return 0

    env = load_env()
    client = RetellClient(env)
    if a.file:
        flow, label = flow_object(a.file), Path(a.file).stem
    else:
        cfg = agent_config(a.client, a.agent)
        flow = client.get_flow(cfg["flow_id"], a.version)
        label = "{}-v{}".format(a.agent, flow.get("version"))

    if a.message:
        jobs = [("custom", a.message)]
    else:
        names = a.scenario or list(scenarios)
        jobs = [(n, scenarios[n]) for n in names]

    total = sum(len(t) for _, t in jobs)
    print("=" * 72)
    print("askcheck")
    print("  source   : {}  ({} nodes)".format(label, len(flow.get("nodes", []))))
    print("  scenarios: {}".format(", ".join(n for n, _ in jobs)))
    print("  cost     : {} messages, about ${:.2f}".format(
        total, total * CENTS_PER_MESSAGE / 100))
    print("=" * 72)
    if not (a.yes or a.message):
        print("re-run with --yes to spend it.")
        return 0

    worst = 0
    for name, turns in jobs:
        said, hops, dvars = run_scenario(client, flow, name, turns, a.verbose)
        set_name, rows, defects, missing = grade(said, dvars, config)
        print("\n{}  [{} question set]".format(name, set_name))
        for state, label_, note in rows:
            print("   {}  {:16s} {}".format(state, label_, note))
        print("   missing  : {}".format(", ".join(missing) or "(none)"))
        if defects:
            worst = 1
            print("   DEFECTS:")
            for d in defects:
                print("     - {}".format(d))

    print("\n" + "=" * 72)
    print("VERDICT: {}".format("RED" if worst else "GREEN"))
    print("Nothing was written to the production flow.")
    return worst


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as e:
        print("ERROR: {}".format(e))
        sys.exit(2)
