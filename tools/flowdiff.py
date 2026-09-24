#!/usr/bin/env python3
"""Diff two Retell conversation-flow exports and spec the difference.

Built for the workflow where the agent cannot be edited through an API:
export the live agent, compare against the last known export, and hand the
output back as an edit spec.

Usage:
    python3 tools/flowdiff.py <old.json> <new.json> [--out spec.md]
"""
import json, argparse, difflib
from flowlint import load, outgoing, cond_text, words


def index(cf):
    return {n["id"]: n for n in cf["nodes"]}


def edges_of(n):
    out = {}
    for kind, e in outgoing(n):
        out[e.get("id", f"{kind}:{e['destination_node_id']}")] = (
            kind, e["destination_node_id"], cond_text(e))
    return out


def textdiff(a, b, label, lines):
    d = list(difflib.unified_diff(a.splitlines(), b.splitlines(),
                                  lineterm="", n=1))
    if not d:
        return
    lines.append(f"\n**{label}**\n")
    lines.append("```diff")
    lines.extend(d[2:])
    lines.append("```")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--out")
    a = ap.parse_args()

    ao, co = load(a.old)
    an, cn = load(a.new)
    no, nn = index(co), index(cn)
    L = [f"# Flow diff: v{ao.get('version')} -> v{an.get('version')}", ""]

    # agent-level settings
    keys = sorted(set(ao) | set(an))
    rows = [(k, ao.get(k), an.get(k)) for k in keys
            if k not in ("conversationFlow", "response_engine")
            and ao.get(k) != an.get(k)]
    L.append("## Agent settings")
    if not rows:
        L.append("\nNo change.")
    for k, x, y in rows:
        L.append(f"\n- `{k}`: `{json.dumps(x)[:90]}` -> `{json.dumps(y)[:90]}`")

    # dynamic variables
    dvo = co.get("default_dynamic_variables") or {}
    dvn = cn.get("default_dynamic_variables") or {}
    L.append("\n## Dynamic variables")
    if dvo == dvn:
        L.append("\nNo change.")
    for k in sorted(set(dvo) | set(dvn)):
        if dvo.get(k) != dvn.get(k):
            L.append(f"\n- `{k}`: `{dvo.get(k)}` -> `{dvn.get(k)}`")

    # global prompt
    L.append("\n## Global prompt")
    if co.get("global_prompt") == cn.get("global_prompt"):
        L.append("\nNo change.")
    else:
        L.append(f"\n{words(co.get('global_prompt',''))} -> "
                 f"{words(cn.get('global_prompt',''))} words")
        textdiff(co.get("global_prompt", ""), cn.get("global_prompt", ""),
                 "global_prompt", L)

    # nodes
    L.append("\n## Nodes")
    added = [nn[i]["name"] for i in nn if i not in no]
    removed = [no[i]["name"] for i in no if i not in nn]
    if added:
        L.append("\n**Added:** " + ", ".join(f"`{x}`" for x in added))
    if removed:
        L.append("\n**Removed:** " + ", ".join(f"`{x}`" for x in removed))
    if not added and not removed:
        L.append("\nNo nodes added or removed.")

    for nid in nn:
        if nid not in no:
            continue
        a_, b_ = no[nid], nn[nid]
        chunk = []
        if a_["name"] != b_["name"]:
            chunk.append(f"\n- renamed from `{a_['name']}`")
        textdiff(a_.get("instruction", {}).get("text", ""),
                 b_.get("instruction", {}).get("text", ""), "instruction", chunk)
        if a_.get("code") != b_.get("code"):
            textdiff(a_.get("code") or "", b_.get("code") or "", "code", chunk)
        if (a_.get("response_variables") or {}) != (b_.get("response_variables") or {}):
            chunk.append(f"\n- response_variables: "
                         f"`{a_.get('response_variables')}` -> "
                         f"`{b_.get('response_variables')}`")
        ga = (a_.get("global_node_setting") or {}).get("condition", "")
        gb = (b_.get("global_node_setting") or {}).get("condition", "")
        textdiff(ga, gb, "global trigger condition", chunk)

        ea, eb = edges_of(a_), edges_of(b_)
        for eid in sorted(set(ea) | set(eb)):
            if eid not in ea:
                k, d, c = eb[eid]
                chunk.append(f"\n- edge ADDED `{eid}` [{k}] -> "
                             f"`{nn.get(d,{}).get('name',d)}`\n\n  > {c[:400]}")
            elif eid not in eb:
                k, d, c = ea[eid]
                chunk.append(f"\n- edge REMOVED `{eid}` [{k}] -> "
                             f"`{no.get(d,{}).get('name',d)}`")
            elif ea[eid] != eb[eid]:
                k1, d1, c1 = ea[eid]
                k2, d2, c2 = eb[eid]
                if d1 != d2:
                    chunk.append(f"\n- edge `{eid}` REPOINTED: "
                                 f"`{no.get(d1,{}).get('name',d1)}` -> "
                                 f"`{nn.get(d2,{}).get('name',d2)}`")
                if c1 != c2:
                    textdiff(c1, c2, f"edge `{eid}` condition", chunk)
        if chunk:
            L.append(f"\n### `{b_['name']}`")
            L.extend(chunk)

    out = "\n".join(L) + "\n"
    if a.out:
        open(a.out, "w").write(out)
        print(f"wrote {a.out}")
    else:
        print(out)


if __name__ == "__main__":
    main()
