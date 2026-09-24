#!/usr/bin/env python3
"""Draw a Retell conversation flow as a PDF flow diagram.

WHY THIS EXISTS

The Retell dashboard shows a node canvas, but it does not show the call as a
path: global nodes float free, edge conditions are hidden behind clicks, and
the safety gates make the graph hard to read at a glance. A client can follow
this picture without opening Retell.

WHAT IT DRAWS

  - Every node in the flow, none omitted, each with a reference number.
  - Every edge: normal, `else_edge`, and `always_edge`, drawn differently.
  - Global nodes in their own band, because they can fire from ANY node after a
    caller turn and are not reached by an ordinary edge.
  - A reference table listing every node by number, name, id, type and exits.

Colour is by node type, and the shapes carry the meaning too, so the page still
reads when printed in black and white.

LAYOUT

Layered, top to bottom. A node's layer is its shortest hop count from the start
node. Nodes no edge reaches sit in a final band. Within a layer, nodes are
ordered by the average position of their parents, one barycentre pass, which is
enough to keep the common paths from crossing.

This is a drawing tool. It reads an export and writes a PDF. It never talks to
Retell and it never writes to the flow.

USAGE

    python tools/flowdiagram.py --client acme-dental --agent intake --out diagram.pdf
    python tools/flowdiagram.py --file acme-dental/agents/intake/exports/v54.json --out x.pdf
"""
import argparse
import json
import os
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

from reportlab.lib.colors import Color, HexColor, black, white
from reportlab.lib.pagesizes import A2, A3, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


# ------------------------------------------------------------------ palette
# Chosen to stay distinguishable in greyscale: the fills differ in lightness.
STYLE = {
    "conversation": dict(fill=HexColor("#E8F0FB"), line=HexColor("#2C5F9E"), label="speaks"),
    "branch":       dict(fill=HexColor("#FFF3D6"), line=HexColor("#B07D1A"), label="decides, silent"),
    "code":         dict(fill=HexColor("#EDEDED"), line=HexColor("#5C5C5C"), label="sets variables, silent"),
    "extract_dynamic_variables": dict(fill=HexColor("#EAF7EE"), line=HexColor("#2E7D46"),
                                      label="reads the call, silent"),
    "end":          dict(fill=HexColor("#FBE3E3"), line=HexColor("#A32C2C"), label="ends the call"),
}
DEFAULT_STYLE = dict(fill=HexColor("#F4F4F4"), line=HexColor("#777777"), label="other")
GLOBAL_LINE = HexColor("#7B2D8E")

BOX_W, BOX_H = 62 * mm, 17 * mm
H_GAP, V_GAP = 7 * mm, 22 * mm


def style_for(node):
    return STYLE.get(node.get("type"), DEFAULT_STYLE)


# ------------------------------------------------------------------- model
def load(path):
    return json.load(open(path, encoding="utf-8"))


def out_edges(node):
    """Every exit a node has, as (kind, destination_id, condition_text)."""
    res = []
    for e in (node.get("edges") or []):
        c = e.get("transition_condition") or {}
        txt = c.get("prompt") or ""
        if not txt and c.get("equations"):
            parts = []
            for q in c["equations"]:
                parts.append("%s %s %s" % (q.get("left"), q.get("operator"), q.get("right")))
            txt = (" and " if c.get("operator") == "&&" else " or ").join(parts)
        res.append(("edge", e.get("destination_node_id"), txt))
    if node.get("else_edge"):
        res.append(("else", node["else_edge"].get("destination_node_id"), "else"))
    if node.get("always_edge"):
        res.append(("always", node["always_edge"].get("destination_node_id"), "always"))
    if node.get("skip_response_edge"):
        res.append(("skip", node["skip_response_edge"].get("destination_node_id"), "skip response"))
    return [(k, d, t) for k, d, t in res if d]


