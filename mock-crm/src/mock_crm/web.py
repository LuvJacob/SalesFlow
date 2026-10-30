"""Mock CRM web dashboard: a small read-only HTTP API plus a static single-page UI.

Run (from mock-crm/):   uv run mock-crm-web            # then open http://127.0.0.1:8765
                        uv run mock-crm-web --open     # also opens your browser

ALL DATA IS FICTIONAL. It uses the same data layer as the MCP server, so the
dashboard and Bob always show the same records.

Security design:
- Binds to 127.0.0.1 only. There is no option to change the host.
- Read-only: only GET and HEAD are accepted. Nothing is ever written.
- The Host header must be this server's own loopback address (blocks DNS rebinding).
- Only a fixed allowlist of static files is served (no path traversal possible).
- Query parameters are validated for type and length. Errors are generic.
- Strict Content-Security-Policy: scripts and styles only from this origin, no inline code.
- Standard library only: no third-party web framework, so no extra dependencies.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from mock_crm import server as crm

log = logging.getLogger("mock_crm.web")

HOST = "127.0.0.1"  # fixed on purpose: never bind to all interfaces
DEFAULT_PORT = 8765
STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_PARAM_LEN = crm.MAX_INPUT_LEN
MAX_QUERY_STRING = 2000

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
        "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


# --------------------------------------------------------------------------- data (pure functions, easy to test)


def get_summary() -> dict:
    return crm.crm_pipeline_summary()["data"]


def get_accounts() -> list[dict]:
    accounts, opps = crm._load()
    counts: dict[str, int] = {}
    for o in opps:
        counts[o.get("account_id")] = counts.get(o.get("account_id"), 0) + 1
    rows = [
        {
            "account_id": a.get("account_id"),
            "name": a.get("name"),
            "industry": a.get("industry"),
            "owner": a.get("owner"),
            "region": a.get("region"),
            "opportunity_count": counts.get(a.get("account_id"), 0),
        }
        for a in accounts
    ]
    rows.sort(key=lambda r: str(r["name"] or "").casefold())
    return rows


def get_opportunities(q: str = "", stage: str = "", account: str = "") -> list[dict]:
    accounts, opps = crm._load()
    by_id = {a.get("account_id"): a for a in accounts}
    rows = []
    for o in sorted(opps, key=crm._sort_key):
        a = by_id.get(o.get("account_id"), {})
        row = {
            **crm._opp_view(o),
            "account_id": o.get("account_id"),
            "account_name": a.get("name"),
            "industry": a.get("industry"),
            "region": a.get("region"),
        }
        if stage and str(row["stage"] or "").casefold() != stage.casefold():
            continue
        if account and row["account_id"] != account:
            continue
        if q:
            hay = " ".join(str(row.get(k) or "") for k in ("name", "account_name", "stage", "owner", "industry", "region"))
            if q.casefold() not in hay.casefold():
                continue
        rows.append(row)
    return rows


def _clean_param(params: dict[str, list[str]], key: str) -> str | None:
    """Return a cleaned single value, '' if absent, or None if invalid."""
    values = params.get(key)
    if not values:
        return ""
    value = " ".join(values[0].split())
    if len(value) > MAX_PARAM_LEN or not value.isprintable():
        return None
    return value


# --------------------------------------------------------------------------- HTTP


class Handler(BaseHTTPRequestHandler):
    server_version = "MockCRM"
    sys_version = ""  # do not disclose the Python version

    # -- plumbing ------------------------------------------------------------

    def log_message(self, fmt: str, *args) -> None:  # noqa: A002 - signature fixed by the base class
        log.info("%s %s", self.command, urlsplit(self.path).path)  # path only, never the query string

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json(status, {"status": "error", "error": {"code": status.value, "message": message}})

    def _host_ok(self) -> bool:
        port = self.server.server_address[1]
        return (self.headers.get("Host") or "") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    # -- verbs ---------------------------------------------------------------

    def do_GET(self) -> None:
        try:
            self._route()
        except Exception:  # noqa: BLE001 - last-resort guard: log details, return a generic message
            log.exception("request failed")
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "Something went wrong.")

    do_HEAD = do_GET

    def _reject_method(self) -> None:
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Allow", "GET, HEAD")
        self.send_header("Content-Length", "0")
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _reject_method

    # -- routing -------------------------------------------------------------

    def _route(self) -> None:
        if not self._host_ok():
            self._error(HTTPStatus.FORBIDDEN, "Forbidden.")
            return
        parts = urlsplit(self.path)
        if len(parts.query) > MAX_QUERY_STRING:
            self._error(HTTPStatus.BAD_REQUEST, "Request too large.")
            return
        path = parts.path

        if path in STATIC_FILES:
            name, ctype = STATIC_FILES[path]
            try:
                body = (STATIC_DIR / name).read_bytes()
            except OSError:
                log.error("static file missing: %s", name)
                self._error(HTTPStatus.NOT_FOUND, "Not found.")
                return
            self._send(HTTPStatus.OK, body, ctype)
            return

        if path == "/api/health":
            self._json(HTTPStatus.OK, {"status": "ok", "data": {"server": "mock-crm-web", "synthetic": True}})
        elif path == "/api/summary":
            self._json(HTTPStatus.OK, {"status": "ok", "data": get_summary()})
        elif path == "/api/accounts":
            rows = get_accounts()
            self._json(HTTPStatus.OK, {"status": "ok", "data": {"count": len(rows), "accounts": rows, "synthetic": True}})
        elif path == "/api/opportunities":
            params = parse_qs(parts.query, keep_blank_values=False, max_num_fields=10)
            cleaned = {k: _clean_param(params, k) for k in ("q", "stage", "account")}
            if any(v is None for v in cleaned.values()):
                self._error(HTTPStatus.BAD_REQUEST, "Invalid search input.")
                return
            rows = get_opportunities(cleaned["q"], cleaned["stage"], cleaned["account"])
            self._json(HTTPStatus.OK, {"status": "ok", "data": {"count": len(rows), "opportunities": rows, "synthetic": True}})
        else:
            self._error(HTTPStatus.NOT_FOUND, "Not found.")


def make_server(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((HOST, port), Handler)
    httpd.daemon_threads = True
    return httpd


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Mock CRM dashboard (read-only, synthetic data, localhost only).")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port to listen on (default {DEFAULT_PORT})")
    ap.add_argument("--open", action="store_true", help="open the dashboard in your browser")
    args = ap.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        ap.error("--port must be between 1024 and 65535")

    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        httpd = make_server(args.port)
    except OSError:
        print(f"Port {args.port} is busy. Try: uv run mock-crm-web --port {args.port + 1}", file=sys.stderr)
        sys.exit(1)

    url = f"http://{HOST}:{args.port}"
    print(f"Mock CRM dashboard (fictional data, read-only): {url}\nPress Ctrl+C to stop.")
    if args.open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
