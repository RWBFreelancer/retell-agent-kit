#!/usr/bin/env python3
"""Build an export by applying N transforms in order. Local only, never PATCHes.

Used to A/B candidate fixes before committing to one. flowapply.py runs exactly
one transform against the live flow; this runs a list against a local export so
several variants can be compared in the same session without touching Retell.

    python tools/_combo.py <base.json> <out.json> <transform> [<transform> ...]
"""
import sys, json, copy, importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "transforms"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, REPO / "transforms" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def main():
    base, out, names = sys.argv[1], sys.argv[2], sys.argv[3:]
    flow = json.loads(Path(base).read_text(encoding="utf-8"))
    for n in names:
        flow = load(n).apply(copy.deepcopy(flow))
        print(f"  applied {n}")
    Path(out).write_text(
        json.dumps(flow, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
