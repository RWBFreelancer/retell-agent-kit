# retell-agent-kit

A public tool kit for building, testing, and safely editing Retell voice
agents, of both types: conversation flow and single-prompt. It holds no
client data. Client work lives in a separate private repo,
`retell-clients`.

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
cp ../retell-agent-kit/.env.example .env
```

Fill `.env` with real keys. Never commit it; `.gitignore` already excludes
it. See `.env.example` for every key this kit uses.

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
| Build a new agent | The `start-session` skill, then `docs/routes/new-agent.md` |
| Check, test, or edit an existing agent | `docs/routes/existing-agent.md` |
| Understand the folder layout | `AGENTS.md` section 10 |
| See every skill | `AGENTS.md` section 5 |
