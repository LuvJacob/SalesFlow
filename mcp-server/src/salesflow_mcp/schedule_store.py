"""SQLite persistence for pipeline-review schedules, run history and audit events.

The database is the single source of truth. The scheduler daemon and the MCP
server are separate processes that both open it, so:

- every connection uses WAL + a busy timeout;
- claiming due work happens inside one BEGIN IMMEDIATE transaction that also
  advances ``next_run_at`` (a second ticker sees nothing due);
- a partial UNIQUE index on (schedule_id, scheduled_for) for scheduled runs is
  a second line of defence against duplicate execution of one occurrence.

All timestamps are stored as UTC ISO-8601 strings. No CRM content is stored here
beyond summary counts; digests live as files under ``digests/``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from .schedule_spec import (
    ScheduleSpec,
    from_iso,
    next_occurrence,
    spec_from_row,
    to_iso,
    to_local_iso,
)

log = logging.getLogger("salesflow.scheduler")

# A scheduled occurrence older than this when the scheduler wakes up is recorded
# as "missed" instead of being run late (a stale Monday digest on Wednesday is
# misleading). Override with SALESFLOW_MISFIRE_GRACE_SECONDS.
DEFAULT_MISFIRE_GRACE = timedelta(hours=6)
# A run still "running" after this long belongs to a crashed process.
STALE_RUN_AFTER = timedelta(minutes=15)
HEARTBEAT_FRESH_FOR = timedelta(minutes=2)
CONFIRMATION_TTL = timedelta(minutes=10)
MAX_CATCHUP_SCAN = 2000

_ID_RE = re.compile(r"^(sched|run)_[0-9a-f]{12}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    seller          TEXT,
    cadence         TEXT NOT NULL CHECK (cadence IN ('daily','weekly')),
    days_of_week    TEXT NOT NULL DEFAULT '',
    hour            INTEGER NOT NULL CHECK (hour BETWEEN 0 AND 23),
    minute          INTEGER NOT NULL CHECK (minute BETWEEN 0 AND 59),
    timezone        TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('active','paused','cancelled')),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    next_run_at     TEXT,
    last_run_at     TEXT,
    last_run_status TEXT,
    last_success_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_schedules_due ON schedules(status, next_run_at);

CREATE TABLE IF NOT EXISTS runs (
    run_id           TEXT PRIMARY KEY,
    schedule_id      TEXT REFERENCES schedules(schedule_id),
    trigger          TEXT NOT NULL CHECK (trigger IN ('scheduled','manual')),
    scheduled_for    TEXT,
    status           TEXT NOT NULL CHECK (status IN ('running','success','failed','skipped')),
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    error_code       TEXT,
    error_message    TEXT,
    seller_scope     TEXT,
    missed_count     INTEGER NOT NULL DEFAULT 0,
    digest_json_path TEXT,
    digest_md_path   TEXT,
    summary_json     TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_runs_scheduled
    ON runs(schedule_id, scheduled_for) WHERE trigger = 'scheduled';
CREATE INDEX IF NOT EXISTS ix_runs_schedule ON runs(schedule_id, started_at);

CREATE TABLE IF NOT EXISTS events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL,
    schedule_id TEXT,
    action      TEXT NOT NULL,
    detail      TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS confirmations (
    token       TEXT PRIMARY KEY,
    action_hash TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
"""


# --------------------------------------------------------------------------- paths


def state_dir() -> Path:
    """Directory holding schedules.db and digests/. Override: SALESFLOW_SCHEDULER_DIR."""
    override = os.environ.get("SALESFLOW_SCHEDULER_DIR")
    if override:
        p = Path(override)
        if not p.is_absolute():
            raise ValueError("SALESFLOW_SCHEDULER_DIR must be an absolute path.")
        return p
    # src/salesflow_mcp/schedule_store.py -> repo root is parents[3]; outputs/* is git-ignored
    return Path(__file__).resolve().parents[3] / "outputs" / "scheduler"


def misfire_grace() -> timedelta:
    raw = os.environ.get("SALESFLOW_MISFIRE_GRACE_SECONDS")
    if raw:
        try:
            seconds = int(raw)
            if seconds >= 0:
                return timedelta(seconds=seconds)
        except ValueError:
            pass
        log.warning("ignoring invalid SALESFLOW_MISFIRE_GRACE_SECONDS")
    return DEFAULT_MISFIRE_GRACE


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def is_valid_id(value: object, prefix: str) -> bool:
    return isinstance(value, str) and bool(_ID_RE.match(value)) and value.startswith(prefix + "_")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Claim:
    """One unit of work claimed from the schedule table."""

    run_id: str
    schedule: dict[str, Any]
    scheduled_for: datetime
    missed_count: int


