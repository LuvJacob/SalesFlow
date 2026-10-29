"""Generate one sample .docx per Document Studio template into docs/samples/.

Usage (from mcp-server/):  uv run python scripts/generate_studio_samples.py
Uses the synthetic demo CRM only. Scheduler state goes to a temp directory so
the real outputs/scheduler store is untouched. Existing samples are replaced
(this script owns docs/samples/studio_*.docx).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))

_tmp = tempfile.mkdtemp(prefix="sf_samples_")
os.environ["SALESFLOW_SCHEDULER_DIR"] = str(Path(_tmp) / "scheduler")
os.environ["SALESFLOW_OUTPUTS_DIR"] = str(Path(_tmp) / "outputs")

from salesflow_mcp import server as s  # noqa: E402
from studio_content import build_all_contents  # noqa: E402


def main() -> int:
    dest_dir = REPO / "docs" / "samples"
    dest_dir.mkdir(parents=True, exist_ok=True)
    contents = build_all_contents()
    failed = 0
    for doc_type, content in contents.items():
        r = s.generate_sales_document(doc_type, content)
        if r["status"] != "ok":
            print(f"FAIL {doc_type}: {r.get('message')}")
            failed += 1
            continue
        src = Path(r["data"]["file_path"])
        target = dest_dir / f"studio_{doc_type}.docx"
        target.write_bytes(src.read_bytes())
        print(f"OK   {doc_type}: {target.relative_to(REPO)} ({target.stat().st_size} bytes)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
