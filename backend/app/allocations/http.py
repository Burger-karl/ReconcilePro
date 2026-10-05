"""Turn allocation errors into HTTP responses. Shared by every route that moves money,
so the same problem always gets the same status code and message."""

from fastapi import HTTPException, status

from app.allocations import service


def to_http(error: service.AllocationError) -> HTTPException:
    if isinstance(error, service.AllocationNotFound):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, (service.OverAllocated, service.AllocationAlreadyReversed)):
        code = status.HTTP_409_CONFLICT  # allowed in general, but not in the current state
    else:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=str(error))
