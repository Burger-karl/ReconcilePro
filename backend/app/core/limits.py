"""Limits that protect the server itself (D-44, D-45).

1. LimitRequestSize: refuses request bodies over MAX_REQUEST_BYTES. Without it, anyone could send a
   multi-gigabyte upload: FastAPI would write it all to a temporary file (or memory) BEFORE our route
   code could check the size, filling the disk. It is plain ASGI middleware so it sees the bytes as
   they arrive, which also catches uploads sent without a Content-Length header ("chunked").

2. LoginAttempts: after too many wrong passwords for one email, that email is blocked for a while.
   Kept in memory: simple, and enough for the MVP's single server process. It resets on restart, and
   with several processes each would count separately; a shared store (Redis) would fix both later.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Statement uploads are at most 5 MB (statements/service.py); 6 MB leaves room for the multipart wrapping.
MAX_REQUEST_BYTES = 6 * 1024 * 1024


class RequestTooLarge(HTTPException):
    """Raised while the body is being read. An HTTPException, so FastAPI answers 413 itself; any other
    exception raised while FastAPI reads a body is turned into a vague 400."""

    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Request body is too large")


class LimitRequestSize:
    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Fast path: the client told us the size up front.
        for name, value in scope["headers"]:
            if name == b"content-length" and value.isdigit() and int(value) > self.max_bytes:
                await _send_413(send)
                return

        # Slow path: count the bytes as they arrive, in case Content-Length was missing or wrong.
        received = 0
        response_started = False

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise RequestTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except RequestTooLarge:
            # Normally FastAPI has already answered 413. This catches the rare case where nothing did.
            if not response_started:
                await _send_413(send)


async def _send_413(send: Send) -> None:
    body = b'{"detail":"Request body is too large"}'
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})


class LoginAttempts:
    """Counts failed logins per email in a sliding window."""

    def __init__(self, max_failures: int = 10, window_seconds: int = 15 * 60) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        # A clock that only goes forward (unlike the wall clock). Tests swap it for a fake one.
        self.clock = time.monotonic
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        # FastAPI runs normal (def) routes in a thread pool, so two requests can touch this at once.
        self._lock = Lock()

    def _recent(self, email: str, now: float) -> deque[float]:
        failures = self._failures[email]
        while failures and failures[0] <= now - self.window_seconds:
            failures.popleft()
        return failures

    def is_blocked(self, email: str) -> bool:
        with self._lock:
            blocked = len(self._recent(email, self.clock())) >= self.max_failures
            if not self._failures[email]:
                del self._failures[email]  # don't keep an entry for every email ever tried
            return blocked

    def record_failure(self, email: str) -> None:
        with self._lock:
            now = self.clock()
            self._recent(email, now).append(now)
            # Someone trying thousands of different emails must not grow this without end:
            # now and then, forget every email whose failures are all outside the window.
            if len(self._failures) > 10_000:
                for key in [key for key, times in self._failures.items() if times[-1] <= now - self.window_seconds]:
                    del self._failures[key]

    def clear(self, email: str) -> None:
        with self._lock:
            self._failures.pop(email, None)

    def reset(self) -> None:
        """Forget everything (tests)."""
        with self._lock:
            self._failures.clear()


login_attempts = LoginAttempts()
