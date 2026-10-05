"""Clock helpers, so "now" and "today" mean the same thing everywhere.

- Timestamps (created_at, sent_at) are stored in UTC.
- Calendar dates (due dates, "is it overdue?") use the date in Lagos, because that's where
  the business and its customers are. At 00:30 in Lagos it is still yesterday in UTC.
"""

from datetime import UTC, date, datetime, timedelta, timezone

# Nigeria is UTC+1 all year (no daylight saving), so a fixed offset is exact.
# (zoneinfo("Africa/Lagos") would need the tzdata package on Windows.)
LAGOS = timezone(timedelta(hours=1), name="Africa/Lagos")


def utc_now() -> datetime:
    return datetime.now(UTC)


def lagos_today() -> date:
    return datetime.now(LAGOS).date()
