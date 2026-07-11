#!/usr/bin/env python3
"""Minimal HTTP API for remote/local atlas search (stdlib only).

  .venv/bin/python scripts/http_api.py --host 127.0.0.1 --port 8787

Endpoints:
  GET /health
  GET /v1/search?q=...&domain=all&limit=3
  GET /v1/nodes/<id>
  GET /v1/alternatives/<id>
  GET /v1/meta
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atlas_lib import get_alternatives, get_node, list_domains, search_projects  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quieter
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        if path == "/health":
            self._send(200, {"ok": True, "service": "kaiyuan-dashuli"})
            return
        if path == "/v1/meta":
            self._send(
                200,
                {
                    "name": "kaiyuan-dashuli",
                    "title": "开源大梳理",
                    "domains": list_domains(),
                    "raw_index_url": "https://raw.githubusercontent.com/Zunzhe966/kaiyuan-dashuli/main/dist/atlas-index.json",
                    "endpoints": [
                        "/health",
                        "/v1/meta",
                        "/v1/search?q=&domain=all&limit=3",
                        "/v1/nodes/<id>",
                        "/v1/alternatives/<id>",
                    ],
                },
            )
            return
        if path == "/v1/search":
            q = (qs.get("q") or qs.get("query") or [""])[0]
            if not q.strip():
                self._send(400, {"error": "missing q"})
                return
            domain = (qs.get("domain") or ["all"])[0]
            limit = int((qs.get("limit") or ["3"])[0])
            d = None if domain in ("all", "", "*") else domain
            self._send(200, {"results": search_projects(query=q, domain=d, limit=limit)})
            return
        if path.startswith("/v1/nodes/"):
            nid = unquote(path[len("/v1/nodes/") :])
            node = get_node(nid)
            if not node:
                self._send(404, {"error": f"unknown id: {nid}"})
                return
            self._send(200, {"node": node})
            return
        if path.startswith("/v1/alternatives/"):
            nid = unquote(path[len("/v1/alternatives/") :])
            self._send(200, {"results": get_alternatives(nid)})
            return
        self._send(404, {"error": "not found", "path": path})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"kaiyuan-dashuli http api on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
