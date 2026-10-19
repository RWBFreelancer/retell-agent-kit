#!/usr/bin/env python3
"""Client-neutral Retell REST wrapper and mode gate. Standard library only.

WHY THIS EXISTS

Retell has three agent types. A conversation flow, a single-prompt agent
(a "Retell LLM"), and a custom LLM websocket. Most tooling people write
covers exactly one of them and hardcodes one client's agent ids. This module
covers the first two and hardcodes nothing.

It also has a real OFFLINE mode. Every command here that does not need the
network runs with no API key at all, so an agent can be designed, linted, and
audited from a retell.json export or from a written brief alone.

ENDPOINTS USED (confirmed against docs.retellai.com, 2026-08-28)

    single prompt (Retell LLM)
      POST   /create-retell-llm
      GET    /get-retell-llm/{llm_id}[?version=N]
      PATCH  /update-retell-llm/{llm_id}[?version=N]
      DELETE /delete-retell-llm/{llm_id}
      GET    /v2/list-retell-llms

    conversation flow
      POST   /create-conversation-flow
      GET    /get-conversation-flow/{id}[?version=N]
      PATCH  /update-conversation-flow/{id}[?version=N]
      DELETE /delete-conversation-flow/{id}

    agent
      POST   /create-agent
      GET    /get-agent/{agent_id}[?version=N]
      PATCH  /update-agent/{agent_id}[?version=N]
      GET    /list-agent-versions/{agent_id}     paged, summary rows only
      POST   /create-agent-version/{agent_id}      body {"base_version": N}
      POST   /publish-agent-version/{agent_id}
      POST   /v2/list-agents
      DELETE /delete-agent/{agent_id}

    text sandbox
      POST   /create-chat-agent
      POST   /create-chat
      POST   /create-chat-completion
      PATCH  /end-chat/{chat_id}
      GET    /get-chat/{chat_id}
      DELETE /delete-chat-agent/{agent_id}

    calls and testing
      POST   /v3/list-calls
      GET    /v2/get-call/{call_id}
      POST   /create-test-case-definition
      POST   /create-batch-test
      GET    /get-batch-test/{batch_id}

THREE RULES THAT DRIVE EVERYTHING

1. update-conversation-flow and update-retell-llm take the WHOLE object,
   not a field patch. So the pattern is always GET, mutate, PATCH back.
2. Those PATCH calls write the latest DRAFT. They never publish.
3. Published versions are immutable and carry live calls. Never target one.

CREDENTIALS

Merged in this order, later wins:
    1. %USERPROFILE%/.retell.env   (the global key, for one-off clients)
    2. .env at the kit root        (every account, see kit/accounts.py)
    3. .env in the current directory, or the nearest parent holding .git
    4. .env.local in the current directory (a client's account choice)
    5. the process environment

Several accounts per service live side by side as KEY__ACCOUNT. A selector
such as RETELL_ACCOUNT=acme promotes that account's keys to the plain
names. See kit/accounts.py.

The API key is never printed, never logged, and never written to a file by
this module. print_env() masks it.

Usage:
    python retellkit.py ping
    python retellkit.py env
    python retellkit.py agents
    python retellkit.py mode
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import accounts  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # older interpreter, or a redirected pipe
    pass

ENV_KEYS = (
    "RETELL_API_KEY",
    "RETELL_BASE_URL",
    "ALLOW_PUBLISH",
)
GLOBAL_ENV = Path.home() / ".retell.env"
KIT_ROOT = Path(__file__).resolve().parent.parent
MODE_FILE = ".retell-mode.json"
DEFAULT_BASE_URL = "https://api.retellai.com"


class RetellError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# environment
# --------------------------------------------------------------------------
def project_root(start=None):
    """Nearest ancestor holding .git or .env. Falls back to the start dir."""
    here = Path(start or Path.cwd()).resolve()
    for d in [here, *here.parents]:
        if (d / ".git").exists() or (d / ".env").exists():
            return d
    return here


def _parse_env_file(path):
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        # strip a trailing inline comment, then whitespace and quotes
        out[key.strip()] = val.split("#")[0].strip().strip('"').strip("'")
    return out


def load_env(start=None):
    """Merge the global env file, the kit .env, the repo .env, a client's
    .env.local, and the process env. Later sources win. Then promote the
    selected account of each service (kit/accounts.py).

    Search order: %USERPROFILE%/.retell.env, then .env at the kit root,
    then .env at the nearest ancestor holding .git or .env, then
    .env.local in the current directory (a per-client override), then the
    process environment.
    """
    root = project_root(start)
    env = _parse_env_file(GLOBAL_ENV)
    env.update(_parse_env_file(KIT_ROOT / ".env"))
    if root != KIT_ROOT:
        env.update(_parse_env_file(root / ".env"))
    env.update(_parse_env_file(Path(start or Path.cwd()) / ".env.local"))
    prefixes = tuple(accounts.SERVICES.values())
    for key, val in os.environ.items():
        if key.startswith(prefixes) or key in ENV_KEYS or key.endswith("_KEY") \
                or key.endswith("_TOKEN") or key.endswith("_SECRET"):
            if val:
                env[key] = val
    try:
        env, _ = accounts.resolve(env)
    except accounts.AccountError as exc:
        raise RetellError(str(exc)) from None
    return env


# --------------------------------------------------------------------------
# client / agent resolution
# --------------------------------------------------------------------------
def clients_root(start=None):
    """Where client folders live, first hit wins:

        1. RETELL_CLIENTS_DIR in the process environment
        2. the nearest ancestor holding .kit-path (a separate retell-clients repo)
        3. <kit>/clients/, when it exists (git-ignored: work inside the kit)
        4. the project root
    """
    if os.environ.get("RETELL_CLIENTS_DIR"):
        return Path(os.environ["RETELL_CLIENTS_DIR"]).resolve()
    here = Path(start or Path.cwd()).resolve()
    for d in [here, *here.parents]:
        if (d / ".kit-path").exists():
            return d
    if (KIT_ROOT / "clients").is_dir():
        return KIT_ROOT / "clients"
    return project_root(start)


def agent_config(client, agent, start=None):
    """Resolve --client <folder> --agent <slug> to its ids, reading
    <clients_root>/<client>/agents/<agent>/AGENT.md.

    AGENT.md holds simple `key: value` lines, for example:

        agent_id: agent_xxxxxxxxxxxx
        flow_id: conversation_flow_xxxxxxxxxxxx
        type: conversation-flow
    """
    path = clients_root(start) / client / "agents" / agent / "AGENT.md"
    if not path.exists():
        raise RetellError(f"no AGENT.md at {path}")
    fields = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        fields[key.strip().lower()] = val.strip()
    fields["client"] = client
    fields["agent"] = agent
    fields["exports"] = path.parent / "exports"
    return fields


def have_key(env=None):
    env = env if env is not None else load_env()
    return bool(env.get("RETELL_API_KEY", "").strip())


def mask(secret):
    """Show only enough to tell two keys apart. Never the key."""
    s = str(secret or "")
    return f"{s[:4]}...{s[-2:]} ({len(s)} chars)" if len(s) > 8 else "set"


def print_env(env=None):
    env = env if env is not None else load_env()
    print(f"global env file : {GLOBAL_ENV}  "
          f"[{'found' if GLOBAL_ENV.exists() else 'absent'}]")
    proj = project_root() / ".env"
    print(f"project env file: {proj}  [{'found' if proj.exists() else 'absent'}]")
    print(f"base_url        : {env.get('RETELL_BASE_URL') or DEFAULT_BASE_URL}")
    print(f"api key         : "
          f"{mask(env.get('RETELL_API_KEY')) if have_key(env) else 'MISSING (offline mode)'}")
    print(f"allow_publish   : {env.get('ALLOW_PUBLISH', 'false')}")
    print(f"retell account  : {env.get('RETELL_ACCOUNT') or '(none selected)'}")


# --------------------------------------------------------------------------
# mode file: answered once, reused by every other skill
# --------------------------------------------------------------------------
def mode_path(start=None):
    return project_root(start) / MODE_FILE


def read_mode(start=None):
    p = mode_path(start)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def write_mode(data, start=None):
    p = mode_path(start)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# client
# --------------------------------------------------------------------------
class RetellClient:
    """Every method here is one HTTP call. Nothing here publishes."""

    def __init__(self, env=None):
        self.env = env if env is not None else load_env()
        self._key = self.env.get("RETELL_API_KEY", "").strip()
        self.base_url = (self.env.get("RETELL_BASE_URL")
                         or DEFAULT_BASE_URL).rstrip("/")
        if not self._key:
            raise RetellError(
                "RETELL_API_KEY is empty. This command needs a key.\n"
                f"Put it in {GLOBAL_ENV} or in .env at the project root, "
                "or use an offline command instead."
                + accounts.hint(self.env, "retell"))

    def __repr__(self):
        return f"<RetellClient base_url={self.base_url} key=***>"

    def _request(self, method, path, body=None, query=None):
        url = f"{self.base_url}{path}"
        if query:
            pairs = "&".join(f"{k}={v}" for k, v in query.items() if v is not None)
            if pairs:
                url = f"{url}?{pairs}"
        data = None
        headers = {"Authorization": f"Bearer {self._key}",
                   "Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:800]
            raise RetellError(
                f"{method} {path} failed: HTTP {exc.code} {exc.reason}\n{detail}"
            ) from None
        except urllib.error.URLError as exc:
            raise RetellError(f"{method} {path} failed: {exc.reason}") from None
        return json.loads(raw) if raw.strip() else {}

    # ---------- single prompt: the Retell LLM object ----------
    def create_llm(self, body):
        """POST /create-retell-llm. Returns the object, including llm_id."""
        return self._request("POST", "/create-retell-llm", body=body)

    def get_llm(self, llm_id, version=None):
        return self._request("GET", f"/get-retell-llm/{llm_id}",
                             query={"version": version})

    def update_llm(self, llm_id, obj, version=None):
        """PATCH the whole object back. Writes the DRAFT, never publishes.

        Read-only response fields are stripped: the API rejects them and the
        server regenerates them anyway.
        """
        payload = {k: v for k, v in dict(obj).items()
                   if k not in ("llm_id", "version", "is_published",
                                "last_modification_timestamp")}
        return self._request("PATCH", f"/update-retell-llm/{llm_id}",
                             body=payload, query={"version": version})

    def delete_llm(self, llm_id):
        return self._request("DELETE", f"/delete-retell-llm/{llm_id}")

    def list_llms(self):
        """GET /v2/list-retell-llms. The unversioned path is deprecated
        (Retell, 2026-06-15). v2 wraps rows in items/pagination_key/has_more."""
        rows, key = [], None
        while True:
            page = self._request("GET", "/v2/list-retell-llms",
                                 query={"pagination_key": key} if key else None)
            rows += (page or {}).get("items") or []
            if not (page or {}).get("has_more"):
                return rows
            key = page.get("pagination_key")

    # ---------- conversation flow ----------
    def create_flow(self, flow_obj):
        payload = {k: v for k, v in dict(flow_obj).items()
                   if k not in ("conversation_flow_id", "version", "is_published",
                                "last_modification_timestamp")}
        return self._request("POST", "/create-conversation-flow", body=payload)

    def get_flow(self, flow_id, version=None):
        return self._request("GET", f"/get-conversation-flow/{flow_id}",
                             query={"version": version})

    def update_flow(self, flow_id, flow_obj, version=None):
        payload = {k: v for k, v in dict(flow_obj).items()
                   if k not in ("conversation_flow_id", "version", "is_published",
                                "last_modification_timestamp")}
        return self._request("PATCH", f"/update-conversation-flow/{flow_id}",
                             body=payload, query={"version": version})

    def delete_flow(self, flow_id):
        return self._request("DELETE", f"/delete-conversation-flow/{flow_id}")

    # ---------- agent ----------
    def create_agent(self, body):
        return self._request("POST", "/create-agent", body=body)

    def get_agent(self, agent_id, version=None):
        return self._request("GET", f"/get-agent/{agent_id}",
                             query={"version": version})

    def update_agent(self, agent_id, fields, version=None):
        """PATCH named fields only. The agent object carries voice, telephony,
        and webhook settings that must not be rewritten by accident."""
        if not isinstance(fields, dict) or not fields:
            raise RetellError("update_agent needs a non-empty dict of fields")
        for banned in ("agent_id", "version", "is_published",
                       "last_modification_timestamp", "response_engine"):
            if banned in fields:
                raise RetellError(
                    f"refusing to PATCH read-only or wiring field {banned!r}")
        return self._request("PATCH", f"/update-agent/{agent_id}",
                             body=fields, query={"version": version})

    def delete_agent(self, agent_id):
        return self._request("DELETE", f"/delete-agent/{agent_id}")

    def list_voices(self):
        """GET /list-voices. Every voice the workspace can use, with
        voice_id, voice_name, provider, gender, accent."""
        out = self._request("GET", "/list-voices")
        return out if isinstance(out, list) else (out or {}).get("items") or []

    def list_agents(self, limit=200):
        """POST /v2/list-agents.

        TRAP: the rows are SLIM. They carry agent_id, agent_name, voice_id,
        channel, tags, is_multi_prompt and response_engine_type -- and NOT
        version, NOT webhook_url, NOT the full response_engine object. Code
        that reads row["response_engine"]["conversation_flow_id"] off this
        list silently gets None. Call get_agent(agent_id) for the real thing.
        """
        out = self._request("POST", "/v2/list-agents", body={"limit": limit})
        if isinstance(out, list):
            return out
        return (out or {}).get("data") or (out or {}).get("items") or []

    def list_agent_versions(self, agent_id):
        """GET /list-agent-versions/{id}, every page, newest first.

        /get-agent-versions was removed on 2026-09-15. Rows are SUMMARIES:
        version, is_published, base_version, last_modification_timestamp.
        No response_engine, no webhook_url. Use get_agent(id, version=N)."""
        rows, key = [], None
        while True:
            query = {"limit": 1000}
            if key:
                query["pagination_key"] = key
            page = self._request("GET", f"/list-agent-versions/{agent_id}",
                                 query=query) or {}
            rows += page.get("items") or []
            if not page.get("has_more"):
                break
            key = page.get("pagination_key")
        return sorted(rows, key=lambda r: r.get("version", 0), reverse=True)

    def create_agent_version(self, agent_id, base_version):
        """POST a new DRAFT agent version built from base_version."""
        return self._request("POST", f"/create-agent-version/{agent_id}",
                             body={"base_version": int(base_version)})

    def publish_agent_version(self, agent_id, version, title=None, description=None):
        """Gated by ALLOW_PUBLISH. No skill in this kit calls this."""
        if str(self.env.get("ALLOW_PUBLISH", "false")).strip().lower() != "true":
            raise RetellError(
                "ALLOW_PUBLISH is not 'true'. Refusing to publish.")
        body = {"version": int(version)}
        if title:
            body["version_title"] = title
        if description:
            body["version_description"] = description
        return self._request("POST", f"/publish-agent-version/{agent_id}", body=body)

    # ---------- text sandbox ----------
    def create_chat_agent(self, response_engine, agent_name=None):
        body = {"response_engine": response_engine}
        if agent_name:
            body["agent_name"] = agent_name
        return self._request("POST", "/create-chat-agent", body=body)

    def create_chat(self, agent_id, dynamic_variables=None):
        body = {"agent_id": agent_id}
        if dynamic_variables:
            body["retell_llm_dynamic_variables"] = dynamic_variables
        return self._request("POST", "/create-chat", body=body)

    def chat_completion(self, chat_id, content):
        return self._request("POST", "/create-chat-completion",
                             body={"chat_id": chat_id, "content": content})

    def end_chat(self, chat_id):
        return self._request("PATCH", f"/end-chat/{chat_id}")

    def get_chat(self, chat_id):
        """Read the finished chat. collected_dynamic_variables is only filled
        in AFTER the chat ends, so always send every turn, end, then read."""
        return self._request("GET", f"/get-chat/{chat_id}")

    def delete_chat_agent(self, agent_id):
        return self._request("DELETE", f"/delete-chat-agent/{agent_id}")

    # ---------- calls ----------
    def list_calls(self, filters=None, limit=50):
        """POST /v3/list-calls, newest first, then GET /v2/get-call per row.

        /v2/list-calls is deprecated (Retell, 2026-06-15). v3 rows carry no
        transcript or transcript_object, so each row is re-read in full."""
        rows, key = [], None
        while len(rows) < limit:
            body = {"limit": min(limit - len(rows), 1000),
                    "sort_order": "descending"}
            if filters:
                body["filter_criteria"] = filters
            if key:
                body["pagination_key"] = key
            page = self._request("POST", "/v3/list-calls", body=body) or {}
            rows += page.get("items") or []
            if not page.get("has_more"):
                break
            key = page.get("pagination_key")
        return [self._request("GET", f"/v2/get-call/{r['call_id']}")
                for r in rows[:limit]]

    # ---------- simulation testing ----------
    def create_test_case(self, name, response_engine, user_prompt, metrics,
                         dynamic_variables=None, llm_model=None):
        body = {"name": name, "response_engine": response_engine,
                "user_prompt": user_prompt, "metrics": list(metrics)}
        if dynamic_variables:
            body["dynamic_variables"] = dynamic_variables
        if llm_model:
            body["llm_model"] = llm_model
        return self._request("POST", "/create-test-case-definition", body=body)

    def create_batch_test(self, test_case_ids, response_engine):
        return self._request("POST", "/create-batch-test",
                             body={"test_case_definition_ids": list(test_case_ids),
                                   "response_engine": response_engine})

    def get_batch_test(self, batch_id):
        return self._request("GET", f"/get-batch-test/{batch_id}")


# --------------------------------------------------------------------------
# small CLI, for proving the plumbing works
# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Retell plumbing check. Read-only. Never writes, "
                    "never publishes.")
    ap.add_argument("command",
                    choices=["env", "ping", "agents", "llms", "flows", "mode"],
                    help="env = show where credentials came from (no network); "
                         "ping = confirm the key authenticates; "
                         "agents/llms = list what the key can see; "
                         "flows = list conversation flows seen on agents; "
                         "mode = show the saved setup mode")
    a = ap.parse_args(argv)
    env = load_env()

    if a.command == "env":
        print_env(env)
        print(f"mode            : "
              f"{'set -> ' + str(mode_path()) if read_mode() else 'not set'}")
        return 0

    if a.command == "mode":
        m = read_mode()
        if not m:
            print("No mode saved. Run the retell-setup skill first.")
            return 1
        print(json.dumps(m, indent=2, ensure_ascii=False))
        return 0

    if not have_key(env):
        print("No API key found. Offline mode.")
        print_env(env)
        print("\nOffline commands that still work:")
        print("  python promptlint.py <prompt-file-or-llm.json>")
        print("  python flowkit.py lint <flow.json>")
        return 1

    client = RetellClient(env)

    if a.command == "ping":
        rows = client.list_agents(limit=200)
        print_env(env)
        print(f"auth            : OK, {len(rows)} agents visible")
        return 0

    if a.command == "agents":
        for r in client.list_agents(limit=200):
            kind = r.get("response_engine_type") or "?"
            if kind == "retell-llm" and r.get("is_multi_prompt"):
                kind = "multi-prompt"
            elif kind == "retell-llm":
                kind = "single-prompt"
            print(f"  {r.get('agent_id')}  {kind:<18} "
                  f"{r.get('agent_name') or '(unnamed)'}")
        return 0

    if a.command == "llms":
        rows = client.list_llms()
        if not rows:
            print("  no single-prompt (Retell LLM) objects in this workspace")
        for r in rows:
            prompt = (r.get("general_prompt") or "").replace("\n", " ")
            print(f"  {r.get('llm_id')}  v{r.get('version')}  "
                  f"{len(r.get('general_prompt') or '')} chars  {prompt[:50]}")
        return 0

    if a.command == "flows":
        # list-agents rows do not carry response_engine, so each candidate
        # needs a real get_agent call. See the trap note on list_agents.
        seen = {}
        for r in client.list_agents(limit=200):
            if r.get("response_engine_type") != "conversation-flow":
                continue
            full = client.get_agent(r["agent_id"])
            eng = full.get("response_engine") or {}
            if eng.get("conversation_flow_id"):
                seen[eng["conversation_flow_id"]] = (
                    f"{full.get('agent_name') or r['agent_id']} "
                    f"(agent v{full.get('version')}, flow v{eng.get('version')})")
        for fid, name in seen.items():
            print(f"  {fid}  used by {name}")
        if not seen:
            print("  no conversation-flow agents in this workspace")
        return 0

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RetellError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
