"""Evidence-based solution comparison for SalesFlow Feature 3.

Pure comparison logic - no MCP server dependencies, no I/O. The server wrapper
loads CRM and catalog records and passes them in.

Design principles:
- Deterministic. Every fit status is derived from catalog text or explicit
  structured attributes by fixed rules; no capability is ever inferred.
- Absence of documentation is "Unknown / insufficient evidence", never
  "Not supported".
- "Supported" requires verified catalog evidence that covers the requirement
  and every measurable qualifier in it (numbers, standards, named frameworks).
- "Not supported" is only produced from an explicit structured attribute
  (status "not_supported" with an evidence string) on a verified entry.
  Free-text limitations that sound negative are flagged for review instead.
- Unverified / synthetic entries can never produce Supported, Partially
  supported or Not supported. They are capped at Unknown and flagged.
- Conflicting catalog information is surfaced, never resolved silently.
- Nothing here produces pricing, guaranteed recovery times, benchmarks or
  competitive claims.
"""

from __future__ import annotations

import re
from typing import Any

from .meeting_analysis import _detect_injection

# ------------------------------------------------------------------ constants

FIT_SUPPORTED = "Supported"
FIT_PARTIAL = "Partially supported"
FIT_NOT_SUPPORTED = "Not supported"
FIT_UNKNOWN = "Unknown / insufficient evidence"
FIT_STATUSES = (FIT_SUPPORTED, FIT_PARTIAL, FIT_NOT_SUPPORTED, FIT_UNKNOWN)

MAX_REQUIREMENTS = 25
MAX_REQUIREMENT_LEN = 300
MAX_CANDIDATES = 6
DEFAULT_CANDIDATES = 4
MAX_FOCUS_AREAS = 10

PRIORITIES = ("must", "should", "nice_to_have")

GUARDRAIL_NOTICE = (
    "This comparison uses only documented catalog text. It contains no pricing, "
    "no guaranteed recovery times, no performance benchmarks and no competitive "
    "claims. It is a preliminary aid for seller and solutions-engineer review, "
    "not a validated configuration or quote."
)
ILLUSTRATIVE_NOTICE = (
    "ILLUSTRATIVE ONLY: every candidate is a synthetic or unverified placeholder "
    "entry. Do not present any result as a real product capability."
)


