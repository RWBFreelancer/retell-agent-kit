#!/usr/bin/env python3
"""Run Retell's own Simulation Testing against a flow version. Read-only.

Retell grades a simulated call against plain-English success criteria and
returns pass, fail or error plus an explanation and the transcript.

  docs.retellai.com/test/llm-simulation-testing

How it differs from tracerun.py, which stays:

  tracerun.py   sends scripted caller turns and counts exact sentences. It is
                the stronger tool for double-say detection, because a repeat is
                counted, not judged.
  simtest.py    lets Retell improvise a caller from a persona and judge the
                whole call. It is the stronger tool for "did this call actually
                work", and it catches things no script anticipated.

Run both. Neither replaces the other.

Endpoints, confirmed against the API reference:

  POST /create-test-case-definition   name, response_engine, user_prompt,
                                      metrics[], dynamic_variables?, llm_model?
  POST /create-batch-test             test_case_definition_ids[], response_engine
  GET  /get-batch-test/{id}           status, pass_count, fail_count, error_count
  GET  /v2/list-test-runs           per-run results
  GET  /get-test-run/{id}             status, result_explanation, transcript

response_engine takes {"type": "conversation-flow", "conversation_flow_id": ...,
"version": N}, so a DRAFT version can be targeted directly. Nothing here writes
to the flow and nothing publishes.

Costs real money: each case is a simulated call. Requires --yes.

BLOCKED WHILE THE FLOW RUNS gpt-4.1. Rey, 2026-09-17: tests use gpt-4.1-mini
or smaller; the client has not approved gpt-4.1 test runs. Simulation Testing runs
the REAL flow version with that version's own `model_choice`, which on both
agents is gpt-4.1, and the API offers no override for the agent's model. So
`run` refuses any flow version that names a model outside
`retell_chat.TEST_MODELS`, which today is every real version. The simulated
caller's `llm_model` is forced to gpt-4.1-mini. Use `tracerun.py` instead.

Usage:
    python tools/simtest.py list
    python tools/simtest.py run --agent b --yes
    python tools/simtest.py run --agent b --version 21 --case B-SIM-2 --yes
"""
import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from retellkit import RetellClient, RetellError, agent_config, clients_root  # noqa: E402
from retell_chat import TEST_MODELS, DEFAULT_TEST_MODEL  # noqa: E402


def spec_path(client_name):
    return clients_root() / client_name / "tests" / "simtests.json"


def _models(o):
    """Every model named in any `model_choice` of a flow object."""
    if isinstance(o, dict):
        mc = o.get("model_choice")
        if isinstance(mc, dict):
            yield mc.get("model")
        for k, v in o.items():
            if k != "model_choice":
                yield from _models(v)
    elif isinstance(o, list):
        for v in o:
            yield from _models(v)


def load_cases(client_name, only=None):
    spec = json.loads(spec_path(client_name).read_text(encoding="utf-8"))
    cases = spec["cases"]
    if only:
        cases = [c for c in cases if c["name"].split()[0] == only
                 or c["name"] == only]
        if not cases:
            have = [c["name"].split()[0] for c in spec["cases"]]
            raise RetellError(f"no case matching {only!r}. Have: {have}")
    return cases


def cmd_list(args):
    for c in load_cases(args.client):
        print(f"  {c['name']}")
        for m in c["metrics"]:
            print(f"      - {m[:96]}")
    return 0


