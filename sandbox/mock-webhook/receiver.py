#!/usr/bin/env python3
"""A local webhook receiver, for testing an integration with no real n8n,
Make, or GHL workflow behind it.

Every POST is saved to results/, one file per request, and answered with
200 and an empty JSON body. Use it as the --url override in
tools/webhookreplay.py, or as an agent's temporary webhook_url while
proving a payload shape offline.

Usage:
    python sandbox/mock-webhook/receiver.py --port 8787 --out results/
"""
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    out_dir = Path("results")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = self.out_dir / f"mock-webhook-{stamp}-{int(time.time() * 1000) % 1000}.json"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        try:
            parsed = json.loads(body)
            path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False),
                           encoding="utf-8")
        except ValueError:
            path.write_bytes(body)
        print(f"received {len(body)} bytes -> {path}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, fmt, *args):
        pass  # keep stdout to the one line printed in do_POST


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--out", default="results", help="where to save payloads")
    a = ap.parse_args(argv)

    Handler.out_dir = Path(a.out)
    server = HTTPServer(("127.0.0.1", a.port), Handler)
    print(f"mock webhook receiver on http://127.0.0.1:{a.port}  "
          f"(saving to {Handler.out_dir})")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