def layer_nodes(flow):
    """Shortest hop count from the start node. Unreached nodes go last."""
    nodes = {n["id"]: n for n in flow["nodes"]}
    start = flow.get("start_node_id")
    adj = defaultdict(list)
    for n in flow["nodes"]:
        for _, dst, _ in out_edges(n):
            if dst in nodes:
                adj[n["id"]].append(dst)

    globals_ = [n["id"] for n in flow["nodes"] if n.get("global_node_setting")]

    # Seed the walk from the start node AND from every global node. A global can
    # fire from anywhere, so the nodes it hands to are genuinely reachable even
    # though no ordinary edge points at them. Seeding only from `start` marked
    # Roadside Line and both Safety Lines as unreachable, which is wrong: they
    # are the whole roadside branch, entered through the safety gate.
    depth = {}
    frontier = []
    if start in nodes:
        depth[start] = 0
        frontier.append(start)
    for g in globals_:
        if g not in depth:
            depth[g] = 0
            frontier.append(g)
    while frontier:
        nxt = []
        for u in frontier:
            for v in adj[u]:
                if v not in depth:
                    depth[v] = depth[u] + 1
                    nxt.append(v)
        frontier = nxt

    # The globals themselves get their own band, so lift them out of the layers.
    for g in globals_:
        depth.pop(g, None)

    unreached = [n["id"] for n in flow["nodes"]
                 if n["id"] not in depth and n["id"] not in globals_]
    maxd = max(depth.values()) if depth else 0
    for u in unreached:
        depth[u] = maxd + 1

    layers = defaultdict(list)
    for nid, d in depth.items():
        layers[d].append(nid)

    # one barycentre pass, so children sit under their parents
    parents = defaultdict(list)
    for n in flow["nodes"]:
        for _, dst, _ in out_edges(n):
            parents[dst].append(n["id"])
    for d in sorted(layers):
        if d == 0:
            layers[d].sort(key=lambda i: nodes[i]["name"])
            continue
        prev = {nid: i for i, nid in enumerate(layers[d - 1])}
        def bary(nid):
            ps = [prev[p] for p in parents.get(nid, []) if p in prev]
            return sum(ps) / len(ps) if ps else 1e6
        layers[d].sort(key=lambda i: (bary(i), nodes[i]["name"]))

    return nodes, layers, globals_, unreached


# ------------------------------------------------------------------ drawing
def fit(text, width, size, cnv, font="Helvetica"):
    """Longest prefix of text that fits, with an ellipsis if trimmed."""
    if cnv.stringWidth(text, font, size) <= width:
        return text
    while text and cnv.stringWidth(text + "...", font, size) > width:
        text = text[:-1]
    return text + "..."


def draw_box(cnv, x, y, node, ref, is_global):
    st = style_for(node)
    cnv.setFillColor(st["fill"])
    cnv.setStrokeColor(GLOBAL_LINE if is_global else st["line"])
    cnv.setLineWidth(2.0 if is_global else 1.1)
    if is_global:
        cnv.setDash(4, 3)
    cnv.roundRect(x, y, BOX_W, BOX_H, 3 * mm, stroke=1, fill=1)
    cnv.setDash()

    # reference number, top-left
    cnv.setFillColor(GLOBAL_LINE if is_global else st["line"])
    cnv.setFont("Helvetica-Bold", 8)
    cnv.drawString(x + 2.4 * mm, y + BOX_H - 5.4 * mm, str(ref))

    cnv.setFillColor(black)
    cnv.setFont("Helvetica-Bold", 8.4)
    name = fit(node.get("name") or node["id"], BOX_W - 12 * mm, 8.4, cnv, "Helvetica-Bold")
    cnv.drawString(x + 8.4 * mm, y + BOX_H - 5.4 * mm, name)

    cnv.setFillColor(HexColor("#555555"))
    cnv.setFont("Helvetica", 6.6)
    kind = node.get("type", "?")
    if is_global:
        kind += "  (GLOBAL)"
    cnv.drawString(x + 2.4 * mm, y + BOX_H - 10.2 * mm, kind)

    itype = (node.get("instruction") or {}).get("type")
    exits = len(out_edges(node))
    tail = "%s | %d exit%s" % (itype or "no instruction", exits, "" if exits == 1 else "s")
    cnv.drawString(x + 2.4 * mm, y + 3.0 * mm, fit(tail, BOX_W - 5 * mm, 6.6, cnv))


