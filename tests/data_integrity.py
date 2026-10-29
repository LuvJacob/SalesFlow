"""Lane C data integrity checks.

Validates that all JSON fixture files in data/ conform to the schemas agreed in
docs/contracts/mcp-tools.md and that cross-file references resolve correctly.

Run from the repo root:
    python tests/data_integrity.py

Exit code 0 = all checks passed. Exit code 1 = failures found.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"

PLAYBOOK_TOPICS = {
    "spin",
    "discovery_agenda",
    "qualification",
    "objection_pricing",
    "objection_technical",
    "objection_competition",
    "objection_implementation",
    "objection_value",
}

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"{status:<6} {name}" + (f"  — {detail}" if detail else ""))


def load(path: Path) -> dict | list | None:
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        check(f"JSON valid: {path.name}", False, str(exc))
        return None


# --------------------------------------------------------------------------- accounts

def check_accounts() -> list[str]:
    """Returns list of valid account_ids for cross-file checks."""
    doc = load(DATA_DIR / "accounts.json")
    if doc is None:
        return []
    check("accounts.json: valid JSON", True)

    accounts = doc.get("accounts") if isinstance(doc, dict) else None
    check("accounts.json: has 'accounts' list", isinstance(accounts, list))
    if not isinstance(accounts, list):
        return []

    check("accounts.json: at least 3 accounts", len(accounts) >= 3, f"found {len(accounts)}")

    ids: list[str] = []
    for i, a in enumerate(accounts):
        prefix = f"accounts[{i}] ({a.get('account_id', '?')})"
        check(f"{prefix}: has account_id", bool(a.get("account_id")))
        check(f"{prefix}: has name", bool(a.get("name")))
        check(f"{prefix}: has industry", bool(a.get("industry")))
        check(f"{prefix}: has overview", bool(a.get("overview")))
        check(f"{prefix}: challenges is list", isinstance(a.get("challenges"), list))
        check(f"{prefix}: unknowns is list", isinstance(a.get("unknowns"), list))
        check(f"{prefix}: has source_id", bool(a.get("source_id")))
        check(f"{prefix}: synthetic flag present", "synthetic" in a)
        if a.get("account_id"):
            ids.append(a["account_id"])
    return ids


# --------------------------------------------------------------------------- opportunities

def check_opportunities(valid_account_ids: list[str]) -> None:
    doc = load(DATA_DIR / "opportunities.json")
    if doc is None:
        return
    check("opportunities.json: valid JSON", True)

    opps = doc.get("opportunities") if isinstance(doc, dict) else None
    check("opportunities.json: has 'opportunities' list", isinstance(opps, list))
    if not isinstance(opps, list):
        return

    check("opportunities.json: at least 1 opportunity", len(opps) >= 1, f"found {len(opps)}")

    acme_found = False
    for i, o in enumerate(opps):
        prefix = f"opportunities[{i}] ({o.get('opportunity_id', '?')})"
        check(f"{prefix}: has opportunity_id", bool(o.get("opportunity_id")))
        check(f"{prefix}: has account_id", bool(o.get("account_id")))
        check(f"{prefix}: account_id resolves", o.get("account_id") in valid_account_ids,
              f"'{o.get('account_id')}' not in accounts.json")
        check(f"{prefix}: has name", bool(o.get("name")))
        check(f"{prefix}: has stage", bool(o.get("stage")))
        check(f"{prefix}: requirements is list", isinstance(o.get("requirements"), list))
        check(f"{prefix}: stakeholders is list", isinstance(o.get("stakeholders"), list))
        check(f"{prefix}: notes is list", isinstance(o.get("notes"), list))
        check(f"{prefix}: unknowns is list", isinstance(o.get("unknowns"), list),
              "unknowns must always be present, even if empty")
        check(f"{prefix}: has source_id", bool(o.get("source_id")))
        check(f"{prefix}: synthetic flag present", "synthetic" in o)

        if o.get("account_id") == "acct_acme_healthcare":
            acme_found = True
            unknowns = o.get("unknowns", [])
            check(f"{prefix}: Acme has at least 2 unknowns (budget, capacity, decision maker)",
                  len(unknowns) >= 2, f"found {unknowns}")
            check(f"{prefix}: Acme requirements count >= 3", len(o.get("requirements", [])) >= 3)

    check("opportunities.json: Acme Healthcare opportunity present", acme_found)


# --------------------------------------------------------------------------- products

def check_products() -> list[str]:
    """Returns list of valid product_ids for cross-file checks."""
    doc = load(DATA_DIR / "products.json")
    if doc is None:
        return []
    check("products.json: valid JSON", True)

    products = doc.get("products") if isinstance(doc, dict) else None
    check("products.json: has 'products' list", isinstance(products, list))
    if not isinstance(products, list):
        return []

    check("products.json: at least 4 products", len(products) >= 4, f"found {len(products)}")

    ids: list[str] = []
    verified_count = 0
    for i, p in enumerate(products):
        prefix = f"products[{i}] ({p.get('product_id', '?')})"
        check(f"{prefix}: has product_id", bool(p.get("product_id")))
        check(f"{prefix}: has name", bool(p.get("name")))
        check(f"{prefix}: has category", bool(p.get("category")))
        check(f"{prefix}: has summary", bool(p.get("summary")))
        check(f"{prefix}: capabilities is list", isinstance(p.get("capabilities"), list))
        check(f"{prefix}: limitations is list", isinstance(p.get("limitations"), list))
        check(f"{prefix}: has source_id", bool(p.get("source_id")))
        check(f"{prefix}: synthetic flag present", "synthetic" in p)

        is_synthetic = bool(p.get("synthetic", True))
        has_url = bool(p.get("source_url"))
        has_date = bool(p.get("verified_date"))

        if not is_synthetic:
            check(f"{prefix}: verified entry has source_url", has_url, "non-synthetic entry missing source_url")
            check(f"{prefix}: verified entry has verified_date", has_date, "non-synthetic entry missing verified_date")
            if has_url and has_date:
                verified_count += 1

        if p.get("product_id"):
            ids.append(p["product_id"])

    check("products.json: at least 3 verified (non-synthetic) entries", verified_count >= 3,
          f"found {verified_count} with source_url + verified_date")
    return ids


# --------------------------------------------------------------------------- playbooks

def check_playbooks() -> None:
    pb_dir = DATA_DIR / "playbooks"
    check("data/playbooks/ directory exists", pb_dir.is_dir())
    if not pb_dir.is_dir():
        return

    files = sorted(pb_dir.glob("*.json"))
    check("playbooks: at least 5 json files", len(files) >= 5, f"found {len(files)}")

    found_topics: set[str] = set()
    for f in files:
        doc = load(f)
        if doc is None:
            continue
        check(f"playbook {f.name}: valid JSON", True)

        # handle both single-object and {playbooks: [...]} formats
        entries = []
        if isinstance(doc, dict) and "playbooks" in doc:
            entries = doc["playbooks"] if isinstance(doc["playbooks"], list) else []
        elif isinstance(doc, dict):
            entries = [doc]

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            topic = entry.get("topic", "")
            prefix = f"playbook {f.name} topic={topic!r}"
            check(f"{prefix}: topic in allowlist", topic in PLAYBOOK_TOPICS,
                  f"valid topics: {sorted(PLAYBOOK_TOPICS)}")
            check(f"{prefix}: has title", bool(entry.get("title")))
            check(f"{prefix}: has guidance", bool(entry.get("guidance")))
            check(f"{prefix}: has source_id", bool(entry.get("source_id")))
            check(f"{prefix}: synthetic flag present", "synthetic" in entry)
            found_topics.add(topic)

    missing = PLAYBOOK_TOPICS - found_topics
    check("playbooks: all 8 required topics present", len(missing) == 0,
          f"missing: {sorted(missing)}" if missing else "")


# --------------------------------------------------------------------------- main

def main() -> None:
    print(f"Data directory: {DATA_DIR}\n")

    valid_account_ids = check_accounts()
    print()
    check_opportunities(valid_account_ids)
    print()
    check_products()
    print()
    check_playbooks()

    print()
    failures = [name for name, ok, _ in results if not ok]
    total = len(results)
    print(f"{total} checks, {len(failures)} failed" +
          (": " + ", ".join(failures) if failures else " — all passed"))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
