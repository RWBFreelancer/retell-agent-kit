---
name: publish
description: The only path to publish a Retell agent version. Checks every gate before publishing, then runs the delivery check after. Use only when Rey has given an explicit go-ahead naming the agent and the version.
---

# Publish

This is the only route to a live publish in this kit. No other skill or
tool flips a version live.

## Gate. All must hold.

1. `ALLOW_PUBLISH=true` in `.env`. If it is `false` or missing, stop.
   Only Rey flips this switch, by hand.
2. Rey's go-ahead is in this session, and it names the agent and the
   exact version number. A client's "yes, looks good" is a requirement,
   not this go-ahead. A go-ahead from a past session does not count.
3. Lint is clean, and traces pass or match the unchanged baseline.
4. A version title and a changelog entry are written.
5. A reversal route is named: the previous published version number.

If any check fails, do not publish. Tell Rey which one, and stop.

## Publish

```bash
K=$(cat .kit-path)
python "$K/kit/publishkit.py" --client <name> --agent <slug> --version <N> \
    --title "<version title>" --description "<what changed>"
```

The tool itself refuses when `ALLOW_PUBLISH` is not `true`, when no
`--version` is given, and when the target version is already published.
This is a second, independent check; do not rely on the skill
instructions alone.

## After publish

Run `delivery-check` immediately. Report the result plainly: pass or
fail, and what it proves.

## A go-ahead covers one publish only

It does not carry to the next change, even a small one. Ask again.

Any change to a payload field that a downstream system reads must be
announced to that system's owner before it ships, publish or not.