def draw_arrow(cnv, x1, y1, x2, y2, kind, label="", faded=False):
    colours = {"edge": HexColor("#3A6FB0"), "else": HexColor("#B07D1A"),
               "always": HexColor("#2E7D46"), "skip": HexColor("#8A8A8A")}
    if faded:
        colours = {k: HexColor("#C9B2D4") for k in colours}
    cnv.setStrokeColor(colours.get(kind, black))
    cnv.setLineWidth(0.5 if faded else (0.8 if kind == "edge" else 1.0))
    if kind == "else":
        cnv.setDash(3, 2)
    elif kind == "skip":
        cnv.setDash(1, 3)
    cnv.line(x1, y1, x2, y2)
    cnv.setDash()

    # arrow head
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    for s in (2.6, -2.6):
        cnv.line(x2, y2,
                 x2 - 3.2 * mm * math.cos(ang - s * 0.12),
                 y2 - 3.2 * mm * math.sin(ang - s * 0.12))
    if label:
        cnv.setFillColor(colours.get(kind, black))
        cnv.setFont("Helvetica-Oblique", 5.6)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        cnv.drawCentredString(mx, my + 1.2 * mm, fit(label, 34 * mm, 5.6, cnv, "Helvetica-Oblique"))


def header(cnv, W, H, title, sub):
    cnv.setFillColor(HexColor("#12314F"))
    cnv.rect(0, H - 16 * mm, W, 16 * mm, stroke=0, fill=1)
    cnv.setFillColor(white)
    cnv.setFont("Helvetica-Bold", 15)
    cnv.drawString(14 * mm, H - 10.4 * mm, title)
    cnv.setFont("Helvetica", 8.6)
    cnv.drawRightString(W - 14 * mm, H - 10.2 * mm, sub)


def legend(cnv, W, H):
    y = H - 24 * mm
    x = 14 * mm
    cnv.setFillColor(black)
    cnv.setFont("Helvetica-Bold", 8)
    cnv.drawString(x, y + 1 * mm, "NODE TYPES")
    x += 24 * mm
    for kind, st in list(STYLE.items()):
        cnv.setFillColor(st["fill"])
        cnv.setStrokeColor(st["line"])
        cnv.setLineWidth(1)
        cnv.roundRect(x, y - 1.6 * mm, 5 * mm, 4 * mm, 1 * mm, stroke=1, fill=1)
        cnv.setFillColor(black)
        cnv.setFont("Helvetica", 7)
        t = "%s, %s" % (kind.replace("_", " "), st["label"])
        cnv.drawString(x + 6.4 * mm, y - 0.4 * mm, t)
        x += 8 * mm + cnv.stringWidth(t, "Helvetica", 7) + 7 * mm

    y -= 6.5 * mm
    x = 14 * mm
    cnv.setFont("Helvetica-Bold", 8)
    cnv.drawString(x, y + 1 * mm, "ARROWS")
    x += 24 * mm
    for kind, desc in (("edge", "a condition the model or an equation judges"),
                       ("else", "else edge, taken when nothing above matched"),
                       ("always", "always edge, taken every time"),
                       ("skip", "skip response edge")):
        cnv.setStrokeColor({"edge": HexColor("#3A6FB0"), "else": HexColor("#B07D1A"),
                            "always": HexColor("#2E7D46"), "skip": HexColor("#8A8A8A")}[kind])
        cnv.setLineWidth(1.1)
        if kind == "else":
            cnv.setDash(3, 2)
        elif kind == "skip":
            cnv.setDash(1, 3)
        cnv.line(x, y, x + 9 * mm, y)
        cnv.setDash()
        cnv.setFillColor(black)
        cnv.setFont("Helvetica", 7)
        cnv.drawString(x + 10.4 * mm, y - 1 * mm, desc)
        x += 12 * mm + cnv.stringWidth(desc, "Helvetica", 7) + 7 * mm

    y -= 6.5 * mm
    cnv.setStrokeColor(GLOBAL_LINE)
    cnv.setLineWidth(2)
    cnv.setDash(4, 3)
    cnv.roundRect(14 * mm, y - 1.6 * mm, 5 * mm, 4 * mm, 1 * mm, stroke=1, fill=0)
    cnv.setDash()
    cnv.setFillColor(black)
    cnv.setFont("Helvetica", 7)
    cnv.drawString(21 * mm, y - 0.4 * mm,
                   "A purple dashed box is a GLOBAL node. No arrow reaches it. It can take over from ANY "
                   "node, but only after the caller has spoken, and it hands the caller back where they were.")


