"""SalesFlow standalone HTML report generator.

Renders professional, self-contained HTML reports from structured data already
retrieved by the SalesFlow MCP read tools. Writes to outputs/reports/ only.

Visual language is adapted from the supplied dashboard reference (rounded cards,
subtle gray borders, compact rows, light/dark variables, restrained accents).
No finance content, navigation labels, or assets are reused.

Design rules
------------
* Self-contained: one file, embedded CSS, inline SVG charts. No JavaScript, no
  external scripts, stylesheets, fonts, images, or CDN. A restrictive
  Content-Security-Policy meta tag is embedded as defense in depth.
* Safe by construction: every dynamic value passes through ``e()`` (HTML
  escaping). Components return ``Html`` objects that are never re-escaped, and
  plain ``str`` values are always escaped. CSS classes are chosen only from
  fixed allowlists, never from data.
* Product/source links are rendered as anchors only when they are https URLs on
  ibm.com (see ``safe_ibm_url``); anything else is shown as inert text.
* Formats supplied content only: never invents facts, capabilities, prices or
  URLs. Synthetic-data labels, evidence labels and source references are kept.
* Never overwrites an existing file; filenames are ASCII-only and traversal-proof
  (shared writer in ``md_report``).
* Logs to stderr only (stdout carries the MCP protocol stream).

Report types mirror the Document Studio / Markdown types:
  discovery_brief, account_summary, action_plan, deal_risk_assessment,
  solution_comparison, followup_plan, pipeline_digest
"""

from __future__ import annotations

import html as _html
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from urllib.parse import urlsplit

from .md_report import REPORT_TYPES, MdReportError, _money, _write_report

log = logging.getLogger("salesflow.html_report")

LIST_CAP = 100  # hard cap on rows rendered from any one list
SPIN_ORDER = ("Situation", "Problem", "Implication", "Need-Payoff")

HEURISTIC_NOTE = (
    "Risk scores are heuristic-based prioritization tools, not statistically validated predictions. "
    "Missing CRM fields are reported as Unknown and are not scored as negative evidence."
)
STANDARD_DISCLAIMER = (
    "This report is a draft for seller review. It formats data returned by SalesFlow tools and does not "
    "include pricing, guaranteed outcomes, or unsourced competitor claims. Verify names, facts and sizing "
    "with the customer and a specialist before any external use. Nothing was sent and no CRM record was changed."
)
LINKS_NOTE = (
    "Product links point to IBM pages recorded in the catalog. This report did not retrieve live IBM "
    "documentation and makes no claim beyond the catalog text supplied."
)

# ---------------------------------------------------------------------------
# Escaping and safe value helpers
# ---------------------------------------------------------------------------

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class Html(str):
    """Marker type: already-safe HTML produced by this module. Never re-escaped."""

    __slots__ = ()


def e(v: Any) -> Html:
    """Escape any value for HTML text/attribute context. Html passes through."""
    if isinstance(v, Html):
        return v
    s = "" if v is None else str(v)
    return Html(_html.escape(_CTRL.sub("", s), quote=True))


def jn(parts: Iterable[Any], sep: str = "") -> Html:
    """Join parts; plain strings are escaped, Html is kept."""
    return Html(sep.join(e(p) for p in parts))


