"""Schedule parameter validation and DST-safe next-run calculation.

Next-run times are computed here (not by APScheduler's CronTrigger) so the
result is deterministic and fires exactly once per local calendar day, even
across daylight-saving transitions:

- Nonexistent local time (spring forward, e.g. 02:30 on 2027-03-14 in
  America/New_York): the run happens at the shifted wall-clock time (03:30 EDT).
- Ambiguous local time (fall back, e.g. 01:30 on 2026-11-01): the FIRST
  occurrence is used, so the run is not executed twice.

Pure functions only: no I/O, no clock access.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/New_York"
CADENCES = ("daily", "weekly")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MAX_NAME_LEN = 80
MAX_SELLER_LEN = 100

_WEEKDAY_ALIASES = {
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}
_TZ_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_+\-]*(/[A-Za-z0-9_+\-]+){0,2}$")


class ScheduleValidationError(ValueError):
    """User-safe validation failure. The message is safe to return to the caller."""


@dataclass(frozen=True)
class ScheduleSpec:
    cadence: str                 # "daily" | "weekly"
    days_of_week: tuple[int, ...]  # 0=Mon..6=Sun; empty for daily
    hour: int
    minute: int
    timezone: str

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def days_label(self) -> str:
        return ",".join(WEEKDAYS[d] for d in self.days_of_week)

    def describe(self) -> str:
        at = f"{self.hour:02d}:{self.minute:02d} {self.timezone}"
        if self.cadence == "daily":
            return f"Daily at {at}"
        return f"Weekly on {', '.join(WEEKDAYS[d].capitalize() for d in self.days_of_week)} at {at}"


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_name(name: object) -> str:
    if not isinstance(name, str):
        raise ScheduleValidationError("name must be a string.")
    cleaned = " ".join("".join(ch for ch in name if ch.isprintable()).split())
    if not cleaned:
        raise ScheduleValidationError("name must not be empty.")
    if len(cleaned) > MAX_NAME_LEN:
        raise ScheduleValidationError(f"name must be at most {MAX_NAME_LEN} characters.")
    return cleaned


def validate_seller(seller: object) -> str | None:
    if seller is None:
        return None
    if not isinstance(seller, str):
        raise ScheduleValidationError("seller must be a string.")
    cleaned = " ".join("".join(ch for ch in seller if ch.isprintable()).split())
    if not cleaned:
        return None
    if len(cleaned) > MAX_SELLER_LEN:
        raise ScheduleValidationError(f"seller must be at most {MAX_SELLER_LEN} characters.")
    return cleaned


def validate_timezone(tz_name: object) -> str:
    """Return the canonical IANA name or raise ScheduleValidationError."""
    if not isinstance(tz_name, str) or not _TZ_NAME.match(tz_name.strip()):
        raise ScheduleValidationError("timezone must be a valid IANA name such as 'America/New_York'.")
    try:
        ZoneInfo(tz_name.strip())
    except (KeyError, ValueError, OSError):
        raise ScheduleValidationError("timezone must be a valid IANA name such as 'America/New_York'.") from None
    return tz_name.strip()


def parse_days(days: object) -> tuple[int, ...]:
    if isinstance(days, str):
        days = [p for p in re.split(r"[,\s]+", days) if p]
    if not isinstance(days, (list, tuple)) or not days:
        raise ScheduleValidationError(
            "weekly schedules need days_of_week, for example ['mon'] (allowed: mon, tue, wed, thu, fri, sat, sun)."
        )
    out: set[int] = set()
    for d in days:
        key = d.strip().lower() if isinstance(d, str) else None
        if key not in _WEEKDAY_ALIASES:
            raise ScheduleValidationError("days_of_week entries must be weekday names such as 'mon' or 'monday'.")
        out.add(_WEEKDAY_ALIASES[key])
    return tuple(sorted(out))


def validate_schedule_params(
    cadence: object,
    hour: object,
    minute: object = 0,
    days_of_week: object = None,
    timezone_name: object = DEFAULT_TIMEZONE,
) -> ScheduleSpec:
    if not isinstance(cadence, str) or cadence.strip().lower() not in CADENCES:
        raise ScheduleValidationError("cadence must be 'daily' or 'weekly'.")
    cad = cadence.strip().lower()
    if not _is_int(hour) or not 0 <= hour <= 23:
        raise ScheduleValidationError("hour must be an integer from 0 to 23 (24-hour clock, local time).")
    if not _is_int(minute) or not 0 <= minute <= 59:
        raise ScheduleValidationError("minute must be an integer from 0 to 59.")
    tz_name = validate_timezone(timezone_name if timezone_name is not None else DEFAULT_TIMEZONE)

    if cad == "weekly":
        days = parse_days(days_of_week)
    else:
        if days_of_week:
            raise ScheduleValidationError("days_of_week applies only to weekly schedules; use cadence 'weekly'.")
        days = ()
    return ScheduleSpec(cadence=cad, days_of_week=days, hour=hour, minute=minute, timezone=tz_name)


def spec_from_row(row: dict) -> ScheduleSpec:
    days = tuple(WEEKDAYS.index(d) for d in row["days_of_week"].split(",") if d)
    return ScheduleSpec(row["cadence"], days, row["hour"], row["minute"], row["timezone"])


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime not allowed")
    return dt.astimezone(timezone.utc)


def next_occurrence(spec: ScheduleSpec, after: datetime) -> datetime:
    """First scheduled instant strictly after `after`, as an aware UTC datetime."""
    after_utc = _as_utc(after)
    tz = spec.tz
    start = after_utc.astimezone(tz).date()
    for offset in range(-1, 9):  # a weekly cadence always matches within 7 days
        day = start + timedelta(days=offset)
        if spec.cadence == "weekly" and day.weekday() not in spec.days_of_week:
            continue
        # fold=0 resolves an ambiguous time to its first occurrence and a
        # nonexistent time to the wall-clock time just after the gap.
        local = datetime(day.year, day.month, day.day, spec.hour, spec.minute, tzinfo=tz, fold=0)
        candidate = local.astimezone(timezone.utc)
        if candidate > after_utc:
            return candidate
    raise RuntimeError("no occurrence found")  # unreachable for validated specs


def to_iso(dt: datetime | None) -> str | None:
    """Canonical UTC ISO-8601 string (lexicographically sortable)."""
    if dt is None:
        return None
    return _as_utc(dt).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def from_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def to_local_iso(dt: datetime | None, tz_name: str) -> str | None:
    if dt is None:
        return None
    return _as_utc(dt).astimezone(ZoneInfo(tz_name)).isoformat(timespec="seconds")
