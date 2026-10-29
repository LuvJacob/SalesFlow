"""Offline checks for the mock CRM web dashboard (real HTTP on 127.0.0.1, random port).

Run (from mock-crm/):  uv run python tests/run_web_test.py
Exit code 0 means every check passed.
"""

from __future__ import annotations

import http.client
import json
import logging
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mock_crm import web  # noqa: E402

logging.getLogger("mock_crm.web").setLevel(logging.CRITICAL)

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def main() -> None:
    httpd = web.make_server(0)  # port 0 = let the OS pick a free port
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def req(method: str, path: str, host: str | None = None, body: bytes | None = None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        c.putrequest(method, path, skip_host=True)
        c.putheader("Host", host or f"127.0.0.1:{port}")
        if body is not None:
            c.putheader("Content-Length", str(len(body)))
        c.endheaders(body)
        r = c.getresponse()
        data = r.read()
        headers = {k.lower(): v for k, v in r.getheaders()}
        c.close()
        return r.status, headers, data

    def get_json(path: str, **kw):
        status, headers, data = req("GET", path, **kw)
        return status, headers, json.loads(data) if data else {}

    try:
        check("binds to loopback only", httpd.server_address[0] == "127.0.0.1", str(httpd.server_address))

        s, h, d = get_json("/api/health")
        check("health ok", s == 200 and d["status"] == "ok")

        s, h, d = get_json("/api/summary")
        check("summary totals", s == 200 and d["data"]["total_opportunities"] >= 6 and d["data"]["total_accounts"] >= 4)
        check("summary has next to close", bool(d["data"]["next_to_close"]))

        s, h, d = get_json("/api/accounts")
        names = [a["name"] for a in d["data"]["accounts"]]
        check("accounts listed and sorted", s == 200 and names == sorted(names, key=str.casefold) and "Acme Healthcare" in names)

        s, h, d = get_json("/api/opportunities")
        allrows = d["data"]["opportunities"]
        check("all opportunities returned", s == 200 and d["data"]["count"] == len(allrows) >= 6)
        dates = [o["close_date"] for o in allrows if o["close_date"]]
        check("sorted by close date", dates == sorted(dates))
        check("undated sort last", all(o["close_date"] is None for o in allrows[len(dates):]))

        s, h, d = get_json("/api/opportunities?account=acct_acme_healthcare")
        check("account filter", s == 200 and d["data"]["count"] == 2 and all(o["account_id"] == "acct_acme_healthcare" for o in d["data"]["opportunities"]))

        s, h, d = get_json("/api/opportunities?stage=negotiation")
        check("stage filter is case-insensitive", s == 200 and d["data"]["count"] >= 1)

        s, h, d = get_json("/api/opportunities?q=encryption")
        check("text search", s == 200 and d["data"]["count"] == 1)

        s, h, d = get_json("/api/opportunities?q=nothing-matches-this")
        check("search with no match returns empty list", s == 200 and d["data"]["count"] == 0)

        s, h, d = get_json("/api/opportunities?q=" + "x" * 500)
        check("over-long search rejected", s == 400 and d["status"] == "error")

        s, h, d = get_json("/api/opportunities?q=%00bad")
        check("control characters rejected", s == 400)

        # Static files
        s, h, data = req("GET", "/")
        check("index served as html", s == 200 and h["content-type"].startswith("text/html") and b"Mock CRM" in data)
        s, h, data = req("GET", "/app.js")
        check("app.js served", s == 200 and "javascript" in h["content-type"])
        check("app.js never uses innerHTML", b"innerHTML" not in data)
        s, h, data = req("GET", "/style.css")
        check("style.css served", s == 200 and h["content-type"].startswith("text/css"))
        s, h, data = req("GET", "/")
        check("no inline scripts in index", b"<script>" not in data and b"onclick" not in data)
        check("no external resources in index", b"http://" not in data and b"https://" not in data)

        # Security headers
        s, h, _ = req("GET", "/")
        csp = h.get("content-security-policy", "")
        check("CSP present and strict", "default-src 'none'" in csp and "script-src 'self'" in csp and "unsafe-inline" not in csp)
        check("nosniff + no-store + frame deny", h.get("x-content-type-options") == "nosniff" and h.get("cache-control") == "no-store" and h.get("x-frame-options") == "DENY")
        check("server does not disclose Python version", "python" not in h.get("server", "").lower())

        # Read-only
        for m in ("POST", "PUT", "DELETE", "PATCH"):
            s, h, _ = req(m, "/api/opportunities", body=b"{}")
            check(f"{m} rejected", s == 405 and "GET" in h.get("allow", ""))

        # Path handling
        for p in ("/../server.py", "/..%2fserver.py", "/static/../web.py", "/server.py", "/api/nope", "/%2e%2e/web.py"):
            s, _, data = req("GET", p)
            check(f"no traversal or leak: {p}", s == 404 and b"FastMCP" not in data and b"def " not in data)

        # DNS rebinding / Host header
        s, _, _ = req("GET", "/api/summary", host="evil.example.com")
        check("foreign Host header rejected", s == 403)
        s, _, _ = req("GET", "/api/summary", host=f"localhost:{port}")
        check("localhost Host accepted", s == 200)

        # Errors are generic
        s, _, data = req("GET", "/api/opportunities?q=" + "y" * 500)
        text = data.decode()
        check("error body is generic", "Traceback" not in text and "/Users/" not in text and "mock_crm" not in text)

        # HEAD has no body
        s, h, data = req("HEAD", "/api/health")
        check("HEAD returns no body", s == 200 and data == b"")

        # Data is untrusted: markup in a record is returned as plain JSON text, never executed server-side
        rows = web.get_opportunities(q="<script>")
        check("markup search is just a string match", rows == [])
    finally:
        httpd.shutdown()
        httpd.server_close()

    if FAILURES:
        print(f"\n{len(FAILURES)} check(s) FAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("\nAll checks passed")


if __name__ == "__main__":
    main()
