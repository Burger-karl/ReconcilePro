"""/api/statements routes."""

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.core.deps import CurrentUser, SessionDep
from app.statements import service
from app.statements.parsers.base import StatementError
from app.statements.schemas import ImportResult

router = APIRouter(prefix="/api/statements", tags=["Statements"])


@router.post("/import")
def import_statement(file: UploadFile, user: CurrentUser, session: SessionDep) -> ImportResult:
    # Read one byte more than the limit, so a too-big file is detected without reading all of it.
    content = file.file.read(service.MAX_FILE_BYTES + 1)
    try:
        return service.import_statement(session, user, file.filename or "", content)
    except service.FileTooLarge:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File is larger than 5 MB") from None
    except StatementError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from None
