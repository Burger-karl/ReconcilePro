"""Dashboard numbers. Read-only: nothing here writes anything.

Every number is derived from stored rows, never stored itself (invariant 5):
- what is owed comes from invoices + non-reversed allocations (invoices.open_invoices),
- what was collected comes from non-reversed allocations, dated by when the money arrived
  (the bank line's value_date), so a payment matched today for last month counts in last month.
Every query filters by the caller's workspace (invariant 8). Definitions: DECISIONS D-48.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import BigInteger, cast
from sqlmodel import Session, func, select

from app.allocations.models import PaymentAllocation
from app.core.time import lagos_today, utc_now
from app.dashboard.schemas import AgeingBucket, AgeingBucketName, Summary, WeekCollected
from app.invoices import service as invoices
from app.reconciliation import service as reconciliation
from app.transactions.models import Transaction

AUTO_MATCH_WINDOW_DAYS = 30


def _collected_by_day(session: Session, workspace_id: uuid.UUID, start: date, end: date) -> dict[date, int]:
    """Kobo matched to invoices per value date, start..end inclusive. Reversed allocations don't count."""
    # SUM() of BIGINT comes back as NUMERIC (a Decimal in Python); cast back so money stays int (invariant 1).
    total = cast(func.sum(PaymentAllocation.amount_kobo), BigInteger)
    rows = session.exec(
        select(Transaction.value_date, total)
        .join(Transaction, Transaction.id == PaymentAllocation.transaction_id)
        .where(
            PaymentAllocation.workspace_id == workspace_id,
            Transaction.workspace_id == workspace_id,
            PaymentAllocation.reversed_at.is_(None),
            Transaction.value_date >= start,
            Transaction.value_date <= end,
        )
        .group_by(Transaction.value_date)
    ).all()
    return {value_date: amount for value_date, amount in rows}


def _auto_match_rate(session: Session, workspace_id: uuid.UUID) -> int | None:
    """Share of the last 30 days' (non-reversed) allocations that the system made, as a whole percent."""
    rows = session.exec(
        select(PaymentAllocation.method, func.count())
        .where(
            PaymentAllocation.workspace_id == workspace_id,
            PaymentAllocation.reversed_at.is_(None),
            PaymentAllocation.created_at >= utc_now() - timedelta(days=AUTO_MATCH_WINDOW_DAYS),
        )
        .group_by(PaymentAllocation.method)
    ).all()
    counts = dict(rows)
    total = sum(counts.values())
    if total == 0:
        return None
    return round(100 * counts.get("auto", 0) / total)


def summary(session: Session, workspace_id: uuid.UUID) -> Summary:
    today = lagos_today()
    open_invoices = invoices.open_invoices(session, workspace_id)
    collected = _collected_by_day(session, workspace_id, today.replace(day=1), today)
    return Summary(
        outstanding_kobo=sum(invoice.outstanding_kobo for invoice in open_invoices),
        open_invoice_count=len(open_invoices),
        collected_this_month_kobo=sum(collected.values()),
        auto_match_rate=_auto_match_rate(session, workspace_id),
        needs_review_count=reconciliation.needs_review_count(session, workspace_id),
    )


def collections(session: Session, workspace_id: uuid.UUID, weeks: int) -> list[WeekCollected]:
    """Money collected per week (Monday to Sunday, Lagos dates), oldest first, ending with this week.

    Weeks with no money are included as 0, so the chart has no gaps.
    """
    today = lagos_today()
    this_monday = today - timedelta(days=today.weekday())  # weekday(): Monday is 0
    first_monday = this_monday - timedelta(weeks=weeks - 1)
    per_week: dict[date, int] = defaultdict(int)
    for value_date, amount in _collected_by_day(session, workspace_id, first_monday, today).items():
        per_week[value_date - timedelta(days=value_date.weekday())] += amount
    return [
        WeekCollected(week_start=monday, collected_kobo=per_week[monday])
        for monday in (first_monday + timedelta(weeks=n) for n in range(weeks))
    ]


def _bucket(days_late: int) -> AgeingBucketName:
    if days_late <= 0:
        return "current"  # not due yet, or due today
    if days_late <= 30:
        return "1_30"
    if days_late <= 60:
        return "31_60"
    return "60_plus"


def ageing(session: Session, workspace_id: uuid.UUID) -> list[AgeingBucket]:
    """What is still owed, grouped by how many days past its due date (Lagos today). All four buckets always."""
    today = lagos_today()
    names: tuple[AgeingBucketName, ...] = ("current", "1_30", "31_60", "60_plus")
    outstanding = dict.fromkeys(names, 0)
    count = dict.fromkeys(names, 0)
    for invoice in invoices.open_invoices(session, workspace_id):
        name = _bucket((today - invoice.due_date).days)
        outstanding[name] += invoice.outstanding_kobo
        count[name] += 1
    return [AgeingBucket(bucket=name, outstanding_kobo=outstanding[name], count=count[name]) for name in names]