class ComparisonInputError(ValueError):
    """Invalid caller input. `code` is 'invalid_input' or 'not_found'."""

    def __init__(self, code: str, message: str, suggestions: list[str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggestions = suggestions or []


# ------------------------------------------------------------------ requirement taxonomy
# Order matters: the first category whose `req` pattern matches a requirement
# is its category. `cap` matches documented capability text; `lim` adds extra
# terms that make a limitation relevant to the category.

_I = re.IGNORECASE

CATEGORIES: dict[str, dict[str, Any]] = {
    "encryption_at_rest": {
        "label": "Encryption at rest",
        "kind": "technical",
        "req": re.compile(r"encrypt|\baes\b|aes-?\d|at rest|\bfips\b", _I),
        "cap": re.compile(r"encrypt", _I),
        "lim": re.compile(r"key manage", _I),
        "questions": [
            "Which encryption standard and key-management approach does the customer require?",
            "Which compliance framework must the encryption support evidence for, and who owns that evidence?",
        ],
    },
    "compliance_audit": {
        "label": "Compliance and audit trails",
        "kind": "functional",
        "req": re.compile(r"audit|complian|\bhipaa\b|\bpci\b|\bgdpr\b|regulat|residency", _I),
        "cap": re.compile(r"audit|complian|hipaa|pci|gdpr|regulat", _I),
        "lim": re.compile(r"framework|regulation", _I),
        "questions": [
            "Which regulations or frameworks apply, and what evidence must be produced for auditors?",
            "Which data sources and systems are in scope for audit and monitoring?",
        ],
    },
    "cyber_resilience": {
        "label": "Cyber resilience",
        "kind": "technical",
        "req": re.compile(r"ransomware|cyber|immutab|air-?gap|malware", _I),
        "cap": re.compile(r"ransomware|immutable|air-gapped|cyber|safeguarded", _I),
        "lim": re.compile(r"runbook|retention", _I),
        "questions": [
            "What immutability, retention and recovery-testing expectations apply to protected copies?",
        ],
    },
    "high_availability": {
        "label": "High availability",
        "kind": "technical",
        "req": re.compile(
            r"high availab|\bha\b|single point|availab|redundan|failover|active-?\s?active|uptime", _I
        ),
        "cap": re.compile(
            r"high availab|single point of failure|hyperswap|active-active|redundan|failover|\bha\b", _I
        ),
        "lim": re.compile(r"site|topology", _I),
        "questions": [
            "Which systems need continuous availability, and is it needed within one site, across two sites, or both?",
            "What site topology and inter-site connectivity exist today?",
        ],
    },
    "disaster_recovery": {
        "label": "Disaster recovery",
        "kind": "technical",
        "req": re.compile(r"disaster|\bdr\b|recover|\brto\b|\brpo\b|replicat", _I),
        "cap": re.compile(
            r"disaster recovery|(?<!without full )replicat|safeguarded copy|point-in-time recovery|off-site", _I
        ),
        "lim": re.compile(r"bandwidth|runbook|recovery|latency", _I),
        "questions": [
            "What recovery time and recovery point objectives apply to each workload tier?",
            "Where is the recovery site, and what inter-site bandwidth and latency are available?",
            "How often is disaster recovery tested today, and what happened in the last test?",
        ],
    },
    "backup_retention": {
        "label": "Backup and retention",
        "kind": "functional",
        "req": re.compile(r"backup|retention|archiv", _I),
        "cap": re.compile(r"backup|retention|archiv|tape", _I),
        "lim": re.compile(r"policy", _I),
        "questions": [
            "What retention periods and backup windows apply to each workload class?",
            "Which hypervisors, databases and operating systems must be protected?",
        ],
    },
    "migration_replacement": {
        "label": "Replacement and migration of existing storage",
        "kind": "functional",
        "req": re.compile(r"replac|migrat|end[\s-]of[\s-](?:support|life)|\baging\b|\bageing\b|refresh|moderni[sz]", _I),
        "cap": re.compile(r"migrat|non-disruptive|virtuali[sz]ation of third-party", _I),
        "lim": re.compile(r"replacement|replace|interoperab|compatib", _I),
        "partial_only": "The catalog documents data migration, not replacement scope, hardware support status or cutover timelines.",
        "questions": [
            "What make, model and age are the arrays being replaced, and which hosts, adapters and switches attach to them?",
            "What cutover window and tolerance for migration disruption apply to each clinical or business system?",
        ],
    },
    "capacity_scalability": {
        "label": "Capacity and scalability",
        "kind": "technical",
        "req": re.compile(r"capacity|scal|growth|petabyte|terabyte|imaging|\bpb\b|\btb\b", _I),
        "cap": re.compile(r"petabyte|scalab|scale|capacity", _I),
        "lim": re.compile(r"sizing|raw", _I),
        "needs_target": True,
        "questions": [
            "What is the current usable capacity and expected growth over the next three to five years?",
            "What are the data types and access patterns of the largest consumers (for example imaging)?",
        ],
    },
    "centralized_management": {
        "label": "Centralised management",
        "kind": "functional",
        "req": re.compile(r"central|unified|single pane|\bmanage|operational|simplif", _I),
        "cap": re.compile(
            r"unified (?:management|pool)|consistent management|centrali[sz]ed|single (?:pane|management)|management interface",
            _I,
        ),
        "lim": re.compile(r"expertise|specialist", _I),
        "questions": [
            "Who will administer the platform day to day, and which management tools do they use today?",
            "Which existing arrays or platforms must be managed from the same interface?",
        ],
    },
    "performance": {
        "label": "Performance",
        "kind": "technical",
        "req": re.compile(r"performance|latency|\biops\b|throughput|\bnvme\b|low-latency", _I),
        "cap": re.compile(r"latency|throughput|iops|sub-millisecond", _I),
        "lim": re.compile(r"proof of concept", _I),
        "needs_target": True,
        "questions": [
            "What IOPS, latency and throughput do the key workloads require, measured how?",
        ],
    },
}

# Negation markers: a limitation containing one of these AND matching a
# category is treated as an explicit statement that the area is not covered.
_NEGATION = re.compile(
    r"\b(?:not|cannot|can't|never|unable|unsupported|doesn't|does not|isn't)\b", _I
)

# Measurable qualifiers inside a requirement. Timeline units (months, years)
# are deliberately excluded: they are customer constraints, not product attributes.
_NUM = r"(?:\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten|twelve|fifteen|twenty|thirty|sixty)"
_UNIT = r"(?:hours?|hrs?|minutes?|mins?|seconds?|secs?|milliseconds?|ms|iops|gb|tb|pb|nines|percent)"
_QUALIFIER_PATTERNS = [
    re.compile(rf"\b{_NUM}[\s-]?{_UNIT}\b", _I),
    re.compile(rf"\b{_NUM}\s?%", _I),
    re.compile(r"\bnear[\s-]?zero\b", _I),
    re.compile(r"\bsub-[a-z]+(?:-[a-z]+)?\b", _I),
    re.compile(r"\baes[\s-]?\d{3}\b", _I),
    re.compile(r"\b(?:hipaa|pci[\s-]?dss|gdpr|sox|fedramp|iso[\s-]?27001)\b", _I),
    re.compile(r"\bsingle point of failure\b", _I),
    re.compile(r"\bactive[\s-]active\b", _I),
    re.compile(r"\bnvme\b", _I),
]
_QUANTITY = re.compile(rf"\b{_NUM}[\s-]?(?:gb|tb|pb|iops|ms|milliseconds?|percent)\b|\bsub-millisecond\b", _I)

_CONSTRAINT_CUES = re.compile(
    r"end[\s-]of[\s-]support|within \d+ (?:months?|years?)|\bq[1-4] 20\d\d\b|deadline|capital spend|"
    r"approval|\blimited\b|small (?:it )?team|turnover",
    _I,
)
_BUSINESS_CUES = re.compile(r"\b(?:reduce|lower|minimi[sz]e|improve|burden)\b", _I)

_STOP = {
    "with", "that", "from", "this", "have", "will", "into", "than", "such", "over", "across",
    "storage", "system", "systems", "data", "support", "supports", "using", "based",
}

_ID_RE = re.compile(r"^[a-z0-9_]{1,64}$")


# ------------------------------------------------------------------ small helpers


def _norm(text: str) -> str:
    return re.sub(r"[\s\-_/]+", " ", text.lower()).strip()


def _stem_set(text: str) -> set[str]:
    return {t[:6] for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 4 and t not in _STOP}


def _trunc(text: str, n: int = 200) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n].rstrip() + "…"


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [" ".join(v.split()) for v in value if isinstance(v, str) and v.strip()]


def categorize(text: str) -> str | None:
    """Return the first matching category id for a requirement text, else None."""
    for cid, cat in CATEGORIES.items():
        if cat["req"].search(text):
            return cid
    return None


def extract_qualifiers(text: str) -> list[str]:
    """Measurable qualifiers in a requirement (deduplicated; contained ones dropped)."""
    found: list[str] = []
    for pat in _QUALIFIER_PATTERNS:
        for m in pat.finditer(text):
            q = m.group(0).strip()
            if q and q.lower() not in (f.lower() for f in found):
                found.append(q)
    return [q for q in found if not any(q != o and _norm(q) in _norm(o) for o in found)]


def is_verified(product: dict) -> bool:
    return bool(product.get("source_url")) and bool(product.get("verified_date")) and not bool(
        product.get("synthetic", True)
    )


def _source(product: dict) -> dict:
    return {
        "source_id": product.get("source_id"),
        "source_url": product.get("source_url"),
        "verified_date": product.get("verified_date"),
    }


# ------------------------------------------------------------------ requirements


def _make_item(
    idx: int,
    text: str,
    source: str,
    source_id: str | None,
    category: str | None = None,
    priority: str | None = None,
    target: str | None = None,
) -> dict:
    cid = category or categorize(text)
    full = f"{text} {target}" if target else text
    qualifiers = extract_qualifiers(full)
    cat = CATEGORIES.get(cid) if cid else None
    questions = list(cat["questions"]) if cat else [
        f"Clarify in measurable terms what '{_trunc(text, 80)}' requires."
    ]
    questions += [
        f"Is '{q}' a firm customer target? If so, ask a product specialist to confirm it against product documentation."
        for q in qualifiers
    ]
    return {
        "requirement_id": f"REQ-{idx}",
        "text": text,
        "category": cid,
        "category_label": cat["label"] if cat else "Unmapped",
        "type": cat["kind"] if cat else "unmapped",
        "priority": priority,
        "qualifiers": qualifiers,
        "target": target,
        "source": source,
        "source_id": source_id,
        "tag": "Seller-provided (unverified)" if source == "seller_provided" else "Verified (CRM)",
        "validation_questions": questions,
    }


def normalize_requirements(raw: Any) -> list[dict]:
    """Validate caller-supplied requirements (strings or structured dicts)."""
    if not isinstance(raw, list) or not raw:
        raise ComparisonInputError("invalid_input", "requirements must be a non-empty list.")
    if len(raw) > MAX_REQUIREMENTS:
        raise ComparisonInputError("invalid_input", f"requirements must contain at most {MAX_REQUIREMENTS} items.")
    items: list[dict] = []
    for i, entry in enumerate(raw, start=1):
        if isinstance(entry, str):
            entry = {"requirement": entry}
        if not isinstance(entry, dict):
            raise ComparisonInputError("invalid_input", f"requirements[{i}] must be a string or an object.")
        text = entry.get("requirement")
        if not isinstance(text, str) or not " ".join(text.split()):
            raise ComparisonInputError("invalid_input", f"requirements[{i}].requirement must be a non-empty string.")
        text = " ".join(text.split())
        if len(text) > MAX_REQUIREMENT_LEN:
            raise ComparisonInputError(
                "invalid_input", f"requirements[{i}].requirement must be at most {MAX_REQUIREMENT_LEN} characters."
            )
        category = entry.get("category")
        if category is not None:
            key = _norm(str(category)).replace(" ", "_")
            if key not in CATEGORIES:
                raise ComparisonInputError(
                    "invalid_input", f"requirements[{i}].category is not recognised.", sorted(CATEGORIES)
                )
            category = key
        priority = entry.get("priority")
        if priority is not None:
            pkey = _norm(str(priority)).replace(" ", "_")
            if pkey not in PRIORITIES:
                raise ComparisonInputError(
                    "invalid_input", f"requirements[{i}].priority must be one of: {', '.join(PRIORITIES)}.", list(PRIORITIES)
                )
            priority = pkey
        target = entry.get("target")
        if target is not None:
            if not isinstance(target, str) or len(target) > MAX_REQUIREMENT_LEN:
                raise ComparisonInputError("invalid_input", f"requirements[{i}].target must be a short string.")
            target = " ".join(target.split()) or None
        items.append(_make_item(i, text, "seller_provided", None, category, priority, target))
    return items


def resolve_focus_areas(raw: Any) -> set[str]:
    if raw is None:
        return set()
    if not isinstance(raw, list) or len(raw) > MAX_FOCUS_AREAS:
        raise ComparisonInputError("invalid_input", f"focus_areas must be a list of at most {MAX_FOCUS_AREAS} items.")
    out: set[str] = set()
    for f in raw:
        if not isinstance(f, str):
            raise ComparisonInputError("invalid_input", "focus_areas entries must be strings.")
        key = _norm(f).replace(" ", "_")
        aliases = {"ha": "high_availability", "dr": "disaster_recovery", "capacity": "capacity_scalability",
                   "encryption": "encryption_at_rest", "management": "centralized_management",
                   "migration": "migration_replacement", "compliance": "compliance_audit"}
        key = aliases.get(key, key)
        if key not in CATEGORIES:
            raise ComparisonInputError(
                "invalid_input", "focus_areas contains an unrecognised area.", sorted(CATEGORIES)
            )
        out.add(key)
    return out


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n+", text) if s.strip()]


def extract_requirements_from_crm(opportunity: dict, account: dict | None) -> dict:
    """Derive requirement items and the wider requirements overview from CRM records."""
    opp_sid = opportunity.get("source_id")
    acct_sid = (account or {}).get("source_id")
    items: list[dict] = []

    for text in _str_list(opportunity.get("requirements")):
        items.append(_make_item(len(items) + 1, text, "crm_opportunity", opp_sid))
    covered = {i["category"] for i in items if i["category"]}

    business: list[dict] = []
    for ch in _str_list((account or {}).get("challenges")):
        cid = categorize(ch)
        if cid and cid not in covered:
            item = _make_item(len(items) + 1, ch, "account_challenge", acct_sid, cid)
            item["tag"] = "Verified (CRM) - inferred requirement from account challenge"
            items.append(item)
            covered.add(cid)
        elif not cid and not _CONSTRAINT_CUES.search(ch):
            business.append({"text": ch, "source": "account_challenge", "source_id": acct_sid})
    for i in items:
        if _BUSINESS_CUES.search(i["text"]):
            business.append({"text": i["text"], "source": i["source"], "source_id": i["source_id"]})

    constraints: list[dict] = []
    seen: set[str] = set()
    pools = (
        [(t, "account_challenge", acct_sid) for t in _str_list((account or {}).get("challenges"))]
        + [(t, "crm_note", opp_sid) for t in _str_list(opportunity.get("notes"))]
        + [(t, "crm_post_meeting_note", opp_sid) for t in _str_list(opportunity.get("post_meeting_notes"))]
    )
    for text, src, sid in pools:
        for sent in _sentences(text):
            if _CONSTRAINT_CUES.search(sent) and sent.lower() not in seen:
                seen.add(sent.lower())
                constraints.append({"text": _trunc(sent), "source": src, "source_id": sid})
    constraints = constraints[:10]

    unknowns: list[dict] = []
    for u in _str_list(opportunity.get("unknowns")) + _str_list((account or {}).get("unknowns")):
        cid = categorize(u)
        unknowns.append({"item": u, "affects_category": cid})

    return {"items": items, "business_priorities": business, "constraints": constraints, "unknowns": unknowns}


def build_requirements_overview(
    items: list[dict],
    business: list[dict],
    constraints: list[dict],
    unknowns: list[dict],
) -> dict:
    questions: list[str] = []
    for i in items:
        for q in i["validation_questions"]:
            if q not in questions:
                questions.append(q)
    return {
        "functional": [i for i in items if i["type"] == "functional"],
        "technical": [i for i in items if i["type"] == "technical"],
        "unmapped": [i for i in items if i["type"] == "unmapped"],
        "business_priorities": business,
        "constraints": constraints,
        "unknown_requirements": unknowns,
        "validation_questions": questions,
    }


# ------------------------------------------------------------------ products


def prepare_products(records: list[dict]) -> list[dict]:
    """Group catalog records by product_id; flag differing duplicates as conflicting."""
    grouped: dict[str, list[dict]] = {}
    for r in records:
        grouped.setdefault(str(r.get("product_id")), []).append(r)
    prepared: list[dict] = []
    for pid, recs in grouped.items():
        first = recs[0]
        conflict = None
        for other in recs[1:]:
            if any(first.get(k) != other.get(k) for k in ("name", "capabilities", "limitations", "structured_attributes")):
                conflict = (
                    f"The catalog contains {len(recs)} entries for {pid} with differing content; "
                    "none can be treated as authoritative until the catalog owner reconciles them."
                )
                break
        prepared.append({"record": first, "catalog_conflict": conflict})
    return sorted(prepared, key=lambda p: str(p["record"].get("product_id")))


def _collect_evidence(product: dict, cid: str) -> dict:
    """Gather positive evidence, explicit negations and relevant limitations for one category."""
    cat = CATEGORIES[cid]
    pos: list[dict] = []
    neg: list[dict] = []
    flags: list[str] = []  # free-text limitations that may exclude the area; need human review

    attrs = product.get("structured_attributes")
    attr = attrs.get(cid) if isinstance(attrs, dict) else None
    if isinstance(attr, dict):
        status = str(attr.get("status", "")).strip().lower()
        evidence = " ".join(str(attr.get("evidence") or "").split())
        # A structured attribute without an evidence string is not documentation.
        if evidence and status == "supported":
            pos.append({"text": evidence, "kind": "structured", "strength": "strong"})
        elif evidence and status == "partial":
            pos.append({"text": evidence, "kind": "structured", "strength": "partial"})
        elif evidence and status == "not_supported":
            neg.append({"text": evidence, "kind": "structured"})

    for cap in _str_list(product.get("capabilities")):
        if cat["cap"].search(cap):
            pos.append({"text": cap, "kind": "capability", "strength": "strong"})
    summary = product.get("summary")
    if isinstance(summary, str) and cat["cap"].search(summary) and not any(p["strength"] == "strong" for p in pos):
        pos.append({"text": " ".join(summary.split()), "kind": "summary", "strength": "weak"})

    relevant_limits: list[str] = []
    for lim in _str_list(product.get("limitations")):
        if cat["cap"].search(lim) or cat["lim"].search(lim):
            relevant_limits.append(lim)
            if _NEGATION.search(lim):
                flags.append(lim)
    relevant_validation = [
        v for v in _str_list(product.get("needs_validation")) if cat["cap"].search(v) or cat["lim"].search(v)
    ]
    return {"pos": pos, "neg": neg, "flags": flags, "limits": relevant_limits, "validation": relevant_validation}


def _row(item: dict, prep: dict, **fields: Any) -> dict:
    p = prep["record"]
    row = {
        "requirement_id": item["requirement_id"],
        "requirement": item["text"],
        "category": item["category"],
        "product_id": p.get("product_id"),
        "product_name": p.get("name"),
        "documented_capability": [],
        "evidence_source": _source(p),
        "verification_status": "verified" if is_verified(p) else "synthetic_unverified",
        "fit_status": FIT_UNKNOWN,
        "missing_information": [],
        "limitations": [],
        "conflict": False,
        "conflict_detail": None,
        "possibly_related_text": [],
        "rationale": "",
    }
    row.update(fields)
    return row


def assess(item: dict, prep: dict) -> dict:
    """Deterministically assess one requirement against one product."""
    p = prep["record"]
    verified = is_verified(p)
    cid = item["category"]

    if prep["catalog_conflict"]:
        return _row(
            item, prep, conflict=True, conflict_detail=prep["catalog_conflict"],
            missing_information=["Reconcile conflicting catalog entries before relying on this product."],
            rationale="Conflicting catalog entries; no fit can be asserted.",
        )

    if cid is None:
        related: list[str] = []
        req_stems = _stem_set(item["text"])
        for cap in _str_list(p.get("capabilities")):
            if len(req_stems & _stem_set(cap)) >= 2:
                related.append(cap)
        return _row(
            item, prep, possibly_related_text=related,
            missing_information=["Requirement is not mapped to a comparable capability area; manual review needed."],
            rationale="No deterministic comparison is defined for this requirement"
            + (" (keyword-overlap text listed for reference only; it is not an assessed match)." if related else "."),
        )

    cat = CATEGORIES[cid]
    ev = _collect_evidence(p, cid)
    pos, neg = ev["pos"], ev["neg"]
    base = dict(limitations=ev["limits"])

    if pos and neg:
        detail = "Documented capability: '{}' conflicts with: '{}'.".format(pos[0]["text"], neg[0]["text"])
        return _row(
            item, prep, documented_capability=[x["text"] for x in pos], conflict=True, conflict_detail=detail,
            missing_information=["Resolve the conflicting catalog statements with the catalog owner or a specialist."],
            rationale="Catalog evidence conflicts; fit cannot be asserted.", **base,
        )

    if neg:
        if not verified:
            return _row(
                item, prep, missing_information=["Entry is synthetic/unverified; no fit can be asserted."],
                rationale="Placeholder entry mentions a limitation, but unverified entries cannot establish fit.", **base,
            )
        return _row(
            item, prep, fit_status=FIT_NOT_SUPPORTED,
            rationale=f"Catalog explicitly states a limitation for this area: '{neg[0]['text']}'",
            **base,
        )

    if not pos:
        has_docs = bool(_str_list(p.get("capabilities"))) or bool(p.get("summary"))
        missing = ["No documented capability for this area in the catalog entry."]
        if not has_docs:
            missing = ["The catalog entry has no documented capabilities or summary."]
        review = [f"Catalog limitation may exclude this area (needs specialist review): '{f}'" for f in ev["flags"]]
        return _row(
            item, prep,
            missing_information=missing + review + ev["validation"],
            rationale="No evidence either way; absence of documentation is not treated as lack of support.", **base,
        )

    texts = [x["text"] for x in pos]
    if not verified:
        return _row(
            item, prep, documented_capability=texts,
            missing_information=["Entry is synthetic/unverified (no source_url/verified_date); text is a placeholder."],
            rationale="Placeholder text mentions this area, but unverified entries cannot establish fit.", **base,
        )

    missing: list[str] = []
    strong = [x for x in pos if x["strength"] == "strong"]
    if not strong:
        missing.append("Only summary-level or partial documentation found; no specific capability stated.")
    evidence_norm = _norm(" ".join(texts))
    unmet = [q for q in item["qualifiers"] if _norm(q) not in evidence_norm]
    for q in unmet:
        missing.append(f"Target '{q}' is not documented in the catalog evidence.")
    if cat.get("needs_target") and not _QUANTITY.search(f"{item['text']} {item.get('target') or ''}"):
        missing.append("The requirement has no quantified target, so sizing cannot be compared.")
    outcome = _BUSINESS_CUES.search(item["text"])
    if outcome:
        missing.append(f"The outcome '{outcome.group(0)}' is not documented; the catalog describes capabilities, not results.")
    if cat.get("partial_only"):
        missing.append(cat["partial_only"])
    missing += [f"Review catalog limitation before relying on this fit: '{f}'" for f in ev["flags"]]
    missing += ev["validation"]

    fully_covered = bool(strong) and not unmet and not outcome and not cat.get("partial_only")
    if cat.get("needs_target") and not _QUANTITY.search(f"{item['text']} {item.get('target') or ''}"):
        fully_covered = False
    fit = FIT_SUPPORTED if fully_covered else FIT_PARTIAL
    if fit == FIT_SUPPORTED:
        rationale = "Verified catalog capability covers the requirement and its stated qualifiers; still preliminary."
    else:
        rationale = "Verified catalog capability is relevant, but the evidence does not cover every part of the requirement."
    return _row(item, prep, documented_capability=texts, fit_status=fit, missing_information=missing, rationale=rationale, **base)


# ------------------------------------------------------------------ candidates


def derive_candidates(items: list[dict], prepared: list[dict], limit: int) -> list[dict]:
    """Rank catalog products by how many requirement categories they document, then product_id."""
    cids = {i["category"] for i in items if i["category"]}
    scored: list[tuple[int, str, dict]] = []
    for prep in prepared:
        if prep["catalog_conflict"]:
            continue
        score = 0
        for cid in cids:
            ev = _collect_evidence(prep["record"], cid)
            if any(x["strength"] == "strong" for x in ev["pos"]) and not ev["neg"]:
                score += 1
        if score > 0:
            scored.append((score, str(prep["record"].get("product_id")), prep))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [t[2] for t in scored[:limit]]


# ------------------------------------------------------------------ orchestration


def compare_solutions(
    *,
    products: list[dict],
    requirements: Any = None,
    opportunity: dict | None = None,
    account: dict | None = None,
    product_ids: list[str] | None = None,
    focus_areas: Any = None,
    max_candidates: int = DEFAULT_CANDIDATES,
) -> dict:
    """Build the comparison. Raises ComparisonInputError for caller mistakes."""
    focus = resolve_focus_areas(focus_areas)
    prepared = prepare_products(products)
    by_id = {str(p["record"].get("product_id")): p for p in prepared}

    business: list[dict] = []
    constraints: list[dict] = []
    unknowns: list[dict] = []
    warnings: list[str] = []

    if requirements is not None:
        items = normalize_requirements(requirements)
        for it in items:
            warnings += _detect_injection(it["text"])
        if opportunity is not None:
            crm = extract_requirements_from_crm(opportunity, account)
            business, constraints, unknowns = crm["business_priorities"], crm["constraints"], crm["unknowns"]
    elif opportunity is not None:
        crm = extract_requirements_from_crm(opportunity, account)
        items, business, constraints, unknowns = crm["items"], crm["business_priorities"], crm["constraints"], crm["unknowns"]
    else:
        raise ComparisonInputError("invalid_input", "Provide either account_id or requirements.")

    if focus:
        present = {i["category"] for i in items}
        items = [i for i in items if i["category"] in focus]
        for cid in sorted(focus - present):
            unknowns.append({"item": f"No customer requirement captured for {CATEGORIES[cid]['label'].lower()}", "affects_category": cid})
        for n, it in enumerate(items, start=1):
            it["requirement_id"] = f"REQ-{n}"
    if not items:
        raise ComparisonInputError("not_found", "No requirements remain to compare after applying the request.")

    # Candidate selection
    if product_ids:
        if not isinstance(product_ids, list) or len(product_ids) > MAX_CANDIDATES:
            raise ComparisonInputError("invalid_input", f"product_ids must be a list of at most {MAX_CANDIDATES} identifiers.")
        ordered_ids: list[str] = []
        for pid in product_ids:
            if not isinstance(pid, str) or not _ID_RE.match(pid):
                raise ComparisonInputError("invalid_input", "product_ids must be product identifiers such as 'prod_flashsystem_5200'.")
            if pid not in ordered_ids:
                ordered_ids.append(pid)
        if any(pid not in by_id for pid in ordered_ids):
            raise ComparisonInputError(
                "not_found", "One or more product_ids were not found in the catalog.", sorted(by_id)
            )
        candidates = [by_id[pid] for pid in ordered_ids]
        method = "seller_specified"
    else:
        candidates = derive_candidates(items, prepared, max_candidates)
        method = "derived_by_documented_category_overlap"
        if not candidates:
            raise ComparisonInputError("not_found", "No catalog product has documented evidence for the stated requirements.")

    # Matrix
    matrix: list[dict] = []
    for item in items:
        for prep in candidates:
            matrix.append(assess(item, prep))

    verified_flags = [is_verified(c["record"]) for c in candidates]
    illustrative = not any(verified_flags)

    # Side-by-side
    side_by_side = []
    for item in items:
        results = {r["product_id"]: r["fit_status"] for r in matrix if r["requirement_id"] == item["requirement_id"]}
        side_by_side.append({"requirement_id": item["requirement_id"], "requirement": item["text"], "results": results})

    # Per-product summaries
    summaries = []
    for prep in candidates:
        p = prep["record"]
        rows = [r for r in matrix if r["product_id"] == p.get("product_id")]
        counts = {s: sum(1 for r in rows if r["fit_status"] == s) for s in FIT_STATUSES}
        summaries.append({
            "product_id": p.get("product_id"),
            "name": p.get("name"),
            "verification_status": "verified" if is_verified(p) else "synthetic_unverified",
            "status_counts": counts,
            "strengths": [
                {"requirement_id": r["requirement_id"], "requirement": r["requirement"],
                 "fit_status": r["fit_status"], "documented_capability": r["documented_capability"]}
                for r in rows if r["fit_status"] in (FIT_SUPPORTED, FIT_PARTIAL)
            ],
            "limitations": _str_list(p.get("limitations")),
            "explicit_gaps": [
                {"requirement_id": r["requirement_id"], "requirement": r["requirement"], "detail": r["rationale"]}
                for r in rows if r["fit_status"] == FIT_NOT_SUPPORTED
            ],
            "conflicts": [
                {"requirement_id": r["requirement_id"], "detail": r["conflict_detail"]} for r in rows if r["conflict"]
            ],
            "needs_validation": _str_list(p.get("needs_validation")),
            "catalog_source": _source(p),
        })

    # Requirements not yet validated
    candidate_ids = {c["record"].get("product_id") for c in candidates}
    not_validated = []
    for item in items:
        rows = [r for r in matrix if r["requirement_id"] == item["requirement_id"]]
        if not any(r["fit_status"] == FIT_SUPPORTED for r in rows):
            reasons: list[str] = []
            for r in rows:
                for m in r["missing_information"]:
                    if m not in reasons:
                        reasons.append(m)
            cid = item["category"]
            others = []
            if cid:
                for prep in prepared:
                    pr = prep["record"]
                    if prep["catalog_conflict"] or pr.get("product_id") in candidate_ids or not is_verified(pr):
                        continue
                    ev = _collect_evidence(pr, cid)
                    if ev["pos"] and not ev["neg"] and any(x["strength"] == "strong" for x in ev["pos"]):
                        others.append({"product_id": pr.get("product_id"), "name": pr.get("name"),
                                       "documented_capability": [x["text"] for x in ev["pos"] if x["strength"] == "strong"],
                                       "evidence_source": _source(pr)})
            not_validated.append({
                "other_catalog_products_with_documented_evidence": others,
                "requirement_id": item["requirement_id"], "requirement": item["text"],
                "best_status": next((s for s in (FIT_PARTIAL, FIT_NOT_SUPPORTED, FIT_UNKNOWN) if any(r["fit_status"] == s for r in rows)), FIT_UNKNOWN),
                "reasons": reasons[:6],
            })

    # Discovery questions (prioritised by gaps)
    questions: list[dict] = []
    seen_q: set[str] = set()

    def add_q(q: str, rid: str | None, why: str) -> None:
        if q not in seen_q:
            seen_q.add(q)
            questions.append({"question": q, "related_requirement_id": rid, "reason": why})

    gap_ids = {n["requirement_id"] for n in not_validated}
    for item in items:
        if item["requirement_id"] in gap_ids:
            for q in item["validation_questions"]:
                add_q(q, item["requirement_id"], "Requirement not yet fully validated by any candidate.")
    for u in unknowns:
        add_q(f"Can the customer provide: {u['item']}?", None, "Listed as unknown in the CRM or in this request.")
    for prep in candidates:
        for v in _str_list(prep["record"].get("needs_validation")):
            add_q(f"Validate with a specialist ({prep['record'].get('name')}): {v}", None, "Catalog 'needs validation' item.")

    # Preliminary direction
    ranked = sorted(summaries, key=lambda s: (-s["status_counts"][FIT_SUPPORTED], -s["status_counts"][FIT_PARTIAL], str(s["product_id"])))
    worth = [
        {"product_id": s["product_id"], "name": s["name"], "status_counts": s["status_counts"],
         "rationale": f"{s['status_counts'][FIT_SUPPORTED]} requirement(s) Supported and {s['status_counts'][FIT_PARTIAL]} Partially supported by verified catalog evidence."}
        for s in ranked
        if s["verification_status"] == "verified" and (s["status_counts"][FIT_SUPPORTED] + s["status_counts"][FIT_PARTIAL]) > 0
    ]
    caveats = [
        "Preliminary and based only on catalog text; not a validated configuration, sizing or quote.",
        "No pricing, guaranteed recovery times, performance benchmarks or competitive claims are provided.",
        "Absence of documentation is shown as Unknown, not as lack of support.",
        "Every Supported or Partially supported result still needs specialist validation of sizing, topology and compatibility.",
    ]
    if illustrative:
        caveats.insert(0, ILLUSTRATIVE_NOTICE)
        worth = []
    elif not all(verified_flags):
        caveats.append("Some candidates are synthetic or unverified placeholders; they are capped at Unknown and excluded from the direction.")
    if any(s["conflicts"] for s in summaries):
        caveats.append("Conflicting catalog information was found; see the conflicts listed per product.")
    if not worth and not illustrative:
        caveats.append("No candidate has verified evidence for any requirement; no direction can be offered.")

    data = {
        "illustrative": illustrative,
        "notice": GUARDRAIL_NOTICE if not illustrative else f"{ILLUSTRATIVE_NOTICE} {GUARDRAIL_NOTICE}",
        "synthetic_customer_data": bool((opportunity or {}).get("synthetic", True)) if opportunity else None,
        "fit_status_legend": list(FIT_STATUSES),
        "requirements_overview": build_requirements_overview(items, business, constraints, unknowns),
        "candidate_selection": {"method": method, "candidates": [c["record"].get("product_id") for c in candidates]},
        "candidates": [
            {"product_id": c["record"].get("product_id"), "name": c["record"].get("name"),
             "category": c["record"].get("category"),
             "verification_status": "verified" if is_verified(c["record"]) else "synthetic_unverified",
             **_source(c["record"])}
            for c in candidates
        ],
        "comparison_matrix": matrix,
        "side_by_side": side_by_side,
        "product_summaries": summaries,
        "requirements_not_yet_validated": not_validated,
        "recommended_discovery_questions": questions,
        "preliminary_solution_direction": {
            "label": "Preliminary - worth exploring, not a recommendation or validated fit",
            "worth_exploring": worth,
            "caveats": caveats,
        },
        "injection_warnings": warnings,
    }
    return data
