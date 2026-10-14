import json


class CsvUploadLimitMiddleware:
    def __init__(self, app, max_file_bytes: int):
        self.app = app
        self.max_request_bytes = max_file_bytes + 64 * 1024

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") not in {
                "/transactions/import",
                "/transactions/import/preview",
            }
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_request_bytes:
                    await self._too_large(scope, receive, send)
                    return
            except ValueError:
                pass

        bytes_received = 0

        async def limited_receive():
            nonlocal bytes_received
            message = await receive()
            if message["type"] == "http.request":
                bytes_received += len(message.get("body", b""))
                if bytes_received > self.max_request_bytes:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            await self._too_large(scope, receive, send)

    @staticmethod
    async def _too_large(scope, receive, send):
        body = json.dumps(
            {"detail": "The CSV file exceeds the upload size limit."}
        ).encode("utf-8")
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


class _RequestBodyTooLarge(Exception):
    pass