def draw_flow_page(cnv, flow, label, page_w, page_h, refs):
    """Lay the graph out in world units, then scale it once so it fits the page.

    Scaling the whole drawing beats shrinking the boxes: the proportions and the
    line weights stay consistent between the two agents, so the pages can be
    compared side by side even though one flow is deeper than the other.
    """
    nodes, layers, globals_, unreached = layer_nodes(flow)
    header(cnv, page_w, page_h,
           "%s  -  conversation flow" % label,
           "%d nodes  |  flow version %s  |  every node is numbered and listed in the reference table"
           % (len(flow["nodes"]), flow.get("version")))
    legend(cnv, page_w, page_h)

    # ---- world layout, y grows downward from 0 ------------------------------
    pos = {}
    wy = 0.0
    if globals_:
        wy += 8 * mm
        total = len(globals_) * BOX_W + (len(globals_) - 1) * H_GAP
        x = -total / 2.0
        for gid in globals_:
            pos[gid] = (x, wy)
            x += BOX_W + H_GAP
        wy += BOX_H + 16 * mm

    global_band_bottom = wy
    for d in sorted(layers):
        row = layers[d]
        total = len(row) * BOX_W + (len(row) - 1) * H_GAP
        x = -total / 2.0
        for nid in row:
            pos[nid] = (x, wy)
            x += BOX_W + H_GAP
        wy += BOX_H + V_GAP

    xs = [p[0] for p in pos.values()]
    minx, maxx = min(xs), max(xs) + BOX_W
    need_w, need_h = maxx - minx, wy

    avail_w = page_w - 20 * mm
    avail_h = page_h - 46 * mm - 12 * mm
    scale = min(1.0, avail_w / need_w, avail_h / need_h)

    slack = avail_h - need_h * scale
    cnv.saveState()
    # world origin at the top-left of the drawing area, y downward, and the
    # whole drawing centred in whatever room is left over
    cnv.translate((page_w - need_w * scale) / 2.0 - minx * scale,
                  page_h - 46 * mm - slack / 2.0)
    cnv.scale(scale, scale)

    def box_xy(nid):
        x, y = pos[nid]
        return x, -y - BOX_H          # flip: world y down -> pdf y up

    # arrows first, boxes on top
    for n in flow["nodes"]:
        if n["id"] not in pos:
            continue
        sx, sy = box_xy(n["id"])
        # A global node hands back to many places. Drawn at full weight those
        # arrows cross the whole page and bury the main chain, so they are faded.
        faded = n["id"] in globals_
        for kind, dst, cond in out_edges(n):
            if dst not in pos:
                continue
            dx, dy = box_xy(dst)
            if dy < sy:                       # normal, downward
                x1, y1 = sx + BOX_W / 2, sy
                x2, y2 = dx + BOX_W / 2, dy + BOX_H
            else:                             # loops back up, route to the side
                x1, y1 = sx + BOX_W, sy + BOX_H / 2
                x2, y2 = dx + BOX_W, dy + BOX_H / 2
            draw_arrow(cnv, x1, y1, x2, y2, kind,
                       "" if kind == "edge" else cond, faded=faded)

    for nid in pos:
        x, y = box_xy(nid)
        draw_box(cnv, x, y, nodes[nid], refs[nid], nid in globals_)

    if globals_:
        cnv.setFillColor(GLOBAL_LINE)
        cnv.setFont("Helvetica-Bold", 9)
        cnv.drawString(minx, -4 * mm,
                       "GLOBAL NODES  -  reachable from ANY node, only after a caller turn, "
                       "then they hand the caller back")
    cnv.restoreState()

    cnv.setFillColor(HexColor("#666666"))
    cnv.setFont("Helvetica-Oblique", 7.2)
    note = "drawn to %.0f%% to fit the page" % (scale * 100)
    if unreached:
        note += "   |   %d node(s) in the bottom band are reached by no edge from the start node" % len(unreached)
    cnv.drawString(14 * mm, 9 * mm, note)
    cnv.showPage()


