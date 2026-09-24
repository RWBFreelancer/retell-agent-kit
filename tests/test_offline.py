#!/usr/bin/env python3
"""Kit self-tests. Offline only, no API key, no network. Run with:

    python tests/test_offline.py

Exits 1 on any failure, prints a PASS/FAIL line per check.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

results = []


def check(name, fn):
    try:
        fn()
        results.append((name, True, ""))
    except Exception as exc:  # noqa: BLE001
        results.append((name, False, str(exc)))


def run(args, env=None):
    e = dict(os.environ)
    e["RETELL_API_KEY"] = ""
    if env:
        e.update(env)
    r = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True, env=e)
    return r


def test_flowlint_skeleton():
    r = run(["tools/flowlint.py", "templates/flow-skeleton.json"])
    assert r.returncode == 0, f"exit {r.returncode}: {r.stdout}{r.stderr}"
    assert "UNREACHABLE" in r.stdout


def test_promptlint_template():
    r = run(["kit/promptlint.py", "templates/single-prompt.md"])
    assert r.returncode == 0, f"exit {r.returncode}: {r.stdout}{r.stderr}"
    assert "fail" in r.stdout.lower()


def test_envcheck_prints_no_values():
    r = run(["tools/envcheck.py"])
    assert r.returncode == 0
    assert "RETELL_API_KEY" in r.stdout
    assert "set" in r.stdout or "missing" in r.stdout
    # never a real-looking key value
    assert "key_" not in r.stdout


def test_sandbox_refuses_without_yes():
    r = run(["sandbox/run.py", "--client", "zz-demo", "--agent", "example-agent"])
    assert r.returncode != 0
    assert "--yes" in (r.stdout + r.stderr)


def test_sandbox_refuses_bad_model():
    r = run(["sandbox/run.py", "--client", "zz-demo", "--agent", "example-agent",
             "--model", "gpt-4.1", "--yes"])
    assert r.returncode != 0


def test_agents_md_line_limit():
    lines = (ROOT / "AGENTS.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 200, f"{len(lines)} lines"


def test_env_example_has_every_key():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for key in ("RETELL_API_KEY", "ALLOW_PUBLISH", "N8N_API_KEY",
                "MAKE_API_TOKEN", "GHL_API_KEY", "HUBSPOT_PRIVATE_APP_TOKEN",
                "ZAPIER_WEBHOOK_URL", "TWILIO_ACCOUNT_SID", "CALCOM_API_KEY",
                "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
                "WEBHOOK_SIGNING_SECRET"):
        assert key in example, key


def test_publish_refuses_without_allow_publish():
    r = run(["kit/publishkit.py", "--client", "zz-demo", "--agent", "example-agent",
             "--version", "1", "--title", "t"], env={"ALLOW_PUBLISH": "false"})
    assert r.returncode != 0
    assert "ALLOW_PUBLISH" in (r.stdout + r.stderr)


def test_sandbox_config_valid():
    cfg = json.loads((ROOT / "sandbox" / "config.json").read_text(encoding="utf-8"))
    assert cfg["test_models"]
    assert isinstance(cfg["max_reps_default"], int)


def main():
    check("flowlint on flow-skeleton.json", test_flowlint_skeleton)
    check("promptlint on single-prompt.md", test_promptlint_template)
    check("envcheck prints no values", test_envcheck_prints_no_values)
    check("sandbox/run.py refuses without --yes", test_sandbox_refuses_without_yes)
    check("sandbox/run.py refuses a model not in config.json", test_sandbox_refuses_bad_model)
    check("publishkit.py refuses when ALLOW_PUBLISH is not true", test_publish_refuses_without_allow_publish)
    check("AGENTS.md is 200 lines or fewer", test_agents_md_line_limit)
    check(".env.example lists every key", test_env_example_has_every_key)
    check("sandbox/config.json is valid", test_sandbox_config_valid)

    failed = 0
    for name, ok, msg in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {msg}" if msg else ""))
        failed += not ok
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
