from pydantic import BaseModel


class ImportResult(BaseModel):
    bank: str  # which parser recognised the file
    rows_read: int  # money lines found (credits + debits)
    added: int  # new credit lines stored
    skipped_duplicates: int  # credit lines already imported before (invariant 2)
    settlements: int  # of the added lines, how many are Paystack settlements (invariant 6)
    debits_ignored: int  # money out; not stored in the MVP
