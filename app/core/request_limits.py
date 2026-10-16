"""Límite de cuerpo también para transferencias sin Content-Length."""
from starlette.responses import JSONResponse

MAX_BODY = 6 * 1024 * 1024


class BodyTooLarge(Exception):
    pass


class RequestLimits:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = 262144 if scope.get("path", "").startswith("/mp/webhook") else MAX_BODY
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = limit + 1
        response = JSONResponse({"detail": "El archivo o la solicitud supera el tamaño permitido"}, status_code=413)
        if declared < 0 or declared > limit:
            return await response(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > limit:
                raise BodyTooLarge()
            return message

        try:
            await self.app(scope, bounded_receive, send)
        except BodyTooLarge:
            await response(scope, receive, send)
