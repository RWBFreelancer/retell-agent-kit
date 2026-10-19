# retell-agent-kit

A tool kit for creating, auditing, testing, and safely editing Retell voice
agents, of both types (conversation flow and single-prompt), and the apps
they feed: n8n, Make, Modal, and others. It holds no client data in git.
Client work lives in a separate private repo, `retell-clients`, or in the
git-ignored `clients/` folder here.

## Accounts

One `.env` at the kit root holds every account of every service, each key
with an account suffix. A selector picks one per service:

```bash
cp .env.example .env                                   # then paste values
python tools/accounts.py template n8n acme             # key lines for a new account
python tools/accounts.py list                          # accounts per service, never values
python tools/accounts.py use --client acme retell=acme n8n=acme
```

Rules: `kit/accounts.py`. MCP servers per account: `mcp/README.md`.

Full rules live in [AGENTS.md](AGENTS.md).

## Install

```bash
git clone <this repo> retell-agent-kit
cd retell-agent-kit
pip install -r requirements.txt
```

Python 3.10 or later. Everything except the PDF diagram tool
(`tools/flowdiagram.py`) is standard library only.

## Set up a clients repo

This kit is used from a separate `retell-clients` repo, one folder per
client:

```bash
git clone <your retell-clients repo> retell-clients
cd retell-clients
echo "/absolute/path/to/retell-agent-kit" > .kit-path
```

Keys stay in the kit's `.env` (see Accounts above). Each client folder gets
a `.env.local` naming its accounts, written by `tools/accounts.py use`.
Never commit either; `.gitignore` already excludes both.

## First run

From inside a client folder in `retell-clients`:

```bash
python ../../retell-agent-kit/kit/retellkit.py env    # no key needed
python ../../retell-agent-kit/kit/retellkit.py ping   # needs RETELL_API_KEY
```

Or, in Claude Code, run the `setup` skill and answer its two questions.

## Offline mode

No API key is needed to build, lint, or audit. `promptlint.py` and
`flowkit.py lint` both work with `RETELL_API_KEY` unset:

```bash
python kit/promptlint.py templates/single-prompt.md
python kit/flowkit.py lint templates/flow-skeleton.json
```

## Kit self-tests

```bash
python tests/test_offline.py
```

## Where to go next

| Task | Start here |
|---|---|
| Build a new agent | The `start-session` skill, then `docs/routes/new-agent.md`, then `create-agent` |
| Read or change n8n, Make, or Modal | `check-integration`, `edit-integration`; tools in `kit/` |
| Check, test, or edit an existing agent | `docs/routes/existing-agent.md` |
| Understand the folder layout | `AGENTS.md` section 10 |
| See every skill | `AGENTS.md` section 5 |
