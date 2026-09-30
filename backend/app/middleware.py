"""ASGI middleware that bounds request body size.

The declared Content-Length is checked first, and bodies that arrive without one
(chunked transfer) are buffered up to the limit before the request is handed on.
The buffered body is replayed through a synthetic receive channel so downstream
routers still see a complete, readable stream.
"""

from __future__ import annotations

import logging

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

BODYLESS_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "DELETE"})


class PayloadLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in BODYLESS_METHODS:
            await self.app(scope, receive, send)
            return

        declared = _declared_length(scope)
        if declared is not None and declared > self.max_bytes:
            logger.warning(
                "rejected request path=%s declared_bytes=%s limit=%s",
                scope.get("path"),
                declared,
                self.max_bytes,
            )
            await _send_too_large(send, self.max_bytes)
            return

        body, complete = await _read_body(receive, self.max_bytes)
        if not complete:
            logger.warning("rejected request path=%s reason=body_limit", scope.get("path"))
            await _send_too_large(send, self.max_bytes)
            return

        sent = False

        async def replay() -> Message:
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


def _declared_length(scope: Scope) -> int | None:
    for key, value in scope.get("headers", []):
        if key == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _read_body(receive: Receive, max_bytes: int) -> tuple[bytes, bool]:
    chunks: list[bytes] = []
    total = 0
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return b"", True
        chunk = message.get("body", b"")
        total += len(chunk)
        if total > max_bytes:
            return b"", False
        chunks.append(chunk)
        if not message.get("more_body", False):
            return b"".join(chunks), True


async def _send_too_large(send: Send, max_bytes: int) -> None:
    body = b'{"detail":"Payload exceeds limit"}'
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
