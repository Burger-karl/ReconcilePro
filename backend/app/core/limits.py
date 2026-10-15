"""Limits that protect the server itself (D-44, D-45).

1. LimitRequestSize: refuses request bodies over MAX_REQUEST_BYTES. Without it, anyone could send a
   multi-gigabyte upload: FastAPI would write it all to a temporary file (or memory) BEFORE our route
   code could check the size, filling the disk. It is plain ASGI middleware so it sees the bytes as
   they arrive, which also catches uploads sent without a Content-Length header ("chunked").

2. LoginAttempts: after too many wrong passwords for one key, that key is blocked for a while. Two counters
   use it: one per email (D-42: guessing one account's password) and one per IP address (D-66: "password
   spraying", one common password tried against many accounts, which never trips a per-email limit).
   Kept in memory: simple, and enough for the MVP's single server process. It resets on restart, and
   with several processes each would count separately; a shared store (Redis) would fix both later.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

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
    """Counts failed logins per key (an email or an IP address) in a sliding window."""

    def __init__(self, max_failures: int = 10, window_seconds: int = 15 * 60) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        # A clock that only goes forward (unlike the wall clock). Tests swap it for a fake one.
        self.clock = time.monotonic
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        # FastAPI runs normal (def) routes in a thread pool, so two requests can touch this at once.
        self._lock = Lock()

    def _recent(self, key: str, now: float) -> deque[float]:
        failures = self._failures[key]
        while failures and failures[0] <= now - self.window_seconds:
            failures.popleft()
        return failures

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            blocked = len(self._recent(key, self.clock())) >= self.max_failures
            if not self._failures[key]:
                del self._failures[key]  # don't keep an entry for every key ever tried
            return blocked

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = self.clock()
            self._recent(key, now).append(now)
            # Someone trying thousands of different keys must not grow this without end:
            # now and then, forget every key whose failures are all outside the window.
            if len(self._failures) > 10_000:
                for key in [key for key, times in self._failures.items() if times[-1] <= now - self.window_seconds]:
                    del self._failures[key]

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def reset(self) -> None:
        """Forget everything (tests)."""
        with self._lock:
            self._failures.clear()


# 10 wrong passwords for one email in 15 minutes (D-42).
login_attempts = LoginAttempts()
# 30 failed logins from one IP address in 15 minutes, whatever the emails (D-66). Higher than the email
# limit because an office or mobile network can put many honest people behind one address.
login_ip_attempts = LoginAttempts(max_failures=30)


def client_ip(request: Request) -> str:
    """The address a request really came from, for the per-IP login limit (D-66).

    Behind a proxy (Render), every request arrives from the proxy's own address, so we read X-Forwarded-For
    instead. Each proxy APPENDS the address it received the request from, so the entry added by the proxy
    nearest the internet is counted from the right: with N trusted proxies it is the N-th from the end.
    Entries further left were written by the client and can be anything, so they are never used.
    """
    peer = request.client.host if request.client else "unknown"
    hops = settings.trusted_proxy_hops
    if hops == 0:
        return peer  # no proxy: the header, if any, came from the client and is ignored
    header = request.headers.get("x-forwarded-for", "")
    entries = [entry.strip() for entry in header.split(",") if entry.strip()]
    if len(entries) < hops:
        return peer  # not what our proxies would send; fall back to the connection's address
    return entries[-hops]