def draw_table_pages(cnv, flow, label, page_w, page_h, refs):
    nodes = {n["id"]: n for n in flow["nodes"]}
    rows = sorted(flow["nodes"], key=lambda n: refs[n["id"]])
    # 44 fits a landscape A2 page with room to spare, so each agent's table is
    # one page rather than two half-empty ones.
    per = 44
    for start in range(0, len(rows), per):
        chunk = rows[start:start + per]
        header(cnv, page_w, page_h, "%s  -  node reference" % label,
               "nodes %d to %d of %d" % (start + 1, start + len(chunk), len(rows)))
        y = page_h - 26 * mm
        cnv.setFillColor(black)
        cnv.setFont("Helvetica-Bold", 7.6)
        cols = [14, 24, 92, 128, 168, 205]
        for cx, t in zip(cols, ("#", "Node", "Type", "Instruction", "Exits", "Where it can go")):
            cnv.drawString(cx * mm, y, t)
        y -= 2 * mm
        cnv.setStrokeColor(HexColor("#999999"))
        cnv.setLineWidth(0.6)
        cnv.line(14 * mm, y, page_w - 14 * mm, y)
        y -= 5 * mm

        for n in chunk:
            st = style_for(n)
            cnv.setFillColor(st["line"])
            cnv.setFont("Helvetica-Bold", 7.2)
            cnv.drawString(cols[0] * mm, y, str(refs[n["id"]]))
            cnv.setFillColor(black)
            cnv.setFont("Helvetica-Bold", 7.2)
            nm = n.get("name") or n["id"]
            if n.get("global_node_setting"):
                nm += "  [GLOBAL]"
            cnv.drawString(cols[1] * mm, y, fit(nm, 66 * mm, 7.2, cnv, "Helvetica-Bold"))
            cnv.setFont("Helvetica", 7)
            cnv.drawString(cols[2] * mm, y, n.get("type", "?"))
            cnv.drawString(cols[3] * mm, y, (n.get("instruction") or {}).get("type") or "-")
            outs = out_edges(n)
            cnv.drawString(cols[4] * mm, y, str(len(outs)) if outs else "0, ends here")
            dests = []
            for kind, dst, _ in outs:
                d = nodes.get(dst)
                tag = "#%s" % refs[dst] if dst in refs else "?"
                if kind != "edge":
                    tag += " (%s)" % kind
                dests.append(tag)
            cnv.drawString(cols[5] * mm, y,
                           fit(", ".join(dests) or "-", page_w - (cols[5] + 16) * mm, 7, cnv))
            y -= 4.6 * mm
            cnv.setStrokeColor(HexColor("#E4E4E4"))
            cnv.line(14 * mm, y + 1.4 * mm, page_w - 14 * mm, y + 1.4 * mm)
        cnv.showPage()