def cmd_run(args):
    cfg = agent_config(args.client, args.agent)
    client = RetellClient()
    cases = load_cases(args.client, args.case)

    flow = client.get_flow(cfg["flow_id"])
    version = args.version if args.version is not None else flow.get("version")

    # Rey, 2026-09-17: no gpt-4.1 test runs. The agent under test uses the
    # version's own model and cannot be overridden, so refuse before any cost.
    tested = client.get_flow(cfg["flow_id"], version)
    models = sorted({m for m in _models(tested) if m})
    bad = [m for m in models if m not in TEST_MODELS]
    if bad:
        raise RetellError(
            "refusing: flow version {} runs {}. Simulation Testing would bill "
            "that model and the client has not approved gpt-4.1 test runs (Rey, "
            "2026-09-17). Use tracerun.py, which runs {}.".format(
                version, ", ".join(bad), DEFAULT_TEST_MODEL))

    print("=" * 72)
    print("simtest  (Retell Simulation Testing)")
    print(f"  agent   : {f"{a.client}/{a.agent}"}")
    print(f"  flow    : {cfg['flow_id']}  version {version}")
    print(f"  cases   : {len(cases)}")
    print(f"  cost    : {len(cases)} simulated calls, billed by Retell")
    print("=" * 72)
    if not args.yes:
        print("\nre-run with --yes to confirm the cost. Nothing was sent.")
        return 0

    print("\n[1/3] Creating test case definitions ...")
    ids, by_id = [], {}
    for c in cases:
        made = client.create_test_case(
            name=c["name"], flow_id=cfg["flow_id"], version=version,
            user_prompt=c["user_prompt"], metrics=c["metrics"],
            dynamic_variables=c.get("dynamic_variables"),
            llm_model=DEFAULT_TEST_MODEL)
        tid = made["test_case_definition_id"]
        ids.append(tid)
        by_id[tid] = c["name"]
        print(f"      {c['name']}  ->  {tid}")

    print("\n[2/3] Launching batch ...")
    batch = client.create_batch_test(ids, cfg["flow_id"], version=version)
    bid = batch["test_case_batch_job_id"]
    print(f"      batch {bid}  status {batch.get('status')}")

    print("\n[3/3] Waiting ...")
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        time.sleep(args.poll)
        batch = client.get_batch_test(bid)
        done = (batch.get("pass_count", 0) + batch.get("fail_count", 0)
                + batch.get("error_count", 0))
        print(f"      {batch.get('status')}  "
              f"pass {batch.get('pass_count')}  fail {batch.get('fail_count')}  "
              f"error {batch.get('error_count')}  of {batch.get('total_count')}")
        if batch.get("status") == "complete":
            break
    else:
        print("      TIMED OUT waiting. The batch is still running on Retell.")
        print(f"      check later: batch id {bid}")
        return 1

    print("\n" + "=" * 72)
    runs = client.list_test_runs(bid)
    verdicts = []
    for r in runs:
        job = r.get("test_case_job_id")
        detail = client.get_test_run(job) if job else r
        snap = detail.get("test_case_definition_snapshot") or {}
        name = snap.get("name") or by_id.get(
            snap.get("test_case_definition_id"), "?")
        status = str(detail.get("status", "?")).upper()
        verdicts.append(status)
        print(f"\n{status:6}  {name}")
        why = detail.get("result_explanation")
        if why:
            for line in str(why).splitlines():
                print(f"        {line}")
    print("\n" + "=" * 72)
    print(f"  pass {batch.get('pass_count')}   fail {batch.get('fail_count')}"
          f"   error {batch.get('error_count')}   of {batch.get('total_count')}")
    ok = batch.get("fail_count", 0) == 0 and batch.get("error_count", 0) == 0
    print("VERDICT: " + ("GREEN" if ok else "RED"))
    print("=" * 72)
    print("Nothing was written to the flow. Nothing was published.")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    ls = sub.add_parser("list", help="show the cases in <client>/tests/simtests.json")
    ls.add_argument("--client", required=True, help="client folder name")

    r = sub.add_parser("run", help="create the cases and run them")
    r.add_argument("--client", required=True, help="client folder name")
    r.add_argument("--agent", required=True, help="agent slug under <client>/agents/")
    r.add_argument("--version", type=int, default=None,
                   help="flow version to test (default: latest, i.e. the draft)")
    r.add_argument("--case", default=None, help="run one case, e.g. B-SIM-2")
    r.add_argument("--yes", action="store_true", help="confirm the cost")
    r.add_argument("--poll", type=int, default=15)
    r.add_argument("--timeout", type=int, default=900)

    args = ap.parse_args(argv)
    return cmd_list(args) if args.cmd == "list" else cmd_run(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
