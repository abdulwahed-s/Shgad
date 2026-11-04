"""Local-only access, bounded request buffering and value-free trace logging.

Socket peers are authoritative: forwarded headers never grant access. Remote
hosting requires a separately reviewed authentication design before deployment.
"""

import asyncio
import logging
import os
import re
from collections import defaultdict, deque
from ipaddress import ip_address
from time import monotonic
from uuid import uuid4

from app.api.errors import _error

ORIGIN = re.compile(r"https?://(?:localhost|127\.0\.0\.1)(?::[0-9]+)?")
HOST = re.compile(r"(?:localhost|127\.0\.0\.1|\[::1\])(?::[0-9]+)?")
MAX_BODY_BYTES = 6 * 1024 * 1024
MAX_JSON_BYTES = 64 * 1024
BODY_TIMEOUT_SECONDS = 15
LIMITS = {"chat": 10, "import": 20, "other": 240}
_windows = defaultdict(deque)
logger = logging.getLogger("shgad.requests")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


class RequestSafety:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started, trace = monotonic(), uuid4().hex
        status, response_started = 500, False
        headers = dict(scope.get("headers", []))

        async def traced_send(message):
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-request-id", trace.encode())
                ]
            await send(message)

        async def reject(code, status_code):
            response = _error(code, status_code)
            if status_code == 429:
                response.headers["Retry-After"] = "60"
            await response(scope, receive, traced_send)

        try:
            peer = (scope.get("client") or ("", 0))[0]
            try:
                local = ip_address(peer).is_loopback
            except ValueError:
                local = os.environ.get("APP_ENV") == "test" and peer == "testclient"
            host = headers.get(b"host", b"").decode("latin1")
            test_host = os.environ.get("APP_ENV") == "test" and host in {
                "test",
                "testserver",
                "testserver:80",
            }
            origin = headers.get(b"origin")
            if (
                not local
                or not (HOST.fullmatch(host) or test_host)
                or (
                    origin is not None and not ORIGIN.fullmatch(origin.decode("latin1"))
                )
            ):
                return await reject("VALIDATION_ERROR", 403)
            path = scope.get("path", "")
            group = (
                "chat"
                if path in {"/api/chat", "/api/collections/draft"}
                else "import"
                if path.startswith("/api/imports")
                else "other"
            )
            if scope["method"] != "OPTIONS":
                window = _windows[(peer, group)]
                while window and window[0] <= started - 60:
                    window.popleft()
                if len(window) >= LIMITS[group]:
                    return await reject("VALIDATION_ERROR", 429)
                window.append(started)
            limit = (
                MAX_BODY_BYTES if path.startswith("/api/imports") else MAX_JSON_BYTES
            )
            length = headers.get(b"content-length", b"0")
            if not length.isdigit():
                return await reject("VALIDATION_ERROR", 400)
            if len(length) > 10 or int(length) > limit:
                return await reject("VALIDATION_ERROR", 413)
            body = bytearray()
            try:
                async with asyncio.timeout(BODY_TIMEOUT_SECONDS):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > limit:
                            return await reject("VALIDATION_ERROR", 413)
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                return await reject("VALIDATION_ERROR", 408)

            async def buffered_receive():
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            try:
                await self.app(scope, buffered_receive, traced_send)
            except Exception:
                if not response_started:
                    await reject("INTERNAL", 500)
        finally:
            # Never record paths, query strings, headers, bodies or exception text.
            logger.info(
                "request_id=%s status=%s duration_ms=%s",
                trace,
                status,
                int((monotonic() - started) * 1000),
            )
