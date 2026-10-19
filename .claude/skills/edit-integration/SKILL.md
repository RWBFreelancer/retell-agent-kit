---
name: edit-integration
description: Checklist for changing a client's post-call integration workflow safely - trace the data from the Retell webhook to every output, change one code node at a time, execute the new code against real payloads and edge cases before pushing, then verify from a fresh pull. Covers n8n, Make, and Modal (kit/n8nkit.py, kit/makekit.py, kit/modalkit.py), with the same approach for GoHighLevel and Zapier. Account-aware. Use for any change to a code node, a downstream payload, recap logic, or an alert.
---

# Edit integration

A code node that parses fine can still throw on every call. Execute it
before it ships.

## Before changing

- [ ] Run `check-integration`. Pull the live workflow. If `updatedAt`
  moved since the last snapshot, find out why.
- [ ] **Trace the data start to finish.** From the raw Retell payload,
  through every node that touches the field, to every output: recap
  email, downstream payload, alert. List each consumer of the field.
- [ ] **Does a downstream system own this field's contract?** Tell its
  owner before changing it, if one exists.
- [ ] Count how many real calls the change affects, inside the right
  schema window. See `check-agent-data`.
- [ ] Check disabled nodes the change could wake. A disabled alert node
  must stay disabled unless asked for.

## Pick the write path

| Change | Path |
|---|---|
| One line in one n8n code node of a live workflow | A one-off tool per change, below. Safest. |
| Several n8n nodes, or a new or off workflow | Edit a fresh `kit/n8nkit.py pull` snapshot, then `n8nkit.py push <id> --file <edited>` |
| A Make scenario | Edit the `blueprint` inside a fresh `kit/makekit.py pull` snapshot, then `makekit.py push <id> --file <edited>` |
| A Modal app | Edit `<client>/integrations/modal/*.py`, `modalkit.py serve` to test, `modalkit.py deploy` |
| Building a new n8n workflow | The n8n MCP Workflow SDK (`get_workflow_sdk_reference` first) or a JSON file, then `n8nkit.py lint` |

Every path: confirm the account first (`tools/accounts.py list --client
<name>`). Every push is a dry run until `--apply`. `push` refuses a file
pulled before someone else's edit, and refuses an active workflow or
scenario unless `--live-ok`. `--live-ok` needs the client's go-ahead for
that change, like a publish. Before calling a workflow done, walk
`docs/reference/n8n-production-checklist.md`.

## Writing a one-off code-node change

- [ ] One tool per change, modeled on `tools/examples/n8n_apply_example.py`. Copy it. Dry run by default, `--apply` to write.
- [ ] **Anchor on a literal string that appears exactly once**, and assert
  the count is 1. Never walk back to the nearest `return`, `}`, or
  `const`. It finds the wrong one.
- [ ] Refuse to run if the live code is not what the tool expects, or if
  a safety node changed state.
- [ ] Snapshot the workflow to `<client>/integrations/` before and after,
  dated and named for the change.
- [ ] Touch only the named nodes, and say which in the docstring.
- [ ] **Search the whole live node for every name you declare.** A
  second `const` of an existing name throws on every call, and the diff
  will not show it.

## Stress test before applying

`node` is installed. Use it.

1. [ ] Write the proposed code to the session scratchpad and run
   `node --check`. This catches syntax only. A scoping bug still passes it.
2. [ ] **Execute it.** Stub `$json` and `$()` with `.first()` and `.item`.
   Feed it a **real** payload saved from an execution, not from pinned
   test fixtures.
   - Model every output of a node read with `$('X')`. With no index,
     `.first()` reads the output linked to this node, which may be an
     empty error output.
   - Stub any workflow static-data accessor with a fresh object per run.
3. [ ] Run every shape the change must handle, plus one it must leave
   alone. At minimum:
   - the target case
   - the field absent, `null`, `""`, `"unknown"`, `"Not provided"`
   - a case that must stay unchanged
   - caller ID present and absent, stated number present and absent,
     when numbers matter
4. [ ] Print the output for each shape next to the expected value.
5. [ ] Only then `--apply`.

## After applying

- [ ] The tool prints `MATCHES`. Then verify again from **your own**
  fresh pull, checking that every earlier live change is still there,
  not only this one.
- [ ] Write those checks as exact line matches. A loose substring can
  appear legitimately inside new code and give a false fail.
- [ ] Watch the next real execution that hits the path.
- [ ] Log it with `log-results`.

## Reversal

Every change has two routes: the pre-change snapshot, or reversing the
one line the tool's docstring names. Name both before applying.
