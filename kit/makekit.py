#!/usr/bin/env python3
"""Make (make.com): read and (carefully) write the scenarios a Retell agent
feeds. Account-aware: MAKE_ACCOUNT picks which organization (kit/accounts.py).

Keys, per account:
    MAKE_API_TOKEN__<ACCT>   Make profile > API access > Add token. Scopes:
                             scenarios:read, scenarios:write, hooks:read,
                             teams:read, user:read
    MAKE_ZONE__<ACCT>        the org's zone host, e.g. eu1.make.com, us1.make.com
    MAKE_TEAM_ID__<ACCT>     the team holding the scenarios

READ

    python kit/makekit.py ping
    python kit/makekit.py scenarios [--name recap]
    python kit/makekit.py pull <scenario-id> [--client acme]
    python kit/makekit.py show <snapshot.json>          (offline: module tree)
    python kit/makekit.py logs <scenario-id> [--limit 20]
    python kit/makekit.py hooks                         (webhook URLs per scenario)
    python kit/makekit.py diff <old.json> <new.json>    (offline)

WRITE (dry run unless --apply)

    python kit/makekit.py push <scenario-id> --file edited-snapshot.json [--apply] [--live-ok]

A snapshot holds {"scenario": <metadata>, "blueprint": <blueprint>}. Edit the
blueprint inside a snapshot, then push that file.

GUARDS ON push: the snapshot's `lastEdit` must equal the live one
(`--stale-ok` overrides), an active scenario needs `--live-ok`, snapshots
before and after, read-back compare. It never runs, activates, or deletes a
scenario. Free plans allow about 30 API calls a minute; this tool makes 2-4.
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from integrationkit import IntegrationError, http_json, load_json, need, snapshot  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

SECRET = re.compile(r"(api[_-]?key|token|secret|password|authorization|bearer)", re.I)
STATUS = {1: "success", 2: "warning", 3: "error"}


class MakeClient:
    def __init__(self, env=None):
        vals, self.env = need("make", "MAKE_API_TOKEN", "MAKE_ZONE", env=env)
        zone = re.sub(r"^https?://", "", vals["MAKE_ZONE"]).strip("/")
        self.zone = zone
        self.base = f"https://{zone}/api/v2"
        self._h = {"Authorization": f"Token {vals['MAKE_API_TOKEN']}"}
        self.team = str(self.env.get("MAKE_TEAM_ID") or "").strip()
        self.account = self.env.get("MAKE_ACCOUNT") or "(default)"

    def _q(self, method, path, body=None, query=None):
        url = self.base + path
        if query:
            q = "&".join(f"{k.replace('[', '%5B').replace(']', '%5D')}={v}"
                         for k, v in query.items() if v not in (None, ""))
            url += ("?" + q) if q else ""
        return http_json(method, url, self._h, body)

    def _team(self):
        if not self.team:
            raise IntegrationError("MAKE_TEAM_ID is empty for this account.")
        return self.team

    def me(self):
        return self._q("GET", "/users/me").get("authUser") or {}

    def scenarios(self):
        return self._q("GET", "/scenarios", query={"teamId": self._team(),
                                                    "pg[limit]": 200}).get("scenarios") or []

    def scenario(self, sid):
        return self._q("GET", f"/scenarios/{sid}").get("scenario") or {}

    def blueprint(self, sid):
        return (self._q("GET", f"/scenarios/{sid}/blueprint").get("response") or {}).get("blueprint") or {}

    def logs(self, sid, limit=20):
        return self._q("GET", f"/scenarios/{sid}/logs",
                       query={"pg[limit]": limit, "pg[sortDir]": "desc"}).get("scenarioLogs") or []

    def hooks(self):
        return self._q("GET", "/hooks", query={"teamId": self._team()}).get("hooks") or []

    def patch_blueprint(self, sid, bp):
        return self._q("PATCH", f"/scenarios/{sid}", body={"blueprint": json.dumps(bp)})


def modules(flow, depth=0):
    """Yield (depth, module) through routers."""
    for m in flow or []:
        yield depth, m
        for route in m.get("routes") or []:
            yield from modules(route.get("flow"), depth + 1)


def secrets_in(bp):
    hits = []

    def walk(v, path):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{path}.{k}" if path else k)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{path}[{i}]")
        elif isinstance(v, str) and len(v) >= 12 and "{{" not in v:
            last = path.split(".")[-1]
            if SECRET.search(last) or re.match(r"^Bearer\s+\S{8,}", v, re.I):
                hits.append(path)
    for _, m in modules(bp.get("flow")):
        walk(m.get("mapper") or {}, f"module {m.get('id')} mapper")
    return hits


def cmd_ping(a):
    c = MakeClient()
    me = c.me()
    print(f"account : {c.account}\nzone    : {c.zone}\nteam    : {c.team or '(MAKE_TEAM_ID empty)'}")
    print(f"auth    : OK, user id {me.get('id')}")


def cmd_scenarios(a):
    c = MakeClient()
    print(f"(account {c.account}, {c.zone}, team {c.team})")
    for s in c.scenarios():
        if a.name and a.name.lower() not in (s.get("name") or "").lower():
            continue
        print(f"{s.get('id'):<10} {'ACTIVE' if s.get('isActive') else 'off   '} "
              f"{str(s.get('lastEdit'))[:19]}  {s.get('name')}")


def cmd_pull(a):
    c = MakeClient()
    meta, bp = c.scenario(a.id), c.blueprint(a.id)
    path = snapshot({"scenario": meta, "blueprint": bp}, "make", f"{a.id}-{meta.get('name')}", a.client)
    n = sum(1 for _ in modules(bp.get("flow")))
    print(f"pulled  : {meta.get('name')} ({a.id}) from {c.zone}")
    print(f"active  : {meta.get('isActive')}   lastEdit: {meta.get('lastEdit')}   modules: {n}")
    print(f"saved   : {path}")


def cmd_show(a):
    snap = load_json(a.file)
    bp = snap.get("blueprint") or snap
    print(f"{bp.get('name')}")
    for depth, m in modules(bp.get("flow")):
        keys = ", ".join(sorted((m.get("mapper") or {}).keys()))[:90]
        print(f"{'  ' * depth}[{m.get('id')}] {m.get('module')}  mapper: {keys or '-'}")
    for path in secrets_in(bp):
        print(f"WARN typed-in secret? {path}. Use a Make connection or keychain instead.")


def cmd_logs(a):
    c = MakeClient()
    for r in c.logs(a.id, a.limit):
        print(f"{str(r.get('timestamp'))[:19]}  {STATUS.get(r.get('status'), r.get('status')):<8} "
              f"{r.get('operations', '?'):>4} ops  {r.get('duration', '?'):>6} ms  {r.get('imtId', '')}")


def cmd_hooks(a):
    c = MakeClient()
    for h in c.hooks():
        print(f"{h.get('id'):<9} {'on ' if h.get('enabled') else 'OFF'} scenario {str(h.get('scenarioId')):<9} "
              f"{h.get('name')}  {h.get('url') or ''}")


def cmd_diff(a):
    old, new = load_json(a.old), load_json(a.new)
    ob, nb = old.get("blueprint") or old, new.get("blueprint") or new
    om = {m.get("id"): m for _, m in modules(ob.get("flow"))}
    nm = {m.get("id"): m for _, m in modules(nb.get("flow"))}
    for i in sorted(set(om) - set(nm)):
        print(f"- removed module {i} {om[i].get('module')}")
    for i in sorted(set(nm) - set(om)):
        print(f"+ added module   {i} {nm[i].get('module')}")
    for i in sorted(set(om) & set(nm)):
        x, y = dict(om[i]), dict(nm[i])
        for m in (x, y):
            m.pop("routes", None)
            (m.get("metadata") or {}).pop("designer", None)
        if x != y:
            print(f"~ changed module {i} {nm[i].get('module')}")
            sys.stdout.writelines(difflib.unified_diff(
                json.dumps(x, indent=1, sort_keys=True).splitlines(True),
                json.dumps(y, indent=1, sort_keys=True).splitlines(True), "old", "new", n=1))


def cmd_push(a):
    c = MakeClient()
    snap = load_json(a.file)
    if "blueprint" not in snap or "scenario" not in snap:
        sys.exit("push needs a snapshot from `pull` ({scenario, blueprint}), edited in place.")
    bp = snap["blueprint"]
    live = c.scenario(a.id)
    print(f"account : {c.account} ({c.zone})")
    print(f"target  : {live.get('name')} ({a.id})  active={live.get('isActive')}  lastEdit={live.get('lastEdit')}")
    hits = secrets_in(bp)
    if hits:
        print("REFUSING: typed-in secrets in: " + "; ".join(hits), file=sys.stderr)
        return 1
    if snap["scenario"].get("lastEdit") != live.get("lastEdit") and not a.stale_ok:
        print("REFUSING: the scenario changed since this snapshot. Pull again, or --stale-ok.",
              file=sys.stderr)
        return 1
    if live.get("isActive") and not a.live_ok:
        print("REFUSING: the scenario is ACTIVE and serves real calls. Get a go-ahead, "
              "then pass --live-ok.", file=sys.stderr)
        return 1
    before = c.blueprint(a.id)
    print(f"modules : {sum(1 for _ in modules(before.get('flow')))} -> {sum(1 for _ in modules(bp.get('flow')))}")
    if not a.apply:
        print("\nDRY RUN. Re-run with --apply to write. Nothing was sent.")
        return 0
    print(f"before  : {snapshot({'scenario': live, 'blueprint': before}, 'make', f'{a.id}-before-push', a.client)}")
    c.patch_blueprint(a.id, bp)
    fresh = c.blueprint(a.id)
    print(f"after   : {snapshot({'scenario': c.scenario(a.id), 'blueprint': fresh}, 'make', f'{a.id}-after-push', a.client)}")
    if json.dumps(fresh.get("flow"), sort_keys=True) != json.dumps(bp.get("flow"), sort_keys=True):
        print("WARN: the live blueprint differs from the file (Make may normalise metadata). "
              "Run diff on the after-snapshot before calling this landed.", file=sys.stderr)
        return 1
    print("MATCHES: the live blueprint flow reads back as sent.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make scenarios for Retell agents. Writes only with push --apply.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping")
    p = sub.add_parser("scenarios")
    p.add_argument("--name")
    p = sub.add_parser("pull")
    p.add_argument("id")
    p.add_argument("--client")
    p = sub.add_parser("show")
    p.add_argument("file")
    p = sub.add_parser("logs")
    p.add_argument("id")
    p.add_argument("--limit", type=int, default=20)
    sub.add_parser("hooks")
    p = sub.add_parser("diff")
    p.add_argument("old")
    p.add_argument("new")
    p = sub.add_parser("push")
    p.add_argument("id")
    p.add_argument("--file", required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--live-ok", action="store_true")
    p.add_argument("--stale-ok", action="store_true")
    p.add_argument("--client")
    a = ap.parse_args(argv)
    fn = {"ping": cmd_ping, "scenarios": cmd_scenarios, "pull": cmd_pull, "show": cmd_show,
          "logs": cmd_logs, "hooks": cmd_hooks, "diff": cmd_diff, "push": cmd_push}[a.cmd]
    return fn(a) or 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except IntegrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
