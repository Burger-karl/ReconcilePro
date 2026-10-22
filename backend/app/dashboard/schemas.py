"""Response bodies for /api/v1/dashboard. All money is integer kobo (invariant 1)."""

from datetime import date
from pydantic import BaseModel

from app.invoices.schemas import AgeingBucketName


class Summary(BaseModel):
    outstanding_kobo: int  # still owed on sent / part_paid / overdue invoices
    open_invoice_count: int
    collected_this_month_kobo: int  # matched to invoices, by the date the money arrived (Lagos month)
    # Whole percent of the last 30 days' matches made automatically; None when nothing was matched,
    # because "0%" would wrongly suggest auto-matching is failing.
    auto_match_rate: int | None
    needs_review_count: int  # credits with money not yet matched to an invoice


class WeekCollected(BaseModel):
    week_start: date  # a Monday
    collected_kobo: int


class AgeingBucket(BaseModel):
    bucket: AgeingBucketName
    outstanding_kobo: int
    count: int
