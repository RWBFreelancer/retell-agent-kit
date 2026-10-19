#!/usr/bin/env python3
"""Shared plumbing for the connected-app kits: n8nkit, makekit, modalkit.

Three things live here, and nothing else:

  1. `http_json()`: one HTTP call with a JSON body, an error that never
     echoes a header, and a timeout.
  2. `snapshot()`: save a workflow or scenario as a new, dated, numbered
     file. Snapshots are immutable, like Retell exports: a new pull is a new
     file, never an overwrite.
  3. `need()`: read required keys from the account-resolved env, with an
     error that names the accounts it saw (kit/accounts.py).

Where snapshots go:

    --client <name>  ->  <clients_root>/<name>/integrations/<platform>/
    no --client      ->  <kit>/results/<platform>/      (git-ignored)

File name: YYYY-MM-DD-vN-<label>.json, N counting up per folder.
"""
import datetime
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import accounts  # noqa: E402
from retellkit import KIT_ROOT, RetellError, clients_root, load_env  # noqa: E402,F401


class IntegrationError(RuntimeError):
    pass


def need(service, *keys, env=None):
    """Return {key: value} for each key, or raise naming what is missing."""
    try:
        env = env if env is not None else load_env()
    except RetellError as exc:  # an AccountError, re-raised by load_env
        raise IntegrationError(str(exc)) from None
    missing = [k for k in keys if not str(env.get(k, "")).strip()]
    if missing:
        raise IntegrationError(
            f"Missing in .env: {', '.join(missing)}." + accounts.hint(env, service))
    return {k: str(env[k]).strip() for k in keys}, env


def http_json(method, url, headers, body=None, timeout=90):
    data = None
    headers = dict(headers)
    headers.setdefault("Accept", "application/json")
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    path = re.sub(r"^https?://[^/]+", "", url).split("?")[0]
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:600]
        raise IntegrationError(
            f"{method} {path} failed: HTTP {exc.code} {exc.reason}\n{detail}") from None
    except urllib.error.URLError as exc:
        raise IntegrationError(f"{method} {path} failed: {exc.reason}") from None
    return json.loads(raw) if raw.strip() else {}


def snapshot_dir(platform, client=None):
    if client:
        d = clients_root() / client / "integrations" / platform
        if not (clients_root() / client).is_dir():
            raise IntegrationError(f"no client folder {clients_root() / client}")
    else:
        d = KIT_ROOT / "results" / platform
    d.mkdir(parents=True, exist_ok=True)
    return d


def snapshot(obj, platform, label, client=None):
    """Write obj as a new numbered file. Never overwrites. Returns the path."""
    d = snapshot_dir(platform, client)
    label = re.sub(r"[^A-Za-z0-9_-]+", "-", str(label)).strip("-")[:60] or "item"
    pat = re.compile(r"^\d{4}-\d{2}-\d{2}-v(\d+)-")
    n = 1 + max([int(m[1]) for f in d.glob("*.json") if (m := pat.match(f.name))],
                default=0)
    path = d / f"{datetime.date.today():%Y-%m-%d}-v{n}-{label}.json"
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
