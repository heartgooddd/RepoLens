"""Cap import bodies before JSON parsing; reject cross-site writes."""

import asyncio

from starlette.responses import JSONResponse

from .import_policy import MAX_BODY

ORIGINS = [f"http://{host}:{port}" for host in ("127.0.0.1", "localhost") for port in (5173, 5174, 4173, 8000)]


class ImportBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != "/api/projects/import":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])

        async def reject(status, code, message):
            await JSONResponse({"detail": {"code": code, "message": message}}, status_code=status)(scope, receive, send)

        if headers.get(b"origin") and headers[b"origin"].decode() not in ORIGINS:
            return await reject(403, "origin_rejected", "不允许此来源导入项目。")
        if headers.get(b"content-type", b"").split(b";", 1)[0].lower() != b"application/json":
            return await reject(415, "invalid_content_type", "导入请求必须是 application/json。")
        body = bytearray()
        try:
            async with asyncio.timeout(30):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > MAX_BODY:
                        return await reject(413, "request_too_large", "上传请求超过 12 MiB 限制。")
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await reject(408, "upload_timeout", "上传超时，请缩小目录后重试。")
        delivered = False

        async def limited_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, limited_receive, send)
