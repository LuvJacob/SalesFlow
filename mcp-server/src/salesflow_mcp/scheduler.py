"""Pipeline-review execution and the standalone scheduler daemon.

This module is independent of any MCP/Bob session. Run it as its own process:

    uv run salesflow-scheduler run      # long-running daemon (APScheduler ticker)
    uv run salesflow-scheduler tick     # run whatever is due once, then exit (cron/launchd friendly)
    uv run salesflow-scheduler demo     # create a schedule, make it due now, run it end to end
    uv run salesflow-scheduler status

Design: SQLite is the source of truth for *what* is scheduled and *when*
(see schedule_store). APScheduler (BackgroundScheduler/BlockingScheduler, in-memory
store) is used only as a reliable interval ticker that calls ``tick()``. Next-run
times are computed by schedule_spec so DST behaviour is explicit and testable, and
a restart simply re-reads the database: nothing lives only in memory.

A local scheduler only executes while its host machine and this process are
running. Missed occurrences are recorded, not silently dropped (see claim_due).

Nothing here sends notifications. ``Notifier`` is an optional adapter hook; no
implementation is shipped and none is invoked unless one is passed in explicitly.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
from datetime import datetime
from typing import Any, Protocol

from .pipeline_review import PipelineDataError, build_digest, write_digest_files
from .schedule_spec import (
    DEFAULT_TIMEZONE,
    ScheduleValidationError,
    to_iso,
    validate_schedule_params,
)
from .schedule_store import Claim, ScheduleStore, schedule_view, utcnow

log = logging.getLogger("salesflow.scheduler")

TICK_SECONDS = 30
DEMO_NAME = "Demo: Monday 8 AM ET pipeline risk briefing"


class Notifier(Protocol):
    """Optional adapter for an approved channel (email, Slack, ...).

    NOT implemented in the MVP. A concrete adapter must (1) be enabled only
    through explicit seller configuration, (2) send a link or summary that the
    seller approved, and (3) never be constructed by default. ``execute_run``
    calls ``notify`` only if an instance is passed in; failures never affect the
    run result.
    """

    def notify(self, digest_summary: dict[str, Any], digest_markdown_path: str) -> None: ...


# --------------------------------------------------------------------------- execution


def execute_run(
    store: ScheduleStore,
    run_id: str,
    *,
    trigger: str,
    schedule: dict[str, Any] | None,
    seller: str | None,
    now: datetime | None = None,
    notifier: Notifier | None = None,
) -> dict[str, Any]:
    """Build and store a digest for an already-created 'running' run row.

    Always finishes the run row (success or failed). Never raises for expected
    failures; unexpected exceptions are logged server-side and recorded generically.
    """
    now = now or utcnow()
    tz_name = schedule["timezone"] if schedule else DEFAULT_TIMEZONE
    try:
        digest = build_digest(
            now=now, trigger=trigger, run_id=run_id, schedule=schedule, seller=seller, tz_name=tz_name
        )
        json_rel, md_rel = write_digest_files(store.digest_dir, run_id, digest)
        summary = {
            "active_deals_analyzed": digest["summary"]["active_deals_analyzed"],
            "flagged_deals": digest["summary"]["flagged_deals"],
            "high_risk": digest["summary"]["risk_distribution"]["High Risk"]["count"],
            "flagged_value": digest["summary"]["flagged_value"],
        }
        store.finish_run(run_id, "success", now=now,
                         digest_json_path=json_rel, digest_md_path=md_rel, summary=summary)
        log.info("run succeeded run=%s schedule=%s flagged=%d", run_id,
                 schedule["schedule_id"] if schedule else "-", summary["flagged_deals"])
        if notifier is not None:
            try:
                notifier.notify(summary, md_rel)
            except Exception:  # noqa: BLE001 - notification must never fail the run
                log.warning("notifier failed run=%s", run_id, exc_info=True)
        return {"status": "success", "run_id": run_id, "summary": summary,
                "digest_json_path": json_rel, "digest_md_path": md_rel}
    except PipelineDataError as exc:
        store.finish_run(run_id, "failed", now=now, error_code=exc.code, error_message=exc.message)
        log.error("run failed run=%s code=%s", run_id, exc.code)
        return {"status": "failed", "run_id": run_id, "error_code": exc.code, "error_message": exc.message}
    except Exception:  # noqa: BLE001 - recorded generically; details only in the server log
        log.error("run crashed run=%s", run_id, exc_info=True)
        message = "The review failed unexpectedly. See the scheduler log for details."
        store.finish_run(run_id, "failed", now=now, error_code="internal_error", error_message=message)
        return {"status": "failed", "run_id": run_id, "error_code": "internal_error", "error_message": message}


def run_manual(
    store: ScheduleStore,
    *,
    schedule_id: str | None = None,
    seller: str | None = None,
    now: datetime | None = None,
    notifier: Notifier | None = None,
) -> dict[str, Any]:
    """Run a review immediately, recorded in history as a 'manual' run."""
    now = now or utcnow()
    schedule = store.get_schedule(schedule_id) if schedule_id else None
    if schedule_id and schedule is None:
        raise KeyError(schedule_id)
    scope = seller if seller else (schedule["seller"] if schedule else None)
    run_id = store.start_manual_run(schedule_id, scope, now=now)
    return execute_run(store, run_id, trigger="manual", schedule=schedule, seller=scope, now=now, notifier=notifier)


def tick(
    store: ScheduleStore, now: datetime | None = None, notifier: Notifier | None = None
) -> list[dict[str, Any]]:
    """Claim and execute every schedule that is due.

    Deliberately does not write the heartbeat: a one-shot tick or the demo must
    not make list_pipeline_schedules report that a scheduler daemon is running.
    """
    now = now or utcnow()
    results = []
    for claim in store.claim_due(now):
        results.append(_execute_claim(store, claim, now, notifier))
    return results


def _execute_claim(store: ScheduleStore, claim: Claim, now: datetime, notifier: Notifier | None) -> dict[str, Any]:
    return execute_run(
        store, claim.run_id, trigger="scheduled", schedule=claim.schedule,
        seller=claim.schedule["seller"], now=now, notifier=notifier,
    )


# --------------------------------------------------------------------------- daemon


def run_daemon(store: ScheduleStore, tick_seconds: int = TICK_SECONDS) -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler

    recovered = store.recover_interrupted()
    log.info("scheduler starting db=%s recovered_interrupted=%d tick=%ss", store.db_path.name, recovered, tick_seconds)
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(
        lambda: _safe_tick(store), "interval", seconds=tick_seconds, id="salesflow-tick",
        max_instances=1, coalesce=True, next_run_time=utcnow(),
    )
    stop = threading.Event()

    def _shutdown(signum: int, _frame: Any) -> None:
        log.info("signal %s received; shutting down", signum)
        if not stop.is_set():
            stop.set()
            sched.shutdown(wait=False)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    try:
        sched.start()
    finally:
        log.info("scheduler stopped")


def _safe_tick(store: ScheduleStore) -> None:
    try:
        store.heartbeat()
        tick(store)
    except Exception:  # noqa: BLE001 - one bad tick must not kill the daemon
        log.error("tick failed", exc_info=True)


# --------------------------------------------------------------------------- demo / CLI


def run_demo(store: ScheduleStore, keep: bool = False) -> dict[str, Any]:
    """Create a schedule, make it due now, and run it through the real claim path.

    Running this command is the seller's explicit authorization to create (and, unless
    --keep, cancel) the demo schedule. The seller's own recurring schedules are untouched.
    """
    spec = validate_schedule_params("weekly", 8, 0, ["mon"], DEFAULT_TIMEZONE)
    now = utcnow()
    schedule = store.create_schedule(spec, DEMO_NAME, None, "authorized via CLI demo command", now=now)
    store.force_next_run(schedule["schedule_id"], now)
    results = tick(store, now=now)
    mine = [r for r in results if r.get("run_id")]
    final = store.get_schedule(schedule["schedule_id"])
    if not keep:
        store.set_status(schedule["schedule_id"], "cancel", "demo cleanup (CLI)")
    return {"schedule": schedule_view(final) if final else None, "results": mine, "kept": keep}


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="salesflow-scheduler", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="run the scheduler daemon in the foreground")
    p_run.add_argument("--tick-seconds", type=int, default=TICK_SECONDS)
    sub.add_parser("tick", help="run due schedules once and exit")
    p_demo = sub.add_parser("demo", help="trigger a scheduled review immediately")
    p_demo.add_argument("--keep", action="store_true", help="leave the demo schedule active")
    sub.add_parser("status", help="show schedules and scheduler heartbeat")
    args = parser.parse_args(argv)

    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    store = ScheduleStore()

    if args.cmd == "run":
        if args.tick_seconds < 1:
            parser.error("--tick-seconds must be >= 1")
        run_daemon(store, args.tick_seconds)
        return 0
    if args.cmd == "tick":
        store.recover_interrupted()
        for r in tick(store):
            print(f"{r['status']}: run {r['run_id']}")
        return 0
    if args.cmd == "demo":
        out = run_demo(store, keep=args.keep)
        if not out["results"] or out["results"][0]["status"] != "success":
            print("Demo run failed; see stderr.", file=sys.stderr)
            return 1
        r = out["results"][0]
        print(f"Schedule created and triggered immediately: {out['schedule']['schedule_id']}")
        print(f"Run {r['run_id']}: {r['summary']['flagged_deals']} flagged of "
              f"{r['summary']['active_deals_analyzed']} active deals")
        print(f"Markdown digest: {store.digest_dir / r['digest_md_path']}")
        print(f"JSON digest:     {store.digest_dir / r['digest_json_path']}")
        print("Schedule kept active." if out["kept"] else "Demo schedule cancelled (use --keep to retain).")
        print("Ask Bob: 'Get my latest pipeline digest.'")
        return 0
    if args.cmd == "status":
        hb = store.scheduler_status()
        print(f"scheduler running: {hb['running']} (last heartbeat: {hb['last_heartbeat_at']})")
        for row in store.list_schedules():
            v = schedule_view(row)
            print(f"{v['schedule_id']}  {v['status']:<9} {v['description']}  next={v['next_expected_run']['local']}")
        return 0
    return 2  # unreachable


def main() -> None:
    try:
        sys.exit(_cli())
    except ScheduleValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