def cover(cnv, page_w, page_h, agents, title="Voice agent conversation flows"):
    cnv.setFillColor(HexColor("#12314F"))
    cnv.rect(0, 0, page_w, page_h, stroke=0, fill=1)
    cnv.setFillColor(white)
    cnv.setFont("Helvetica-Bold", 30)
    cnv.drawString(24 * mm, page_h - 46 * mm, title)
    cnv.setFont("Helvetica", 19)
    cnv.drawString(24 * mm, page_h - 58 * mm, "Voice agent conversation flows")
    cnv.setFont("Helvetica", 11)
    y = page_h - 82 * mm
    for label, flow, live in agents:
        cnv.setFont("Helvetica-Bold", 12)
        cnv.drawString(24 * mm, y, label)
        cnv.setFont("Helvetica", 10)
        cnv.drawString(72 * mm, y, "flow version %s  |  %d nodes  |  %s"
                       % (flow.get("version"), len(flow["nodes"]), live))
        y -= 8 * mm
    y -= 6 * mm
    cnv.setFont("Helvetica", 9.4)
    for line in textwrap.wrap(
            "Each agent has two pages. The first is the flow itself, drawn top to bottom from the "
            "greeting to the end of the call, with every node numbered. The second is a reference "
            "table listing every node by that number, with its type and where it can go next.", 96):
        cnv.drawString(24 * mm, y, line)
        y -= 5.4 * mm
    y -= 4 * mm
    for line in textwrap.wrap(
            "The four purple dashed boxes at the top of each flow are GLOBAL nodes. No arrow reaches "
            "them because none can: a global node listens on every turn and can take over from any "
            "node in the flow, but only after the caller has spoken. When it is finished it hands the "
            "caller back to the node they came from. That is why the safety gate and the guardrail "
            "answers do not appear in the main chain.", 96):
        cnv.drawString(24 * mm, y, line)
        y -= 5.4 * mm
    cnv.setFont("Helvetica-Oblique", 8.4)
    cnv.drawString(24 * mm, 20 * mm,
                   "Drawn directly from the published Retell exports by tools/flowdiagram.py. "
                   "Nothing here is hand-drawn, so it cannot drift from the agent.")
    cnv.showPage()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--client", help="client folder name")
    ap.add_argument("--agent", help="agent slug under <client>/agents/")
    ap.add_argument("--file")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    if a.file:
        targets = [(os.path.basename(a.file), a.file, "")]
    elif a.client and a.agent:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kit"))
        from retellkit import agent_config
        cfg = agent_config(a.client, a.agent)
        exports = sorted(Path(cfg["exports"]).glob("v*.json"))
        if not exports:
            raise SystemExit(f"no exports found under {cfg['exports']}")
        targets = [(f"{a.client}/{a.agent}", str(exports[-1]), "")]
    else:
        raise SystemExit("pass --file, or --client and --agent")

    # Seeding the walk from the globals as well as the start node made both
    # flows nine layers deep instead of twelve and fourteen, so a landscape
    # page now fits them at close to full size. Portrait forced 65%.
    flow_w, flow_h = landscape(A2)
    tab_w, tab_h = landscape(A2)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    cnv = pdfcanvas.Canvas(a.out, pagesize=(flow_w, flow_h))
    title = f"{a.client} - voice agent conversation flows" if a.client else \
        "Voice agent conversation flows"
    cnv.setTitle(title)

    loaded = [(label, load(path), live) for label, path, live in targets]
    if len(loaded) > 1:
        cnv.setPageSize((flow_w, flow_h))
        cover(cnv, flow_w, flow_h, loaded, title=title)

    for label, flow, _live in loaded:
        nodes, layers, globals_, _ = layer_nodes(flow)
        order = []
        for g in globals_:
            order.append(g)
        for d in sorted(layers):
            order.extend(layers[d])
        refs = {nid: i + 1 for i, nid in enumerate(order)}
        cnv.setPageSize((flow_w, flow_h))
        draw_flow_page(cnv, flow, label, flow_w, flow_h, refs)
        cnv.setPageSize((tab_w, tab_h))
        draw_table_pages(cnv, flow, label, tab_w, tab_h, refs)
        print("drew %s: %d nodes, %d global, %d layers"
              % (label, len(flow["nodes"]), len(globals_), len(layers)))

    cnv.save()
    print("wrote", a.out, os.path.getsize(a.out), "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