def _d(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _l(v: Any) -> list:
    return v if isinstance(v, list) else []


def _isnum(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _s(v: Any, fallback: str = "Unknown") -> str:
    if v is None:
        return fallback
    s = str(v).strip()
    return s if s else fallback


def _txt(d: dict, *keys: str) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if _isnum(v):
            return str(v)
    return ""


def _strs(v: Any) -> list[str]:
    """Flatten a list of str/dict items into display strings."""
    out: list[str] = []
    for x in _l(v):
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
        elif isinstance(x, dict):
            t = _txt(x, "text", "detail", "gap", "label", "question", "action", "name")
            if t:
                out.append(t)
    return out


def _item_text(x: Any) -> str:
    if isinstance(x, str):
        return x.strip()
    if isinstance(x, dict):
        return _txt(x, "detail", "text", "description", "name") or ""
    return ""


def _readable(key: Any) -> str:
    return _s(key, "").replace("_", " ").strip()


def _cap(items: list, n: int = LIST_CAP) -> tuple[list, int]:
    return items[:n], max(0, len(items) - n)


def _is_seller_question(text: str) -> bool:
    t = text.strip()
    return t.startswith("Seller:") or t.endswith("?")


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

_MAX_URL = 2048


def safe_ibm_url(url: Any) -> Optional[str]:
    """Return the URL only if it is a plain https URL on ibm.com or a subdomain.

    Rejects non-strings, whitespace/control/non-ASCII characters, backslashes,
    credentials, non-443 ports, other schemes (javascript:, data:, http:), and
    look-alike hosts such as ibm.com.evil.example or evilibm.com.
    """
    if not isinstance(url, str):
        return None
    u = url.strip()
    if not u or len(u) > _MAX_URL or "\\" in u:
        return None
    if any(ord(ch) <= 32 or ord(ch) > 126 for ch in u):
        return None
    try:
        parts = urlsplit(u)
        host = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if parts.scheme != "https" or not host:
        return None
    if parts.username is not None or parts.password is not None:
        return None
    if port not in (None, 443):
        return None
    host = host.lower()
    if host != "ibm.com" and not host.endswith(".ibm.com"):
        return None
    return u


def _link(url: Any, label: str) -> Html:
    safe = safe_ibm_url(url)
    if not safe:
        return Html("")
    return Html(f'<a href="{e(safe)}" target="_blank" rel="noopener noreferrer">{e(label)}</a>')


# ---------------------------------------------------------------------------
# Design system: CSS
# ---------------------------------------------------------------------------

_LIGHT_VARS = (
    "color-scheme:light;--bg:#ffffff;--card:#ffffff;--line:#e5e7eb;--inner:#ffffff;--inner-line:#f4f4f5;"
    "--inner-line2:#e4e4e7;--hover:#f4f4f5;--fg:#18181b;--muted:#52525b;--faint:#71717a;--btn:#18181b;"
    "--btn-fg:#fafafa;--ok-bg:#d1fae5;--ok-fg:#047857;--warn-bg:#fef3c7;--warn-fg:#b45309;"
    "--info-bg:#dbeafe;--info-fg:#1d4ed8;--bad-bg:#fee2e2;--bad-fg:#b91c1c;--acc-bg:#f3e8ff;--acc-fg:#7e22ce;"
    "--neu-bg:#f4f4f5;--neu-fg:#3f3f46;--c-high:#dc2626;--c-med:#d97706;--c-low:#059669;--link:#1d4ed8;"
)
_DARK_VARS = (
    "color-scheme:dark;--bg:#0f0f12;--card:#0f0f12;--line:#1f1f23;--inner:rgba(24,24,27,.7);--inner-line:#27272a;"
    "--inner-line2:#3f3f46;--hover:rgba(39,39,42,.5);--fg:#f4f4f5;--muted:#a1a1aa;--faint:#8b8b94;--btn:#fafafa;"
    "--btn-fg:#18181b;--ok-bg:rgba(6,78,59,.35);--ok-fg:#34d399;--warn-bg:rgba(120,53,15,.35);--warn-fg:#fbbf24;"
    "--info-bg:rgba(30,58,138,.35);--info-fg:#60a5fa;--bad-bg:rgba(127,29,29,.35);--bad-fg:#f87171;"
    "--acc-bg:rgba(88,28,135,.35);--acc-fg:#c084fc;--neu-bg:#27272a;--neu-fg:#d4d4d8;--c-high:#f87171;"
    "--c-med:#fbbf24;--c-low:#34d399;--link:#60a5fa;"
)

_CSS = """
:root{%LIGHT%}
@media (prefers-color-scheme:dark){:root:not(:has(#th-light:checked)){%DARK%}}
:root:has(#th-dark:checked){%DARK%}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:13px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,"Helvetica Neue",Arial,sans-serif}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}
h1,h2,h3,h4,p,ul,ol,dl,dd{margin:0}
.th{position:absolute;opacity:0;pointer-events:none}
.topnav{position:sticky;top:0;z-index:5;height:56px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 24px;background:var(--bg);border-bottom:1px solid var(--line)}
.crumbs{display:flex;align-items:center;gap:6px;font-weight:500;color:var(--muted);min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.crumbs b{color:var(--fg);font-weight:500}.crumbs i{font-style:normal;color:var(--faint)}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:999px;padding:2px;background:var(--inner);flex:none}
.seg label{font-size:11px;padding:3px 10px;border-radius:999px;cursor:pointer;color:var(--muted)}
:root:has(#th-auto:checked) label[for=th-auto],:root:has(#th-light:checked) label[for=th-light],:root:has(#th-dark:checked) label[for=th-dark]{background:var(--btn);color:var(--btn-fg)}
:root:has(#th-auto:focus-visible) label[for=th-auto],:root:has(#th-light:focus-visible) label[for=th-light],:root:has(#th-dark:focus-visible) label[for=th-dark]{outline:2px solid var(--link);outline-offset:1px}
main{max-width:1080px;margin:0 auto;padding:24px;display:flex;flex-direction:column;gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 24px;min-width:0}
.card-h{display:flex;align-items:center;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.card h2{font-size:16px;font-weight:700;letter-spacing:-.01em;display:flex;align-items:center;gap:8px}
.card h2::before{content:"";width:8px;height:8px;border-radius:2px;background:var(--fg);flex:none}
.card h3{font-size:12px;font-weight:600;margin:14px 0 6px}
.card h4{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin-bottom:4px}
.hero{display:flex;gap:16px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}
.hero-l{display:flex;gap:14px;align-items:center;min-width:0}
.mono-box{width:44px;height:44px;border-radius:10px;background:var(--neu-bg);border:1px solid var(--inner-line2);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px;flex:none}
.eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:600}
.hero h1{font-size:22px;line-height:1.25;font-weight:700;letter-spacing:-.02em;overflow-wrap:anywhere}
.hero p{color:var(--muted);font-size:12px;margin-top:2px}
.pills{display:flex;gap:6px;flex-wrap:wrap}
.muted{color:var(--muted)}.faint{color:var(--faint)}.xs{font-size:12px}.xxs{font-size:11px}.strong{font-weight:600}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px}
.count{font-size:11px;color:var(--muted);background:var(--neu-bg);border-radius:999px;padding:1px 8px}
.pill{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:500;white-space:nowrap}
.pill.ok{background:var(--ok-bg);color:var(--ok-fg)}.pill.warn{background:var(--warn-bg);color:var(--warn-fg)}
.pill.info{background:var(--info-bg);color:var(--info-fg)}.pill.bad{background:var(--bad-bg);color:var(--bad-fg)}
.pill.acc{background:var(--acc-bg);color:var(--acc-fg)}.pill.neutral{background:var(--neu-bg);color:var(--neu-fg)}
.unk{display:inline-flex;gap:4px;align-items:center;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:500;background:var(--warn-bg);color:var(--warn-fg)}
.unk i{font-style:normal;font-weight:400;opacity:.85}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.metric{background:var(--inner);border:1px solid var(--inner-line);border-radius:10px;padding:12px 14px}
.m-l{font-size:11px;color:var(--muted)}.m-v{font-size:22px;font-weight:600;letter-spacing:-.02em;margin-top:2px;overflow-wrap:anywhere}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.stack{display:flex;flex-direction:column;gap:16px;min-width:0}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px 20px}
.kv dt{font-size:11px;color:var(--muted)}.kv dd{font-size:13px;font-weight:500;overflow-wrap:anywhere}
.callout{border:1px solid var(--inner-line2);border-left:3px solid var(--info-fg);background:var(--inner);border-radius:8px;padding:10px 12px;font-size:12px;color:var(--muted)}
.callout.warn{border-left-color:var(--warn-fg)}.callout.bad{border-left-color:var(--bad-fg)}
.callout strong{color:var(--fg)}
.list{padding-left:18px;display:flex;flex-direction:column;gap:4px}
.list.plain{list-style:none;padding-left:0}
.rows{display:flex;flex-direction:column;gap:4px}
.row{display:flex;align-items:center;gap:10px;padding:8px;border-radius:8px}
.row:hover{background:var(--hover)}
.ico.wide{width:auto;min-width:64px;padding:0 8px;white-space:nowrap}
.ico{width:28px;height:28px;border-radius:8px;background:var(--neu-bg);border:1px solid var(--inner-line2);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;flex:none}
.r-b{flex:1;min-width:0}.r-t{font-size:12px;font-weight:500;overflow-wrap:anywhere}.r-s{font-size:11px;color:var(--muted);overflow-wrap:anywhere}
.r-v{font-size:12px;font-weight:500;text-align:right;flex:none}
.spin{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.spin-q{background:var(--inner);border:1px solid var(--inner-line);border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:8px}
.spin-q p{font-size:13px}
.tblwrap{overflow-x:auto;border:1px solid var(--inner-line);border-radius:10px}
.tbl{width:100%;border-collapse:collapse;font-size:12px}
.tbl th{text-align:left;font-size:11px;font-weight:600;color:var(--muted);padding:8px 12px;background:var(--hover);border-bottom:1px solid var(--inner-line)}
.tbl td{padding:8px 12px;border-bottom:1px solid var(--inner-line);vertical-align:top;overflow-wrap:anywhere}
.tbl tr:last-child td{border-bottom:0}
.tbl td.c,.tbl th.c{text-align:center}
.disc{border:1px solid var(--inner-line);border-radius:10px;background:var(--inner);margin-top:8px}
.disc:first-child{margin-top:0}
.disc>summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px;padding:10px 12px;font-size:12px;font-weight:600}
.disc>summary::-webkit-details-marker{display:none}
.disc>summary::after{content:"+";margin-left:auto;color:var(--muted);font-weight:400;font-size:14px}
.disc[open]>summary::after{content:"\\2013"}
.disc>summary:hover{background:var(--hover);border-radius:10px}
.disc-b{padding:4px 12px 12px;display:flex;flex-direction:column;gap:10px}
.deal{background:var(--inner);border:1px solid var(--inner-line);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:10px}
.deal:hover{border-color:var(--inner-line2)}
.deal-h{display:flex;gap:10px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}
.deal-t{display:flex;gap:10px;align-items:flex-start;min-width:0}
.deal-t .r-t{font-size:13px;font-weight:600}
.deal-r{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.score{font-size:12px;font-weight:600}
.bar{height:6px;background:var(--neu-bg);border-radius:999px;overflow:hidden}
.bar>span{display:block;height:100%;border-radius:999px;background:var(--fg)}
.bar>span.s-high{background:var(--c-high)}.bar>span.s-med{background:var(--c-med)}.bar>span.s-low{background:var(--c-low)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.chart{display:flex;gap:20px;align-items:center;flex-wrap:wrap}
.donut{width:150px;height:150px;flex:none}
.ring{transform-origin:center}
.ring.r-track{stroke:var(--inner-line2)}.ring.r-high{stroke:var(--c-high)}.ring.r-med{stroke:var(--c-med)}.ring.r-low{stroke:var(--c-low)}
.ring-n{font-size:9px;font-weight:700;fill:var(--fg);text-anchor:middle}
.ring-l{font-size:3.4px;fill:var(--muted);text-anchor:middle}
.legend{display:flex;flex-direction:column;gap:6px;min-width:200px;flex:1}
.lg{display:flex;align-items:center;gap:8px;font-size:12px}
.dot{width:9px;height:9px;border-radius:50%;flex:none}
.dot.d-high{background:var(--c-high)}.dot.d-med{background:var(--c-med)}.dot.d-low{background:var(--c-low)}
.lg .v{margin-left:auto;color:var(--muted)}
.hb{display:flex;flex-direction:column;gap:8px}
.hb-r{display:grid;grid-template-columns:minmax(120px,38%) 1fr 28px;gap:8px;align-items:center;font-size:12px}
.hb-r .bar{height:8px}
.email{white-space:pre-wrap;font-size:12px;background:var(--inner);border:1px solid var(--inner-line);border-radius:8px;padding:12px;overflow-wrap:anywhere}
.fit{min-width:112px;justify-content:center}
.foot{max-width:1080px;margin:0 auto;padding:8px 24px 32px;font-size:11px;color:var(--faint)}
@media (max-width:760px){.grid2,.spin,.cols{grid-template-columns:1fr}main{padding:12px}.topnav{padding:0 12px}.card{padding:16px}.hb-r{grid-template-columns:1fr 1fr 24px}}
@media print{.topnav .seg{display:none}.topnav{position:static}.card{break-inside:avoid}}
""".replace("%LIGHT%", _LIGHT_VARS).replace("%DARK%", _DARK_VARS)

_CSP = ("default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'")

# ---------------------------------------------------------------------------
# Design system: components (all return Html)
# ---------------------------------------------------------------------------

_KINDS = {"ok", "warn", "info", "bad", "acc", "neutral"}


def pill(text: Any, kind: str = "neutral", extra: str = "") -> Html:
    k = kind if kind in _KINDS else "neutral"
    x = " fit" if extra == "fit" else ""
    return Html(f'<span class="pill {k}{x}">{e(text)}</span>')


_LABELS = {
    "verified": ("Verified", "ok"),
    "synthetic": ("Synthetic CRM", "info"),
    "ai": ("AI-generated", "acc"),
    "unknown": ("Unknown", "warn"),
    "unverified": ("Unverified spec", "warn"),
}


def label_pill(key: str) -> Html:
    text, kind = _LABELS.get(key, ("Unknown", "warn"))
    return pill(text, kind)


def risk_pill(rating: Any) -> Html:
    r = _s(rating, "Unrated")
    low = r.lower()
    kind = "bad" if low.startswith("high") else "warn" if low.startswith("medium") else \
        "ok" if low.startswith("low") else "neutral"
    return pill(r, kind)


def fit_pill(status: Any) -> Html:
    st = _s(status, "Unknown / insufficient evidence")
    low = st.lower()
    kind = "ok" if low.startswith("supported") else "warn" if low.startswith("partially") else \
        "bad" if low.startswith("not supported") else "neutral"
    return pill(st, kind, "fit")


def unknown_badge(text: Any) -> Html:
    return Html(f'<span class="unk">{e(text)} <i>(Unknown)</i></span>')


def chips(items: Iterable[Html]) -> Html:
    return Html(f'<div class="chips">{jn(items)}</div>')


def card(title: str, inner: Any, *, sub: str = "", count: Any = None) -> Html:
    head = f"<h2>{e(title)}</h2>"
    if sub:
        head += f'<span class="muted xs">{e(sub)}</span>'
    if count is not None:
        head += f'<span class="count">{e(count)}</span>'
    return Html(f'<section class="card"><div class="card-h">{head}</div>{e(inner)}</section>')


def disclosure(summary: str, inner: Any, *, open_: bool = False, count: Any = None) -> Html:
    cnt = f'<span class="count">{e(count)}</span>' if count is not None else ""
    return Html(f'<details class="disc"{" open" if open_ else ""}><summary><span>{e(summary)}</span>{cnt}'
                f'</summary><div class="disc-b">{e(inner)}</div></details>')


def callout(text: Any, kind: str = "info") -> Html:
    cls = {"warn": " warn", "bad": " bad"}.get(kind, "")
    return Html(f'<div class="callout{cls}">{e(text)}</div>')


def ul(items: Iterable[Any], *, ordered: bool = False, plain: bool = False) -> Html:
    tag = "ol" if ordered else "ul"
    cls = "list plain" if plain else "list"
    lis = "".join(f"<li>{e(i)}</li>" for i in items)
    return Html(f'<{tag} class="{cls}">{lis}</{tag}>') if lis else Html("")


def table(headers: list[str], rows: list[list[Any]], *, center_from: int = -1) -> Html:
    def th(i: int, h: str) -> str:
        return f'<th class="c">{e(h)}</th>' if 0 <= center_from <= i else f"<th>{e(h)}</th>"

    def td(i: int, c: Any) -> str:
        return f'<td class="c">{e(c)}</td>' if 0 <= center_from <= i else f"<td>{e(c)}</td>"

    head = "".join(th(i, h) for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(td(i, c) for i, c in enumerate(r)) + "</tr>" for r in rows)
    return Html(f'<div class="tblwrap"><table class="tbl"><thead><tr>{head}</tr></thead>'
                f"<tbody>{body}</tbody></table></div>")


def kv(pairs: list[tuple[str, Any]], *, fallback: str = "Unknown") -> Html:
    cells = []
    for k, v in pairs:
        val = v if isinstance(v, Html) else _s(v, fallback)
        cells.append(f"<div><dt>{e(k)}</dt><dd>{e(val)}</dd></div>")
    return Html(f'<dl class="kv">{"".join(cells)}</dl>')


def metrics(items: list[tuple[str, Any]]) -> Html:
    cells = "".join(f'<div class="metric"><div class="m-l">{e(l)}</div><div class="m-v">{e(v)}</div></div>'
                    for l, v in items)
    return Html(f'<div class="metrics">{cells}</div>')


def row(icon: Any, title: Any, sub: Any = "", value: Any = "", wide: bool = False) -> Html:
    s = f'<div class="r-s">{e(sub)}</div>' if sub not in ("", None) else ""
    v = f'<div class="r-v">{e(value)}</div>' if value not in ("", None) else ""
    return Html(f'<div class="row"><div class="ico{" wide" if wide else ""}">{e(icon)}</div><div class="r-b">'
                f'<div class="r-t">{e(title)}</div>{s}</div>{v}</div>')


def score_bar(score: Any, rating: Any) -> Html:
    if not _isnum(score):
        return Html("")
    w = max(4, min(100, int(round(score * 100 / 10))))  # visual scale: 10 points = full bar
    low = _s(rating, "").lower()
    cls = "s-high" if low.startswith("high") else "s-med" if low.startswith("medium") else \
        "s-low" if low.startswith("low") else ""
    return Html(f'<div class="bar" role="img" aria-label="Risk score {e(score)}"><span class="{cls}" '
                f'style="width:{w}%"></span></div>')


def hero(label: str, subject: str, subtitle: str, pills: list[Html], mono: str = "SF") -> Html:
    return Html(
        '<section class="card hero"><div class="hero-l">'
        f'<div class="mono-box" aria-hidden="true">{e(mono)}</div><div style="min-width:0">'
        f'<div class="eyebrow">{e(label)}</div><h1>{e(subject)}</h1><p>{e(subtitle)}</p></div></div>'
        f'<div class="pills">{jn(pills)}</div></section>')


def _initials(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name)
    return "".join(w[0] for w in words[:2]).upper() or "SF"


# --- charts ---------------------------------------------------------------


def donut(items: list[tuple[str, int, str]], center: str = "deals") -> Html:
    """Inline-SVG donut. items: (label, count, ring_class) with ring_class from a fixed allowlist."""
    allowed = {"r-high", "r-med", "r-low"}
    total = sum(c for _, c, _ in items)
    if total <= 0:
        return Html("")
    circles = ['<circle class="ring r-track" cx="21" cy="21" r="15.9155" fill="none" stroke-width="5"/>']
    offset = 25.0
    for _label, count, cls in items:
        if count <= 0 or cls not in allowed:
            continue
        pct = count / total * 100
        circles.append(
            f'<circle class="ring {cls}" cx="21" cy="21" r="15.9155" fill="none" stroke-width="5" '
            f'stroke-dasharray="{pct:.3f} {100 - pct:.3f}" stroke-dashoffset="{offset:.3f}"/>')
        offset -= pct
    desc = ", ".join(f"{l}: {c}" for l, c, _ in items if c > 0)
    return Html(
        f'<svg class="donut" viewBox="0 0 42 42" role="img" aria-label="Deal risk distribution: {e(desc)}">'
        f"<title>Deal risk distribution</title><desc>{e(desc)}</desc>{''.join(circles)}"
        f'<text x="21" y="22.2" class="ring-n">{e(total)}</text>'
        f'<text x="21" y="26.6" class="ring-l">{e(center)}</text></svg>')


def hbars(items: list[tuple[str, int]]) -> Html:
    if not items:
        return Html("")
    mx = max((c for _, c in items), default=0) or 1
    rows = []
    for label, count in items:
        w = max(3, min(100, int(round(count * 100 / mx))))
        rows.append(f'<div class="hb-r"><span>{e(label)}</span><div class="bar"><span style="width:{w}%">'
                    f'</span></div><span class="muted">{e(count)}</span></div>')
    return Html(f'<div class="hb" role="img" aria-label="Top risk factors by number of deals">{"".join(rows)}</div>')


# ---------------------------------------------------------------------------
# Shared report plumbing
# ---------------------------------------------------------------------------


class _R:
    """Collects unknowns, source references and disclaimers while rendering."""

    def __init__(self, synthetic: bool):
        self.synthetic = synthetic
        self.unknowns: list[str] = []
        self.refs: list[tuple] = []
        self.disclaimers: list[str] = []

    def add_unknowns(self, items: Iterable[Any]) -> None:
        for x in items:
            t = _item_text(x) if not isinstance(x, str) else x.strip()
            if t:
                self.unknowns.append(t)


def _derive_sources(explicit: Any, refs: list[tuple]) -> list[dict]:
    """Union of supplied sources and ids found in content, de-duplicated.

    Type/title are derived from the id prefix only; nothing else is invented.
    """
    out: list[dict] = []
    seen: set = set()

    def add(sid: Any, url: Any, date: Any, title: Any = None, stype: Any = None, note: Any = None) -> None:
        sid = sid if isinstance(sid, str) else ""
        url = url if isinstance(url, str) else ""
        key = (sid, url)
        if key == ("", "") or key in seen:
            return
        seen.add(key)
        low = sid.lower()
        stype = stype if isinstance(stype, str) and stype else (
            "Synthetic CRM" if "_crm_" in low else "Product catalog" if "_prod_" in low
            else "Playbook" if "playbook" in low else "")
        out.append({"source_id": sid, "type": stype, "url": url,
                    "verified": date if isinstance(date, str) else "",
                    "title": title if isinstance(title, str) else "",
                    "note": note if isinstance(note, str) else ""})

    for s in _l(explicit):
        if isinstance(s, dict):
            add(s.get("source_id") or s.get("id"), s.get("source_url") or s.get("url"),
                s.get("verified_date"), s.get("title"), s.get("source_type"), s.get("note"))
    for r in refs:
        sid, url, date = (list(r) + [None, None])[:3]
        add(sid, url, date)
    return out[:LIST_CAP]


def _unknowns_card(r: _R) -> Html:
    items = [u for u in dict.fromkeys(u.strip() for u in r.unknowns if u and u.strip())]
    if not items:
        return card("Unknown information",
                    callout("No unknowns were supplied with this report. Absence of a list is not confirmation "
                            "that everything is known.", "warn"))
    shown, hidden = _cap(items)
    inner = jn([callout("Items below are not in the data and must be confirmed."),
                Html('<div style="height:10px"></div>'), chips([unknown_badge(u) for u in shown]),
                Html(f'<p class="muted xs" style="margin-top:8px">{hidden} more not shown.</p>') if hidden else ""])
    return card("Unknown information", inner, count=len(items))


def _sources_card(r: _R, c: dict) -> Html:
    sources = _derive_sources(c.get("sources"), r.refs)
    parts: list[Html] = []
    if r.synthetic:
        parts.append(callout("Synthetic demonstration data. Customer, opportunity and product records in this "
                             "report are fictional placeholders, not real customer or product facts.", "warn"))
    else:
        parts.append(callout("Data supplied by the seller or CRM. Verify before relying on it."))
    if sources:
        rows = []
        for s in sources:
            link = _link(s["url"], "Open source")
            if not link and s["url"]:
                link = Html(f'<span class="muted xs">Link withheld (not a validated https IBM URL)</span>')
            rows.append([Html(f'<span class="mono">{e(s["source_id"] or "no id")}</span>'),
                         s["type"] or "-", link or "-", s["verified"] or "-"])
        parts.append(disclosure("Source references", table(["Source ID", "Type", "Link", "Verified"], rows),
                                count=len(sources)))
    else:
        parts.append(Html('<p class="muted xs">No source references were supplied with this report.</p>'))
    legend = jn([
        Html(f'<div class="rows">{row("V", "Verified", "Returned by a SalesFlow tool and cited by source ID.")}'),
        row("S", "Synthetic CRM", "From the synthetic demonstration CRM; not real customer data."),
        row("A", "AI-generated", "Written or inferred by the assistant from the data; check before use."),
        row("?", "Unknown", "Not available from any tool; confirm with the customer."),
        row("U", "Unverified spec", "Catalog entry has no verified public source; treat as a placeholder."),
        Html("</div>")])
    parts.append(disclosure("Information integrity: how to read the labels", legend))
    disc = [STANDARD_DISCLAIMER, LINKS_NOTE] + [d for d in dict.fromkeys(r.disclaimers) if d]
    parts.append(Html(f'<p class="muted xs" style="margin-top:10px">{e(" ".join(disc))}</p>'))
    return card("Sources and verification", jn(parts, "\n"))


def _exec_summary_card(items: Any, points: list[str]) -> Html:
    supplied = [t for t in _strs(items)][:20]
    inner = []
    if points:
        inner.append(ul(points))
    if supplied:
        inner.append(Html(f'<div style="margin-top:10px">{label_pill("ai")} '
                          '<span class="muted xs">Assistant-written summary based on the data in this report.</span>'
                          "</div>"))
        inner.append(Html('<div style="margin-top:6px"></div>'))
        inner.append(ul(supplied))
    return card("Executive summary", jn(inner)) if inner else Html("")


def _stakeholder_table(stakeholders: Any) -> Html:
    rows = []
    for s in _l(stakeholders)[:50]:
        if isinstance(s, dict):
            rows.append([_txt(s, "role", "role_hint") or "Role unknown", _txt(s, "name") or "Name not confirmed",
                         _txt(s, "notes", "source_sentence") or "-"])
        elif isinstance(s, str) and s.strip():
            rows.append(["Role unknown", s.strip(), "-"])
    return table(["Role", "Name", "Notes"], rows) if rows else Html("")


def _action_table(actions: list[dict]) -> Html:
    rows = []
    for a in actions[:LIST_CAP]:
        owner = a.get("owner") or ""
        deadline = a.get("deadline") or ""
        basis = a.get("basis") or ""
        rows.append([a.get("action") or "-",
                     owner if owner else Html('<span class="muted">[Unknown]</span>'),
                     deadline if deadline else Html('<span class="muted">[TBD]</span>'),
                     basis if basis else "-"])
    return table(["Action", "Owner", "Deadline", "Basis"], rows)


def _subtitle(now: datetime, synthetic: bool, extra: str = "") -> str:
    base = f"Generated {now.strftime('%Y-%m-%d %H:%M UTC')} \u00b7 DRAFT for seller review \u00b7 " \
           f"{'Synthetic demo data' if synthetic else 'Seller/CRM-supplied data'}"
    return base + (f" \u00b7 {extra}" if extra else "")


def _status_pills(synthetic: bool, *extra: Html) -> list[Html]:
    out = [pill("DRAFT", "neutral"), label_pill("synthetic") if synthetic else label_pill("verified")]
    return out + list(extra)


# ---------------------------------------------------------------------------
# Risk helpers (pipeline, deal risk, account, action plan)
# ---------------------------------------------------------------------------


def _deal_view(d: Any, idx: int) -> dict:
    d = _d(d)
    opp = _txt(d, "opportunity_name", "name") or _txt(d, "opportunity_id") or "Unnamed opportunity"
    acct = _txt(d, "account_name")
    title = f"{acct}: {opp}" if acct and acct not in opp else opp
    evidence: list[str] = []
    actions: list[str] = []
    for f in _l(d.get("evidence")) + _l(d.get("flagged_risks")):
        line, act = "", ""
        if isinstance(f, str):
            line = f.strip()
        elif isinstance(f, dict):
            factor, ev = _txt(f, "factor"), _txt(f, "evidence")
            pts = f.get("score_contribution")
            ps = f"+{pts}" if _isnum(pts) else ""
            head = f"{factor} ({ps})" if factor and ps else factor
            line = f"{head}: {ev}" if head and ev else (head or ev)
            act = _txt(f, "recommended_action")
        if line and line not in evidence:
            evidence.append(line)
        if act and act not in actions:
            actions.append(act)
    for a in _l(d.get("recommended_actions")):
        if isinstance(a, str) and a.strip() and a.strip() not in actions:
            actions.append(a.strip())
    value = d.get("value")
    return {
        "rank": d.get("rank") if _isnum(d.get("rank")) else idx,
        "title": title,
        "stage": _txt(d, "stage") or "Stage unknown",
        "seller": _txt(d, "seller"),
        "close": _txt(d, "close_date"),
        "value": value if _isnum(value) else None,
        "rating": _txt(d, "risk_rating") or "Unrated",
        "score": d.get("risk_score") if _isnum(d.get("risk_score")) else None,
        "evidence": evidence, "actions": actions,
        "unknown": [_readable(u) for u in _l(d.get("unknown_factors")) if isinstance(u, str) and u.strip()],
        "source_id": _txt(d, "source_id"),
        "disclaimer": _txt(d, "disclaimer"),
    }


def _deal_card(v: dict, *, expand: bool = True) -> Html:
    meta = " \u00b7 ".join(x for x in (
        v["stage"], f"Seller {v['seller']}" if v["seller"] else "",
        f"Close {v['close']}" if v["close"] else "",
        f"CRM value {_money(v['value'])}" if v["value"] is not None else "") if x)
    score = f'<span class="score">Score {e(v["score"])}</span>' if v["score"] is not None else ""
    acts = v["actions"]
    top_actions = ul(acts[:2]) if acts else Html('<p class="muted xs">No action recorded.</p>')
    more_actions = disclosure("All recommended actions", ul(acts), count=len(acts)) if len(acts) > 2 else Html("")
    ev = ul(v["evidence"]) if v["evidence"] else Html('<p class="muted xs">No risk evidence recorded.</p>')
    unk = ""
    if v["unknown"]:
        unk = Html(f'<div><h4>Fields missing from the CRM (not scored as risk)</h4>'
                   f'{chips([unknown_badge(u) for u in v["unknown"]])}</div>')
    return Html(
        '<article class="deal"><div class="deal-h"><div class="deal-t">'
        f'<div class="ico">{e(v["rank"])}</div><div style="min-width:0"><div class="r-t">{e(v["title"])}</div>'
        f'<div class="r-s">{e(meta)}</div></div></div>'
        f'<div class="deal-r">{risk_pill(v["rating"])}{score}</div></div>'
        f'{score_bar(v["score"], v["rating"])}'
        f'<div><h4>Recommended actions</h4>{top_actions}{more_actions}</div>'
        f'{disclosure("Risk evidence", ev, open_=expand, count=len(v["evidence"]))}{unk}</article>')


def _dist_items(dist: Any) -> list[tuple[str, int, Any]]:
    """Normalize a risk distribution dict to [(label, count, value)] in High/Medium/Low order."""
    dist = _d(dist)
    out = []
    for label, keys in (("High Risk", ("High Risk", "high_risk")), ("Medium Risk", ("Medium Risk", "medium_risk")),
                        ("Low Risk", ("Low Risk", "low_risk"))):
        v = {}
        for k in keys:
            if isinstance(dist.get(k), dict):
                v = dist[k]
                break
        cnt = v.get("count")
        out.append((label, int(cnt) if _isnum(cnt) else 0, v.get("value") if _isnum(v.get("value")) else None))
    return out


def _dist_from_deals(views: list[dict]) -> list[tuple[str, int, Any]]:
    out = []
    for label, prefix in (("High Risk", "high"), ("Medium Risk", "medium"), ("Low Risk", "low")):
        sel = [v for v in views if v["rating"].lower().startswith(prefix)]
        vals = [v["value"] for v in sel if v["value"] is not None]
        out.append((label, len(sel), sum(vals) if vals else None))
    return out


def _risk_chart_card(dist: list[tuple[str, int, Any]], factors: Any, *, computed: bool) -> Html:
    cls = {"High Risk": ("r-high", "d-high"), "Medium Risk": ("r-med", "d-med"), "Low Risk": ("r-low", "d-low")}
    total = sum(c for _, c, _ in dist)
    if total <= 0 and not _l(factors):
        return Html("")
    legend = "".join(
        f'<div class="lg"><span class="dot {cls[l][1]}"></span><span>{e(l)}</span>'
        f'<span class="v">{e(c)} deal{"s" if c != 1 else ""}'
        f'{" \u00b7 " + e(_money(v)) if v is not None else ""}</span></div>' for l, c, v in dist)
    chart = ""
    if total > 0:
        chart = (f'<div class="chart">{donut([(l, c, cls[l][0]) for l, c, _ in dist])}'
                 f'<div class="legend">{legend}</div></div>')
    fac = []
    for f in _l(factors)[:8]:
        if isinstance(f, dict) and _txt(f, "factor"):
            cnt = f.get("count")
            fac.append((_txt(f, "factor"), int(cnt) if _isnum(cnt) else 0))
    note = Html('<p class="muted xs" style="margin-top:10px">Distribution computed from the deals listed in this '
                "report.</p>") if computed and total > 0 else Html("")
    inner = jn([Html(chart), note,
                Html(f'<h3>Most common risk factors</h3>{hbars(fac)}') if fac else Html("")])
    return card("Risk distribution", inner, sub="Deals by rating")


# ---------------------------------------------------------------------------
# Template 1: Discovery Meeting Brief
# ---------------------------------------------------------------------------


def _gap_label(g: Any) -> str:
    if isinstance(g, dict):
        return _txt(g, "gap", "label")
    return g.strip() if isinstance(g, str) else ""


def _select_spin(spin: list) -> list[dict]:
    items = [q for q in spin if isinstance(q, dict)]
    chosen: list[dict] = []
    for cat in SPIN_ORDER:
        m = next((q for q in items if q.get("category") == cat), None)
        if m:
            chosen.append(m)
        else:
            fb = next((q for q in items if q not in chosen), None)
            if fb:
                chosen.append({**fb, "category": cat})
    return chosen


def _render_discovery(c: dict, now: datetime) -> tuple[str, str, str]:
    acct, opp = _d(c.get("account")), _d(c.get("opportunity"))
    synthetic = bool(c.get("synthetic", True))
    r = _R(synthetic)
    name = _s(acct.get("name"), "Unknown Account")
    opp_name = _txt(opp, "name") or _txt(opp, "opportunity_id") or "Unknown"
    stage = _txt(opp, "stage") or "Unknown"
    positioning = _d(c.get("solution_positioning"))
    products = [p for p in _l(positioning.get("products")) if isinstance(p, dict)]
    gaps = [g for g in (_gap_label(g) for g in _l(c.get("qualification_gaps"))) if g]
    why = [(_gap_label(g), _txt(g, "why_it_matters")) for g in _l(c.get("qualification_gaps")) if isinstance(g, dict)]
    agenda = [a for a in _l(c.get("agenda")) if isinstance(a, dict)]
    spin_all = _l(c.get("spin_questions"))
    spin = _select_spin(spin_all)
    steps = _strs(c.get("next_steps"))[:3]

    r.add_unknowns(_l(acct.get("unknowns")) + _l(opp.get("unknowns")) + _l(c.get("unknowns")))
    r.unknowns += gaps
    r.refs += [(acct.get("source_id"),), (opp.get("source_id"),)]
    if c.get("playbook_available") and c.get("playbook_source_id"):
        r.refs.append((c.get("playbook_source_id"),))
    for p in products:
        r.refs.append((p.get("source_id"), p.get("source_url"), p.get("verified_date")))

    parts: list[Html] = [hero("Discovery Meeting Brief", name, _subtitle(now, synthetic),
                              _status_pills(synthetic, pill(stage, "info")), _initials(name))]

    snap = [kv([("Company", name), ("Industry", acct.get("industry")), ("Opportunity", opp_name),
                ("Stage", stage)])]
    if acct.get("overview"):
        snap.append(Html(f'<p class="muted" style="margin-top:12px">{e(acct["overview"])}</p>'))
    parts.append(card("Account snapshot", jn(snap)))
    parts.append(metrics([("SPIN questions", len(spin)), ("Agenda segments", len(agenda)),
                          ("Qualification gaps", len(gaps)), ("Unknown items", len(set(r.unknowns)))]))
    parts.append(_exec_summary_card(c.get("executive_summary"), []))

    if spin:
        cells = "".join(
            f'<div class="spin-q"><div>{pill(_s(q.get("category")), "info")}</div>'
            f'<p>{e(_s(q.get("question") or q.get("text")))}</p></div>' for q in spin)
        parts.append(card("Discovery questions (SPIN)", Html(f'<div class="spin">{cells}</div>'),
                          sub="One per category; the seller chooses what to ask"))

    left: list[Html] = []
    if agenda:
        rows = "".join(str(row(_s(a.get("time_slot", a.get("time")), "-"), _s(a.get("segment")),
                               _s(a.get("goal", a.get("objective")), ""), wide=True)) for a in agenda)
        left.append(card("30-minute agenda", Html(f'<div class="rows">{rows}</div>')))
    if gaps:
        gp = [chips([unknown_badge(g) for g in gaps])]
        shown_why = [(g, w) for g, w in why if w]
        if shown_why:
            gp.append(Html('<div style="margin-top:10px"></div>'))
            gp.append(disclosure("Why these gaps matter",
                                 table(["Gap", "Why it matters"], [[g, w] for g, w in shown_why])))
        left.append(card("Qualification gaps", jn(gp)))
    if left:
        parts.append(Html(f'<div class="grid2">{jn(left)}</div>') if len(left) == 2 else left[0])

    if products:
        rows = []
        for p in products[:LIST_CAP]:
            group = _s(p.get("category") or p.get("product_group"), "Not specified")
            group = group[:1].upper() + group[1:]
            link = _link(p.get("source_url"), "IBM product page") or Html('<span class="muted">Link unavailable</span>')
            rows.append([_s(p.get("name")), group, link])
        parts.append(card("Potential IBM products", table(["Product", "Product group", "Official IBM product page"],
                                                         rows), sub="Worth exploring, not a validated fit"))

    if steps:
        parts.append(card("Next steps", ul(steps, ordered=True), sub="Maximum three"))

    detail: list[Html] = []
    if acct.get("challenges"):
        detail.append(disclosure("Business challenges on record", ul(_strs(acct["challenges"])),
                                 count=len(_strs(acct["challenges"]))))
    if opp.get("requirements"):
        detail.append(disclosure("Stated requirements", ul(_strs(opp["requirements"])),
                                 count=len(_strs(opp["requirements"]))))
    if _stakeholder_table(opp.get("stakeholders")):
        detail.append(disclosure("Stakeholders", _stakeholder_table(opp.get("stakeholders"))))
    if opp.get("notes"):
        detail.append(disclosure("Meeting history", ul(_strs(opp["notes"])), count=len(_strs(opp["notes"]))))
    extra_spin = [q for q in spin_all if isinstance(q, dict) and q not in spin]
    if extra_spin:
        detail.append(disclosure("Additional SPIN questions", ul(
            [f"{_s(q.get('category'))}: {_s(q.get('question') or q.get('text'))}" for q in extra_spin[:LIST_CAP]],
            ordered=True), count=len(extra_spin)))
    if products:
        pd = []
        for p in products[:LIST_CAP]:
            ver = label_pill("verified") if p.get("verification_status") == "verified" else label_pill("unverified")
            body = [Html(f"<div>{ver}</div>")]
            if p.get("summary"):
                body.append(Html(f'<p class="xs">{e(p["summary"])}</p>'))
            if _strs(p.get("capabilities")):
                body.append(Html(f'<h4>Documented capabilities</h4>{ul(_strs(p.get("capabilities")))}'))
            if _strs(p.get("limitations")):
                body.append(Html(f'<h4>Limitations</h4>{ul(_strs(p.get("limitations")))}'))
            if p.get("source_id"):
                body.append(Html(f'<p class="muted xxs">Source <span class="mono">{e(p["source_id"])}</span></p>'))
            pd.append(disclosure(_s(p.get("name")), jn(body)))
        detail.append(disclosure("Product catalog detail (from catalog text only)", jn(pd), count=len(products)))
    notes = [t for t in (positioning.get("directional_angle"), positioning.get("notice"),
                         c.get("methodology_note")) if isinstance(t, str) and t.strip()]
    if notes:
        detail.append(disclosure("Positioning notes and method", ul(notes)))
    if detail:
        parts.append(card("Additional detail", jn(detail), sub="Expand for the full record"))

    parts += [_unknowns_card(r), _sources_card(r, c)]
    return jn(parts, "\n"), name, "Discovery Meeting Brief"


# ---------------------------------------------------------------------------
# Template 2: Executive Account Summary
# ---------------------------------------------------------------------------


def _render_account_summary(c: dict, now: datetime) -> tuple[str, str, str]:
    acct = _d(c.get("account"))
    synthetic = bool(c.get("synthetic", True))
    r = _R(synthetic)
    name = _s(acct.get("name"), "Unknown Account")
    opps = [o for o in _l(c.get("opportunities")) if isinstance(o, dict)][:50]
    views = [_deal_view(d, i) for i, d in enumerate(_l(c.get("at_risk_deals"))[:50], 1)]
    high = sum(1 for v in views if v["rating"].lower().startswith("high"))

    r.add_unknowns(_l(acct.get("unknowns")) + _l(c.get("unknowns")))
    for o in opps:
        r.add_unknowns(_l(o.get("unknowns")))
        r.refs.append((o.get("source_id"),))
    r.refs.append((acct.get("source_id"),))
    r.refs += [(v["source_id"],) for v in views]
    for v in views:
        if v["disclaimer"]:
            r.disclaimers.append(v["disclaimer"])
            break

    key = [name + (f" operates in {acct['industry']}." if acct.get("industry") else ".")]
    if opps:
        key.append(f"{len(opps)} opportunity record(s) on file.")
    if views:
        key.append(f"{len(views)} deal(s) flagged by the risk engine, {high} rated High Risk.")

    parts: list[Html] = [hero("Executive Account Summary", name, _subtitle(now, synthetic),
                              _status_pills(synthetic), _initials(name))]
    parts.append(metrics([("Opportunities", len(opps)), ("Flagged deals", len(views)), ("High risk", high),
                          ("Unknown items", len(set(r.unknowns)))]))
    parts.append(_exec_summary_card(c.get("executive_summary"), key))

    snap = [kv([("Account", name), ("Account ID", acct.get("account_id")), ("Industry", acct.get("industry"))])]
    snap.append(Html(f'<p class="muted" style="margin-top:12px">{e(acct["overview"])}</p>') if acct.get("overview")
                else callout("Account overview not provided.", "warn"))
    if _strs(acct.get("challenges")):
        snap.append(Html(f'<h3>Business challenges on record</h3>{ul(_strs(acct["challenges"]))}'))
    parts.append(card("Account snapshot", jn(snap)))

    if opps:
        rows = [[_s(o.get("name"), "Unnamed"), Html(f'<span class="mono">{e(_s(o.get("opportunity_id")))}</span>'),
                 pill(_s(o.get("stage")), "info")] for o in opps]
        inner = [table(["Opportunity", "ID", "Stage"], rows)]
        for o in opps:
            reqs, sh = _strs(o.get("requirements")), _stakeholder_table(o.get("stakeholders"))
            if reqs or sh:
                body = []
                if reqs:
                    body.append(Html(f"<h4>Requirements on record</h4>{ul(reqs)}"))
                if sh:
                    body.append(Html(f"<h4>Stakeholders</h4>{sh}"))
                inner.append(disclosure(_s(o.get("name") or o.get("opportunity_id"), "Opportunity"), jn(body)))
        parts.append(card("Opportunities", jn(inner[:1] + [Html('<div style="height:10px"></div>')] + inner[1:]),
                          count=len(opps)))

    if views:
        top, rest = views[:3], views[3:]
        inner = [callout(HEURISTIC_NOTE), Html('<div class="stack" style="margin-top:12px">'
                                                f'{jn(_deal_card(v, expand=False) for v in top)}</div>')]
        if rest:
            inner.append(Html('<div style="height:10px"></div>'))
            inner.append(disclosure("Other flagged deals", Html(
                f'<div class="stack">{jn(_deal_card(v, expand=False) for v in rest)}</div>'), count=len(rest)))
        parts.append(card("Risk posture", jn(inner), sub="Highest risk first"))

    steps = _strs(c.get("next_steps"))
    if steps:
        parts.append(card("Recommended next steps", ul(steps[:LIST_CAP], ordered=True)))
    parts += [_unknowns_card(r), _sources_card(r, c)]
    return jn(parts, "\n"), name, "Executive Account Summary"


# ---------------------------------------------------------------------------
# Template 3: Opportunity Action Plan
# ---------------------------------------------------------------------------


def _crm_updates_table(updates: list) -> Html:
    rows = []
    for u in updates[:LIST_CAP]:
        if not isinstance(u, dict):
            continue
        val = u.get("proposed_value") if "proposed_value" in u else u.get("value")
        rows.append([_readable(u.get("field") or u.get("name") or "field unknown"),
                     "-" if val is None else str(val), _s(u.get("uncertainty"), "Unknown"),
                     _txt(u, "excerpt") or "-"])
    if not rows:
        return Html("")
    return jn([callout("These are proposals only. Nothing has been written to the CRM; the seller must approve "
                       "each change.", "warn"), Html('<div style="height:10px"></div>'),
               table(["Field", "Proposed value", "Uncertainty", "Supporting excerpt"], rows)])


def _render_action_plan(c: dict, now: datetime) -> tuple[str, str, str]:
    name = _s(c.get("account_name"), "Unknown Account")
    synthetic = bool(c.get("synthetic", True))
    r = _R(synthetic)
    opp = _d(c.get("opportunity"))
    views = [_deal_view(d, i) for i, d in enumerate(_l(c.get("risks"))[:50], 1)]

    actions: list[dict] = []
    seen: set = set()
    for a in _l(c.get("actions")):
        if isinstance(a, dict):
            t = _txt(a, "action", "text")
            if t and t not in seen:
                seen.add(t)
                actions.append({"action": t, "owner": _txt(a, "owner"), "deadline": _txt(a, "deadline"),
                                "basis": _txt(a, "basis", "confidence") or "AI-generated"})
        elif isinstance(a, str) and a.strip() and a.strip() not in seen:
            seen.add(a.strip())
            actions.append({"action": a.strip(), "owner": "", "deadline": "", "basis": "AI-generated"})
    for v in views:
        for a in v["actions"]:
            if a not in seen:
                seen.add(a)
                actions.append({"action": a, "owner": "", "deadline": "", "basis": "AI-generated"})
    unowned = sum(1 for a in actions if not a["owner"])

    r.add_unknowns(_l(c.get("unknowns")) + _l(opp.get("unknowns")) + _l(c.get("open_questions")))
    r.refs.append((opp.get("source_id"),))
    r.refs += [(v["source_id"],) for v in views]
    for v in views:
        if v["disclaimer"]:
            r.disclaimers.append(v["disclaimer"])
            break

    key = []
    if opp.get("name"):
        key.append(f"Plan for {opp['name']}" + (f" (stage: {opp['stage']})." if opp.get("stage") else "."))
    key.append(f"{len(actions)} action(s) proposed; {unowned} still need an owner." if actions
               else "No actions were supplied or derivable from the risk data.")

    parts: list[Html] = [hero("Opportunity Action Plan", name, _subtitle(now, synthetic),
                              _status_pills(synthetic, pill(_s(opp.get("stage"), "Stage unknown"), "info")),
                              _initials(name))]
    parts.append(metrics([("Actions", len(actions)), ("Need an owner", unowned), ("Risks addressed", len(views)),
                          ("Open questions", len(_l(c.get("open_questions"))))]))
    parts.append(_exec_summary_card(c.get("executive_summary"), key))

    if actions:
        parts.append(card("Action plan", jn([
            callout("Actions come from the risk engine and the seller's input. Owners and deadlines are shown only "
                    "when supplied; otherwise they are marked for the seller to set."),
            Html('<div style="height:10px"></div>'), _action_table(actions)]), count=len(actions)))
    else:
        parts.append(card("Action plan", callout("Action items were not provided.", "warn")))

    if views:
        parts.append(card("Risks this plan addresses", Html(
            f'<div class="stack">{jn(_deal_card(v, expand=False) for v in views)}</div>'), count=len(views)))

    detail: list[Html] = []
    if _strs(opp.get("requirements")):
        detail.append(disclosure("Requirements on record", ul(_strs(opp["requirements"])),
                                 count=len(_strs(opp["requirements"]))))
    if _stakeholder_table(opp.get("stakeholders")):
        detail.append(disclosure("Stakeholders", _stakeholder_table(opp.get("stakeholders"))))
    if _l(c.get("crm_updates")) and _crm_updates_table(_l(c.get("crm_updates"))):
        detail.append(disclosure("Proposed CRM updates (not applied)", _crm_updates_table(_l(c["crm_updates"])),
                                 count=len(_l(c["crm_updates"]))))
    if _strs(c.get("open_questions")):
        detail.append(disclosure("Open questions", ul(_strs(c["open_questions"])),
                                 count=len(_strs(c["open_questions"])), open_=True))
    if detail:
        parts.append(card("Supporting detail", jn(detail)))

    parts += [_unknowns_card(r), _sources_card(r, c)]
    return jn(parts, "\n"), name, "Opportunity Action Plan"


# ---------------------------------------------------------------------------
# Templates 4 and 7: Deal Risk Assessment / Weekly Pipeline Risk Digest
# ---------------------------------------------------------------------------


def _render_pipeline(c: dict, now: datetime, *, digest_mode: bool) -> tuple[str, str, str]:
    digest = _d(c.get("digest"))
    summary = _d(digest.get("summary") or c.get("pipeline_summary") or c.get("summary"))
    deals_raw = _l(digest.get("flagged_deals")) or _l(c.get("deals"))
    synthetic = bool(c.get("synthetic", True)) and digest.get("synthetic_data") is not False
    r = _R(synthetic)
    scope = _s(digest.get("seller_scope") or c.get("seller_scope") or c.get("account_name"), "All sellers")
    views = [_deal_view(d, i) for i, d in enumerate(deals_raw[:200], 1)]
    views.sort(key=lambda v: (-(v["score"] or 0), -(v["value"] or 0), v["title"]))
    for i, v in enumerate(views, 1):
        v["rank"] = i

    total_deals = summary.get("active_deals_analyzed", summary.get("total_deals"))
    total_value = summary.get("total_active_value", summary.get("total_value"))
    flagged = summary.get("flagged_deals")
    flagged = flagged if _isnum(flagged) else len(views)
    dist = _dist_items(summary.get("risk_distribution"))
    computed = sum(c_ for _, c_, _ in dist) == 0
    if computed:
        dist = _dist_from_deals(views)
    high = dist[0][1]
    factors = _l(summary.get("top_risk_factors"))

    r.add_unknowns(_l(c.get("unknowns")))
    for v in views:
        r.unknowns += [f"{v['title']}: {u}" for u in v["unknown"]]
        r.refs.append((v["source_id"],))
    for t in (digest.get("disclaimer"), digest.get("limitations")):
        if isinstance(t, str) and t.strip():
            r.disclaimers.append(t.strip())
    if _d(c.get("pipeline_summary")).get("disclaimer"):
        r.disclaimers.append(str(c["pipeline_summary"]["disclaimer"]))

    label = "Weekly Pipeline Risk Digest" if digest_mode else "Deal Risk Assessment"
    generated = _s(digest.get("generated_at"), now.strftime("%Y-%m-%d %H:%M UTC"))
    parts: list[Html] = [hero(label, scope, _subtitle(now, synthetic, f"Run {generated}" if digest_mode else ""),
                              _status_pills(synthetic), "PL")]

    parts.append(metrics([
        ("Active deals", total_deals if _isnum(total_deals) else len(views)),
        ("Pipeline value" if digest_mode else "CRM value in scope",
         _money(total_value) if _isnum(total_value) else _money(sum(v["value"] or 0 for v in views))),
        ("Flagged (Medium/High)" if digest_mode else "Deals assessed", flagged), ("High risk", high)]))

    key: list[str] = []
    if views:
        t = views[0]
        key.append(f"Highest priority: {t['title']} ({t['rating']}" +
                   (f", score {t['score']}" if t["score"] is not None else "") + ").")
    else:
        key.append("No deals were flagged in this review.")
    if _isnum(total_deals):
        key.append(f"{flagged} of {total_deals} active deal(s) are flagged Medium or High risk.")
    if factors and isinstance(factors[0], dict):
        key.append(f"Most common factor: {_s(factors[0].get('factor'))} ({_s(factors[0].get('count'), '?')} deal(s)).")
    parts.append(_exec_summary_card(c.get("executive_summary"), key))

    parts.append(_risk_chart_card(dist, factors, computed=computed))

    if views:
        top, rest = views[:3], views[3:]
        inner = [callout(HEURISTIC_NOTE), Html('<div class="stack" style="margin-top:12px">'
                                                f'{jn(_deal_card(v, expand=True) for v in top)}</div>')]
        if rest:
            inner.append(Html('<div style="height:10px"></div>'))
            inner.append(disclosure("Other flagged deals", Html(
                f'<div class="stack">{jn(_deal_card(v, expand=False) for v in rest)}</div>'), count=len(rest)))
        parts.append(card("Top at-risk opportunities", jn(inner), sub="Highest risk first", count=len(views)))
    else:
        parts.append(card("Top at-risk opportunities", callout("No deals met the flagging threshold.")))

    prios = [f for f in factors[:3] if isinstance(f, dict) and _txt(f, "factor")]
    if prios:
        items = [Html(f"Address <strong>{e(_txt(f, 'factor'))}</strong>"
                      + (f" ({e(f.get('count'))} deal{'s' if f.get('count') != 1 else ''})" if f.get("count") else ""))
                 for f in prios]
        parts.append(card("Key seller priorities", ul(items, ordered=True), sub="Maximum three"))

    detail: list[Html] = []
    ufc = _d(summary.get("unknown_factor_counts"))
    if ufc:
        detail.append(disclosure("Data gaps: CRM fields unknown", jn([
            callout("Missing CRM fields are not scored as risk. Confirming them sharpens the ratings."),
            table(["CRM field", "Deals with this field unknown"], [[_readable(k), v] for k, v in ufc.items()])]),
            count=len(ufc)))
    nf = [x for x in _l(digest.get("not_flagged_opportunity_ids")) if isinstance(x, str)]
    if nf:
        detail.append(disclosure("Not flagged", Html(f'<p class="mono">{e(", ".join(nf[:LIST_CAP]))}</p>'),
                                 count=len(nf)))
    defs = _d(digest.get("definitions"))
    method = [f"{_readable(k).capitalize()}: {v}" for k, v in defs.items()] or [
        "Each risk factor adds points; High Risk is 5 or more, Medium Risk is 2 to 4.",
        "Scores prioritise attention. They are not statistical or machine-learning predictions.",
        "Missing CRM fields are reported as Unknown and are not treated as negative evidence."]
    run_pairs = [(k, digest.get(f)) for k, f in (("Run ID", "run_id"), ("Trigger", "trigger"),
                 ("Schedule", "schedule_name"), ("Seller scope", "seller_scope"), ("Time zone", "timezone"),
                 ("Generated (local)", "generated_at_local"), ("Review date", "review_date")) if digest.get(f)]
    mbody = [ul(method)]
    if run_pairs:
        mbody.append(kv(run_pairs))
    if digest_mode:
        mbody.append(callout("This digest was stored locally and retrieved on request. No notification was sent."))
    notes = _strs(digest.get("notes"))
    if notes:
        mbody.append(ul(notes))
    detail.append(disclosure("How scores are produced and run details", jn(mbody)))
    parts.append(card("Method and details", jn(detail)))

    parts += [_unknowns_card(r), _sources_card(r, c)]
    return jn(parts, "\n"), scope, label


# ---------------------------------------------------------------------------
# Template 5: Solution Comparison Report
# ---------------------------------------------------------------------------

_FIT_ORDER = ["Supported", "Partially supported", "Not supported", "Unknown / insufficient evidence"]


def _render_comparison(c: dict, now: datetime) -> tuple[str, str, str]:
    name = _s(c.get("account_name"), "Unknown Account")
    synthetic = bool(c.get("synthetic", True))
    r = _R(synthetic)
    cands = [p for p in _l(c.get("candidates")) if isinstance(p, dict)]
    summaries = [p for p in _l(c.get("product_summaries")) if isinstance(p, dict)]
    matrix = [m for m in _l(c.get("side_by_side")) if isinstance(m, dict)]
    unval = [u for u in _l(c.get("requirements_not_yet_validated")) if isinstance(u, dict)]
    direction = _d(c.get("preliminary_solution_direction"))
    notice = _txt(c, "notice")
    names: dict[Any, str] = {p.get("product_id"): _s(p.get("name") or p.get("product_id"), "Product") for p in cands}
    for p in summaries:
        names.setdefault(p.get("product_id"), _s(p.get("name") or p.get("product_id"), "Product"))
    order = [p.get("product_id") for p in cands] or list(names)
    unverified = [p for p in cands if p.get("verification_status") != "verified"]

    r.refs += [(p.get("source_id"), p.get("source_url"), p.get("verified_date")) for p in cands]
    r.add_unknowns(_l(c.get("unknowns")))
    r.unknowns += [_s(u.get("requirement") or u.get("requirement_id"), "") for u in unval]
    if notice:
        r.disclaimers.append(notice)

    key = [f"{len(order)} catalog product(s) compared against {len(matrix)} customer requirement(s)." if matrix
           else f"{len(order)} catalog product(s) listed.",
           "Fit statuses reflect documented catalog text only. Absence of documentation is shown as Unknown, "
           "not as lack of support."]
    if unval:
        key.append(f"{len(unval)} requirement(s) are not yet validated by any candidate.")

    opp_name = _txt(c, "opportunity_name")
    parts: list[Html] = [hero("Solution Comparison Report", name + (f": {opp_name}" if opp_name else ""),
                              _subtitle(now, synthetic, "Illustrative" if synthetic else ""),
                              _status_pills(synthetic), _initials(name))]
    if notice:
        parts.append(callout(notice, "warn"))
    parts.append(metrics([("Products compared", len(order)), ("Requirements", len(matrix)),
                          ("Not yet validated", len(unval)), ("Unverified entries", len(unverified))]))
    parts.append(_exec_summary_card(c.get("executive_summary"), key))

    if direction:
        body = [label_pill("ai"), Html(f' <span class="muted xs">{e(_s(direction.get("label"), "Preliminary: worth exploring, not a recommendation or validated fit"))}</span>')]
        worth = [w for w in _l(direction.get("worth_exploring")) if isinstance(w, (dict, str))]
        if worth:
            items = [Html(f"<strong>{e(_s(w.get('name')))}</strong>: {e(_s(w.get('rationale'), ''))}")
                     if isinstance(w, dict) else w for w in worth]
            body.append(Html('<div style="margin-top:10px"></div>'))
            body.append(ul(items))
        cav = _strs(direction.get("caveats"))
        if cav:
            body.append(Html(f"<h3>Caveats</h3>{ul(cav)}"))
        parts.append(card("Preliminary direction", jn(body)))

    if matrix and order:
        rows = []
        for m in matrix[:LIST_CAP]:
            res = _d(m.get("results"))
            req = f"{_txt(m, 'requirement_id')}: {_txt(m, 'requirement')}".strip(": ") or "Requirement"
            rows.append([req] + [fit_pill(res.get(pid)) for pid in order])
        legend = ", ".join(_strs(c.get("fit_status_legend")) or _FIT_ORDER)
        parts.append(card("Requirement fit matrix", jn([
            table(["Requirement"] + [names.get(pid, _s(pid)) for pid in order], rows, center_from=1),
            Html(f'<p class="muted xs" style="margin-top:8px">Statuses: {e(legend)}. Requirements come from the '
                 "CRM opportunity unless marked seller-provided.</p>")])))

    if summaries or cands:
        base = summaries or cands
        rows = []
        for p in base[:LIST_CAP]:
            sc = _d(p.get("status_counts"))
            if not sc and matrix:  # derive from the fit matrix when counts were not supplied
                pid = p.get("product_id")
                sc = {k: sum(1 for m in matrix if _d(m.get("results")).get(pid) == k) for k in _FIT_ORDER}
            ver = "verified" if p.get("verification_status") == "verified" else "unverified"
            link = _link(p.get("source_url") or _d(p.get("catalog_source")).get("source_url"), "IBM product page") \
                or Html('<span class="muted">Link unavailable</span>')
            rows.append([_s(p.get("name") or p.get("product_id")), *[sc.get(k, "-") for k in _FIT_ORDER],
                         label_pill(ver), link])
        parts.append(card("Products compared", table(
            ["Product", "Supported", "Partial", "Not supported", "Unknown", "Catalog entry", "Official page"],
            rows, center_from=1), sub="Counts of requirement statuses"))

    if summaries:
        det = []
        for p in summaries[:LIST_CAP]:
            src = _d(p.get("catalog_source"))
            verified = p.get("verification_status") == "verified"
            body: list[Html] = [Html(f'<div>{label_pill("verified" if verified else "unverified")} '
                                     f'<span class="muted xs">'
                                     + ("Catalog entry verified" + (f" on {e(src.get('verified_date'))}" if src.get("verified_date") else "")
                                        if verified else "Catalog entry is unverified; treat capabilities as placeholders")
                                     + "</span></div>")]
            st = [f"{_s(s.get('requirement_id'), '')}: {'; '.join(str(x) for x in _l(s.get('documented_capability')))} "
                  f"({_s(s.get('fit_status'), '')})" for s in _l(p.get("strengths")) if isinstance(s, dict)]
            if st:
                body.append(Html(f"<h4>Documented capabilities matched to requirements</h4>{ul(st)}"))
            for key_, head in (("limitations", "Documented limitations"), ("explicit_gaps", "Explicit gaps"),
                               ("conflicts", "Conflicts to resolve"), ("needs_validation", "Needs specialist validation")):
                vals = [t for t in (_item_text(x) for x in _l(p.get(key_))) if t]
                if vals:
                    body.append(Html(f"<h4>{e(head)}</h4>{ul(vals[:LIST_CAP])}"))
            link = _link(p.get("source_url") or src.get("source_url"), "Official IBM product page")
            if link:
                body.append(Html(f'<p class="xs">{link}</p>'))
            det.append(disclosure(_s(p.get("name") or p.get("product_id")), jn(body)))
        parts.append(card("Product detail", jn(det), sub="Catalog text only"))

    if unval:
        rows = [[f"{_txt(u, 'requirement_id')}: {_txt(u, 'requirement')}".strip(": ") or "Requirement",
                 fit_pill(u.get("best_status")), "; ".join(str(x) for x in _l(u.get("reasons"))[:3]) or "-"]
                for u in unval[:LIST_CAP]]
        parts.append(card("Requirements not yet validated", jn([
            callout("No candidate has full documented evidence for these. Validate with a specialist.", "warn"),
            Html('<div style="height:10px"></div>'), table(["Requirement", "Best status", "Why"], rows)]),
            count=len(unval)))

    qs = [q for q in _l(c.get("recommended_discovery_questions")) if isinstance(q, dict)]
    if qs:
        items = [f"{_s(q.get('question'))}" + (f" ({q['related_requirement_id']})" if q.get("related_requirement_id") else "")
                 for q in qs[:30]]
        parts.append(card("Recommended discovery questions", jn([label_pill("ai"),
                          Html(' <span class="muted xs">Questions that would close the gaps above.</span>'),
                          Html('<div style="margin-top:8px"></div>'), ul(items, ordered=True)]), count=len(qs)))

    parts += [_unknowns_card(r), _sources_card(r, c)]
    return jn(parts, "\n"), name, "Solution Comparison Report"


# ---------------------------------------------------------------------------
# Template 6: Post-Meeting Follow-Up Plan
# ---------------------------------------------------------------------------

_BAD_OWNERS = {"that", "this", "it", "we", "they", "there", "which", "who", "i", "you"}


def _meeting_items(items: Any) -> list[tuple[str, str]]:
    out = []
    for i in _l(items):
        if not isinstance(i, dict):
            continue
        t = _txt(i, "text", "source_sentence")
        if t and not _is_seller_question(t):
            out.append((t, (_txt(i, "confidence") or "unknown").capitalize()))
    return out


def _render_followup(c: dict, now: datetime) -> tuple[str, str, str]:
    name = _s(c.get("account_name"), "Unknown Account")
    synthetic = bool(c.get("synthetic", True))
    r = _R(synthetic)
    m = _d(c.get("meeting_analysis"))
    props_raw = c.get("crm_proposals")
    props = _d(props_raw)
    proposals = _l(props.get("proposed_updates")) if props else _l(props_raw)
    label = _txt(c, "meeting_label")

    actions: list[dict] = []
    seen: set = set()

    def add_action(text: str, owner: str, deadline: str, basis: str) -> None:
        if text and text not in seen:
            seen.add(text)
            owner = "" if owner.lower() in _BAD_OWNERS else owner
            actions.append({"action": text, "owner": owner, "deadline": deadline, "basis": basis})

    for a in _l(c.get("actions")):
        if isinstance(a, dict):
            add_action(_txt(a, "action", "text"), _txt(a, "owner"), _txt(a, "deadline"),
                       _txt(a, "basis", "confidence") or "AI-generated")
        elif isinstance(a, str):
            add_action(a.strip(), "", "", "AI-generated")
    for a in _l(m.get("action_items")):
        if isinstance(a, dict):
            conf = _txt(a, "confidence")
            add_action(_txt(a, "text", "action"), _txt(a, "owner"), _txt(a, "deadline"),
                       conf.capitalize() if conf else "AI-generated")

    reqs = _meeting_items(m.get("requirements"))
    challenges = _meeting_items(m.get("challenges"))
    objections = _meeting_items(m.get("objections"))
    bt = _d(m.get("budget_and_timeline"))
    cust_qs = [t for t in (_txt(q, "text") for q in _l(m.get("open_questions")) if isinstance(q, dict))
               if t.endswith("?") and not t.startswith("Seller:")]

    r.add_unknowns(_l(c.get("unknowns")))
    if m and bt.get("budget_confirmed") is not True:
        r.unknowns.append("Budget has not been confirmed in the meeting notes.")
    r.unknowns += cust_qs
    r.add_unknowns(_l(props.get("potentially_outdated")))
    for t in (m.get("disclaimer"), props.get("disclaimer")):
        if isinstance(t, str) and t.strip():
            r.disclaimers.append(t.strip())
    injected = bool(_l(m.get("injection_warnings")))
    if injected:
        r.disclaimers.append("Some meeting text looked like instructions and was ignored as data.")

    unowned = sum(1 for a in actions if not a["owner"])
    key = [f"Follow-up for {name}" + (f" ({label})." if label else ".")]
    key.append(f"{len(actions)} follow-up action(s) identified; {unowned} without an owner.")
    if proposals:
        key.append(f"{len(proposals)} CRM update(s) proposed for the seller to approve; none have been applied.")

    parts: list[Html] = [hero("Post-Meeting Follow-Up Plan", name + (f": {label}" if label else ""),
                              _subtitle(now, synthetic, "Not sent"), _status_pills(synthetic, pill("Not sent", "neutral")),
                              _initials(name))]
    if injected:
        parts.append(callout("Instruction-like text was found in the meeting notes and was ignored; it was "
                             "treated as data only.", "warn"))
    parts.append(metrics([("Follow-up actions", len(actions)), ("CRM updates proposed", len(proposals)),
                          ("Requirements heard", len(reqs)), ("Open unknowns", len(set(r.unknowns)))]))
    parts.append(_exec_summary_card(c.get("executive_summary"), key))

    def heard(items: list[tuple[str, str]]) -> Html:
        rows = "".join(str(row("E" if conf == "Explicit" else "I" if conf == "Inferred" else "?", t,
                               f"Basis: {conf}")) for t, conf in items[:LIST_CAP])
        return Html(f'<div class="rows">{rows}</div>')

    if m:
        heard_parts: list[Html] = [label_pill("ai"), Html(
            ' <span class="muted xs">Extracted from meeting notes by pattern matching. Explicit means stated in '
            "the notes; Inferred means suggested by context. Verify before relying on either.</span>")]
        for head, items in (("Requirements", reqs), ("Challenges", challenges), ("Objections and concerns", objections)):
            if items:
                heard_parts.append(Html(f"<h3>{e(head)}</h3>{heard(items)}"))
        sh = [{"role": _txt(s, "role_hint"), "notes": _txt(s, "source_sentence")}
              for s in _l(m.get("stakeholders"))[:20] if isinstance(s, dict)]
        if sh:
            heard_parts.append(Html(f"<h3>Stakeholders mentioned</h3>{_stakeholder_table(sh)}"))
        heard_parts.append(Html("<h3>Budget and timeline</h3>"))
        heard_parts.append(kv([
            ("Budget confirmed", "Yes" if bt.get("budget_confirmed") is True else "Not confirmed"),
            ("Budget mentions", "; ".join(str(x) for x in _l(bt.get("budget_mentions"))[:4]) or "None found"),
            ("Timeline mentions", "; ".join(str(x) for x in _l(bt.get("timeline_mentions"))[:4]) or "None found"),
            ("Dates found", ", ".join(str(x) for x in _l(bt.get("dates_found"))) or "None found")]))
        parts.append(card("What we heard", jn(heard_parts)))
    else:
        parts.append(card("What we heard", callout("Meeting analysis was not provided.", "warn")))

    parts.append(card("Follow-up actions", _action_table(actions) if actions
                      else callout("Follow-up actions were not provided.", "warn"), count=len(actions)))

    if proposals and _crm_updates_table(proposals):
        body = [_crm_updates_table(proposals)]
        if props.get("preservation_notice"):
            body.append(Html(f'<p class="muted xs" style="margin-top:8px">{e(props["preservation_notice"])}</p>'))
        parts.append(card("Proposed CRM updates (not applied)", jn(body), count=len(proposals)))

    new_risks = [str(x) for x in _l(props.get("new_risks")) if isinstance(x, str) and not _is_seller_question(x)]
    if new_risks:
        parts.append(card("New risks raised", ul(new_risks[:8]), count=len(new_risks)))
    if cust_qs:
        parts.append(card("Open questions from the customer", ul(cust_qs[:LIST_CAP]), count=len(cust_qs)))

    # Follow-up email draft (collapsed): placeholders only, never invented names/dates
    email = [f"Subject: Follow-up from our meeting - {name}", "", "Hi [Contact name],", "",
             "Thank you for taking the time to connect on [date].", ""]
    if reqs:
        email += ["What we heard:"] + [f"- {t}" for t, _ in reqs[:3]] + [""]
    email += ["Proposed next steps:"]
    email += [f"{i}. {a['action']}" for i, a in enumerate(actions[:2], 1)]
    email += ["", "Please let us know if you have any questions.", "", "[Your name]"]
    parts.append(card("Follow-up email draft", jn([
        callout("DRAFT - for seller review. Not sent.", "warn"), Html('<div style="height:10px"></div>'),
        disclosure("Show draft text", jn([Html(f'<div class="email">{e(chr(10).join(email))}</div>'),
                                          Html('<p class="muted xs">Seller checklist: confirm names and facts, '
                                               "remove anything unsuitable before sending.</p>")]))])))

    parts += [_unknowns_card(r), _sources_card(r, c)]
    return jn(parts, "\n"), name, "Post-Meeting Follow-Up Plan"


# ---------------------------------------------------------------------------
# Registry and page shell
# ---------------------------------------------------------------------------

_RENDERERS: dict[str, Callable[[dict, datetime], tuple[str, str, str]]] = {
    "discovery_brief": _render_discovery,
    "account_summary": _render_account_summary,
    "action_plan": _render_action_plan,
    "deal_risk_assessment": lambda c, n: _render_pipeline(c, n, digest_mode=False),
    "solution_comparison": _render_comparison,
    "followup_plan": _render_followup,
    "pipeline_digest": lambda c, n: _render_pipeline(c, n, digest_mode=True),
}


def _page(body: str, label: str, subject: str, now: datetime) -> str:
    title = f"{label} - {subject}"
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f'<meta http-equiv="Content-Security-Policy" content="{e(_CSP)}">\n'
        '<meta name="referrer" content="no-referrer">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light dark">\n'
        f"<title>{e(title)}</title>\n<style>{_CSS}</style>\n</head>\n<body>\n"
        '<input type="radio" name="theme" id="th-auto" class="th" checked aria-label="Theme: automatic">'
        '<input type="radio" name="theme" id="th-light" class="th" aria-label="Theme: light">'
        '<input type="radio" name="theme" id="th-dark" class="th" aria-label="Theme: dark">\n'
        '<header class="topnav"><nav class="crumbs" aria-label="Breadcrumb">'
        f"<span>SalesFlow</span><i>/</i><span>{e(label)}</span><i>/</i><b>{e(subject)}</b></nav>"
        '<div class="seg" role="group" aria-label="Theme">'
        '<label for="th-auto">Auto</label><label for="th-light">Light</label><label for="th-dark">Dark</label>'
        "</div></header>\n"
        f"<main>\n{body}\n</main>\n"
        f'<footer class="foot">SalesFlow report \u00b7 generated {e(now.strftime("%Y-%m-%d %H:%M UTC"))} \u00b7 '
        "draft for seller review \u00b7 self-contained file with no external resources.</footer>\n"
        "</body>\n</html>\n")


class HtmlReportError(MdReportError):
    """Safe-to-show error from HTML report generation (subclass so callers can share handling)."""


def render_html(report_type: str, content: dict, now: Optional[datetime] = None) -> tuple[str, str]:
    """Render a report to an HTML string. Returns (html_document, subject)."""
    if report_type not in REPORT_TYPES:
        raise HtmlReportError("invalid_input", f"report_type must be one of: {', '.join(REPORT_TYPES)}.")
    if not isinstance(content, dict):
        raise HtmlReportError("invalid_input", "content must be a JSON object.")
    now = now or datetime.now(tz=timezone.utc)
    body, subject, label = _RENDERERS[report_type](content, now)
    return _page(body, label, subject, now), subject


def save_html_report(report_type: str, content: dict, *, now: Optional[datetime] = None,
                     reports_dir: Optional[Path] = None) -> dict:
    """Render and save a standalone HTML report. Returns file facts dict.

    Raises HtmlReportError (an MdReportError) for invalid input or I/O failures.
    """
    now = now or datetime.now(tz=timezone.utc)
    try:
        document, subject = render_html(report_type, content, now)
    except HtmlReportError:
        raise
    except Exception as exc:
        log.error("HTML rendering failed: %s", type(exc).__name__, exc_info=True)
        raise HtmlReportError("generation_failed", "HTML rendering failed. No file was written.")

    try:
        dest = _write_report(document, report_type, subject, now, reports_dir, ext=".html")
    except (ValueError, OSError) as exc:
        log.error("HTML file write failed: %s", type(exc).__name__)
        raise HtmlReportError("generation_failed", "Could not write the report file.")

    if not dest.exists():
        raise HtmlReportError("generation_failed", "Report generation reported success but the file was not found.")
    return {
        "file_path": str(dest),
        "file_name": dest.name,
        "size_bytes": dest.stat().st_size,
        "report_type": report_type,
        "report_label": REPORT_TYPES[report_type],
        "subject": subject,
        "format": "html",
    }