# --------------------------------------------------------------------------- store


class ScheduleStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path) if db_path else state_dir() / "schedules.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self._conn() as conn:
            conn.executescript(SCHEMA)
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    @property
    def digest_dir(self) -> Path:
        return self.db_path.parent / "digests"

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")

    # ------------------------------------------------------------ schedules

    def create_schedule(
        self,
        spec: ScheduleSpec,
        name: str,
        seller: str | None,
        authorization: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or utcnow()
        schedule_id = new_id("sched")
        first = next_occurrence(spec, now)
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO schedules (schedule_id, name, seller, cadence, days_of_week, hour, minute,"
                " timezone, status, created_at, updated_at, next_run_at)"
                " VALUES (?,?,?,?,?,?,?,?, 'active', ?,?,?)",
                (schedule_id, name, seller, spec.cadence, spec.days_label, spec.hour, spec.minute,
                 spec.timezone, to_iso(now), to_iso(now), to_iso(first)),
            )
            self._event(conn, now, schedule_id, "created", authorization)
        return self.get_schedule(schedule_id)  # type: ignore[return-value]

    def get_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM schedules WHERE schedule_id = ?", (schedule_id,)).fetchone()
        return dict(row) if row else None

    def list_schedules(self, include_cancelled: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM schedules"
        if not include_cancelled:
            sql += " WHERE status != 'cancelled'"
        sql += " ORDER BY created_at, schedule_id"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql)]

    def set_status(
        self, schedule_id: str, action: str, authorization: str, now: datetime | None = None
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Apply pause / resume / cancel. Returns (schedule, error_message)."""
        now = now or utcnow()
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM schedules WHERE schedule_id = ?", (schedule_id,)).fetchone()
            if row is None:
                return None, None
            current = row["status"]
            if current == "cancelled":
                return dict(row), "This schedule is already cancelled and cannot be changed. Create a new schedule instead."
            if action == "pause":
                if current == "paused":
                    return dict(row), "This schedule is already paused."
                new_status, next_run = "paused", None
            elif action == "resume":
                if current == "active":
                    return dict(row), "This schedule is already active."
                new_status, next_run = "active", to_iso(next_occurrence(spec_from_row(dict(row)), now))
            elif action == "cancel":
                new_status, next_run = "cancelled", None
            else:  # callers validate; defensive
                return dict(row), "Unsupported action."
            conn.execute(
                "UPDATE schedules SET status = ?, next_run_at = ?, updated_at = ? WHERE schedule_id = ?",
                (new_status, next_run, to_iso(now), schedule_id),
            )
            self._event(conn, now, schedule_id, action, authorization)
        return self.get_schedule(schedule_id), None

    def force_next_run(self, schedule_id: str, when: datetime) -> None:
        """Demo/test hook: pretend the next occurrence is `when`."""
        with self._tx() as conn:
            conn.execute("UPDATE schedules SET next_run_at = ? WHERE schedule_id = ?", (to_iso(when), schedule_id))

    # ------------------------------------------------------------ claiming / runs

    def claim_due(self, now: datetime | None = None, grace: timedelta | None = None) -> list[Claim]:
        """Atomically claim every due schedule and advance its next_run_at.

        If several occurrences were missed (process was down) only the most
        recent one is run, provided it is within `grace`; older ones are counted
        in ``missed_count``. If even the latest is beyond `grace`, a 'skipped'
        history row is written instead of running a stale review.
        """
        now = now or utcnow()
        grace = misfire_grace() if grace is None else grace
        claims: list[Claim] = []
        with self._tx() as conn:
            due = conn.execute(
                "SELECT * FROM schedules WHERE status = 'active' AND next_run_at IS NOT NULL AND next_run_at <= ?"
                " ORDER BY next_run_at, schedule_id",
                (to_iso(now),),
            ).fetchall()
            for row in due:
                sched = dict(row)
                spec = spec_from_row(sched)
                latest = from_iso(sched["next_run_at"])
                assert latest is not None
                count = 1
                while count < MAX_CATCHUP_SCAN:
                    nxt = next_occurrence(spec, latest)
                    if nxt > now:
                        break
                    latest, count = nxt, count + 1
                new_next = next_occurrence(spec, now)
                run_id = new_id("run")
                too_old = now - latest > grace
                try:
                    conn.execute(
                        "INSERT INTO runs (run_id, schedule_id, trigger, scheduled_for, status, started_at,"
                        " finished_at, error_code, error_message, seller_scope, missed_count)"
                        " VALUES (?,?, 'scheduled', ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            run_id, sched["schedule_id"], to_iso(latest),
                            "skipped" if too_old else "running", to_iso(now),
                            to_iso(now) if too_old else None,
                            "missed" if too_old else None,
                            "Scheduler was not running at the scheduled time; the occurrence was too old to run."
                            if too_old else None,
                            sched["seller"], count - 1,
                        ),
                    )
                except sqlite3.IntegrityError:
                    # This occurrence already has a run row: duplicate-run protection.
                    log.warning("duplicate occurrence suppressed schedule=%s scheduled_for=%s",
                                sched["schedule_id"], to_iso(latest))
                    self._event(conn, now, sched["schedule_id"], "duplicate_suppressed", to_iso(latest))
                    conn.execute("UPDATE schedules SET next_run_at = ?, updated_at = ? WHERE schedule_id = ?",
                                 (to_iso(new_next), to_iso(now), sched["schedule_id"]))
                    continue
                conn.execute(
                    "UPDATE schedules SET next_run_at = ?, updated_at = ?,"
                    " last_run_at = CASE WHEN ? THEN ? ELSE last_run_at END,"
                    " last_run_status = CASE WHEN ? THEN 'skipped' ELSE last_run_status END"
                    " WHERE schedule_id = ?",
                    (to_iso(new_next), to_iso(now), too_old, to_iso(now), too_old, sched["schedule_id"]),
                )
                if too_old:
                    self._event(conn, now, sched["schedule_id"], "missed", to_iso(latest))
                    log.warning("missed occurrence skipped schedule=%s scheduled_for=%s",
                                sched["schedule_id"], to_iso(latest))
                    continue
                claims.append(Claim(run_id, sched, latest, count - 1))
        return claims

    def start_manual_run(
        self, schedule_id: str | None, seller_scope: str | None, now: datetime | None = None
    ) -> str:
        now = now or utcnow()
        run_id = new_id("run")
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO runs (run_id, schedule_id, trigger, status, started_at, seller_scope)"
                " VALUES (?,?, 'manual', 'running', ?, ?)",
                (run_id, schedule_id, to_iso(now), seller_scope),
            )
        return run_id

    def finish_run(
        self,
        run_id: str,
        status: str,
        now: datetime | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        digest_json_path: str | None = None,
        digest_md_path: str | None = None,
        summary: dict[str, Any] | None = None,
    ) -> None:
        now = now or utcnow()
        with self._tx() as conn:
            row = conn.execute("SELECT schedule_id FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            conn.execute(
                "UPDATE runs SET status = ?, finished_at = ?, error_code = ?, error_message = ?,"
                " digest_json_path = ?, digest_md_path = ?, summary_json = ? WHERE run_id = ?",
                (status, to_iso(now), error_code, error_message, digest_json_path, digest_md_path,
                 json.dumps(summary) if summary is not None else None, run_id),
            )
            if row and row["schedule_id"]:
                conn.execute(
                    "UPDATE schedules SET last_run_at = ?, last_run_status = ?,"
                    " last_success_at = CASE WHEN ? = 'success' THEN ? ELSE last_success_at END"
                    " WHERE schedule_id = ?",
                    (to_iso(now), status, status, to_iso(now), row["schedule_id"]),
                )
            self._event(conn, now, row["schedule_id"] if row else None,
                        f"run_{status}", f"{run_id} {error_code or ''}".strip())

    def recover_interrupted(self, now: datetime | None = None, stale_after: timedelta = STALE_RUN_AFTER) -> int:
        """Mark runs left 'running' by a crashed process as failed. Returns the count."""
        now = now or utcnow()
        cutoff = to_iso(now - stale_after)
        recovered = 0
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT run_id, schedule_id FROM runs WHERE status = 'running' AND started_at <= ?", (cutoff,)
            ).fetchall()
            for r in rows:
                conn.execute(
                    "UPDATE runs SET status = 'failed', finished_at = ?, error_code = 'interrupted',"
                    " error_message = 'The scheduler stopped before this run finished.' WHERE run_id = ?",
                    (to_iso(now), r["run_id"]),
                )
                if r["schedule_id"]:
                    conn.execute("UPDATE schedules SET last_run_at = ?, last_run_status = 'failed' WHERE schedule_id = ?",
                                 (to_iso(now), r["schedule_id"]))
                self._event(conn, now, r["schedule_id"], "run_interrupted", r["run_id"])
                recovered += 1
        if recovered:
            log.warning("recovered %d interrupted run(s)", recovered)
        return recovered

    def list_runs(self, schedule_id: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        sql = "SELECT * FROM runs"
        args: list[Any] = []
        if schedule_id:
            sql += " WHERE schedule_id = ?"
            args.append(schedule_id)
        sql += " ORDER BY started_at DESC, rowid DESC LIMIT ?"
        args.append(limit)
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, args)]

    def latest_successful_run(self, schedule_id: str | None = None) -> dict[str, Any] | None:
        sql = "SELECT * FROM runs WHERE status = 'success'"
        args: list[Any] = []
        if schedule_id:
            sql += " AND schedule_id = ?"
            args.append(schedule_id)
        sql += " ORDER BY finished_at DESC, rowid DESC LIMIT 1"
        with self._conn() as conn:
            row = conn.execute(sql, args).fetchone()
        return dict(row) if row else None

    def list_events(self, schedule_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        sql = "SELECT * FROM events"
        args: list[Any] = []
        if schedule_id:
            sql += " WHERE schedule_id = ?"
            args.append(schedule_id)
        sql += " ORDER BY event_id DESC LIMIT ?"
        args.append(limit)
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, args)]

    # ------------------------------------------------------------ seller authorization

    def issue_confirmation(self, action: dict[str, Any], now: datetime | None = None) -> str:
        """Create a single-use token bound to exactly this action (tool + parameters)."""
        now = now or utcnow()
        token = "confirm_" + secrets.token_urlsafe(18)
        with self._tx() as conn:
            conn.execute("DELETE FROM confirmations WHERE expires_at <= ?", (to_iso(now),))
            conn.execute(
                "INSERT INTO confirmations (token, action_hash, expires_at) VALUES (?,?,?)",
                (token, _action_hash(action), to_iso(now + CONFIRMATION_TTL)),
            )
        return token

    def consume_confirmation(self, token: object, action: dict[str, Any], now: datetime | None = None) -> bool:
        """Atomically spend a token. False if unknown, expired, already used, or for a different action."""
        if not isinstance(token, str) or not token.startswith("confirm_") or len(token) > 100:
            return False
        now = now or utcnow()
        with self._tx() as conn:
            cur = conn.execute(
                "DELETE FROM confirmations WHERE token = ? AND action_hash = ? AND expires_at > ?",
                (token, _action_hash(action), to_iso(now)),
            )
            return cur.rowcount == 1


    # ------------------------------------------------------------ heartbeat

    def heartbeat(self, now: datetime | None = None) -> None:
        now = now or utcnow()
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('heartbeat', ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (json.dumps({"at": to_iso(now), "pid": os.getpid()}),),
            )

    def scheduler_status(self, now: datetime | None = None) -> dict[str, Any]:
        """Whether a scheduler process has recently ticked (it may not be running at all)."""
        now = now or utcnow()
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = 'heartbeat'").fetchone()
        last = None
        if row:
            try:
                last = from_iso(json.loads(row["value"]).get("at"))
            except (ValueError, TypeError, AttributeError):
                last = None
        running = bool(last and now - last <= HEARTBEAT_FRESH_FOR)
        return {"running": running, "last_heartbeat_at": to_iso(last)}

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _event(conn: sqlite3.Connection, now: datetime, schedule_id: str | None, action: str, detail: str | None) -> None:
        conn.execute(
            "INSERT INTO events (at, schedule_id, action, detail) VALUES (?,?,?,?)",
            (to_iso(now), schedule_id, action, detail),
        )

    def resolve_digest_file(self, relative: str | None) -> Path | None:
        """Resolve a stored relative digest path, refusing anything outside digest_dir."""
        if not relative:
            return None
        base = self.digest_dir.resolve()
        candidate = (base / relative).resolve()
        try:
            candidate.relative_to(base)
        except ValueError:
            log.error("digest path escaped digest dir; refusing to read")
            return None
        return candidate if candidate.is_file() else None


def _action_hash(action: dict[str, Any]) -> str:
    canonical = json.dumps(action, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def schedule_view(row: dict[str, Any]) -> dict[str, Any]:
    """Seller-facing representation of a schedule row (local + UTC times)."""
    spec = spec_from_row(row)
    tz = row["timezone"]

    def pair(key: str) -> dict[str, str | None]:
        value = from_iso(row.get(key))
        return {"utc": to_iso(value), "local": to_local_iso(value, tz)}

    return {
        "schedule_id": row["schedule_id"],
        "name": row["name"],
        "seller": row["seller"],
        "status": row["status"],
        "enabled": row["status"] == "active",
        "cadence": spec.cadence,
        "days_of_week": [d for d in row["days_of_week"].split(",") if d],
        "time_local": f"{spec.hour:02d}:{spec.minute:02d}",
        "timezone": tz,
        "description": spec.describe(),
        "next_expected_run": pair("next_run_at"),
        "last_run": pair("last_run_at"),
        "last_run_status": row["last_run_status"],
        "last_successful_run": pair("last_success_at"),
        "created_at": row["created_at"],
    }
