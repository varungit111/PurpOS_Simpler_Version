import asyncio
import unittest

from app.main import app


class ASGIResponse:
    def __init__(
        self, status_code: int, body: bytes, headers: list[tuple[bytes, bytes]]
    ) -> None:
        self.status_code = status_code
        self.body = body
        self.headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in headers
        }


def options(path: str, origin: str) -> ASGIResponse:
    return asyncio.run(_options(path, origin))


async def _options(path: str, origin: str) -> ASGIResponse:
    messages: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, object]) -> None:
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "OPTIONS",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": [
                (b"origin", origin.encode("ascii")),
                (b"access-control-request-method", b"POST"),
                (b"access-control-request-headers", b"content-type"),
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )

    status_code = 500
    response_body = b""
    response_headers: list[tuple[bytes, bytes]] = []
    for message in messages:
        if message["type"] == "http.response.start":
            status_code = int(message["status"])
            response_headers = list(message.get("headers", []))
        if message["type"] == "http.response.body":
            response_body += message.get("body", b"")

    return ASGIResponse(status_code, response_body, response_headers)


class CorsTests(unittest.TestCase):
    def test_sessions_preflight_accepts_localhost_frontend(self) -> None:
        response = options("/api/sessions", "http://localhost:3000")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:3000",
        )
        self.assertEqual(response.headers["access-control-allow-credentials"], "true")

    def test_sessions_preflight_accepts_next_fallback_dev_port(self) -> None:
        response = options("/api/sessions", "http://localhost:3001")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:3001",
        )

    def test_sessions_preflight_accepts_127_frontend(self) -> None:
        response = options("/api/sessions", "http://127.0.0.1:3000")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://127.0.0.1:3000",
        )

    def test_sessions_preflight_accepts_private_lan_frontend_in_development(
        self,
    ) -> None:
        response = options("/api/sessions", "http://192.168.1.20:3000")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://192.168.1.20:3000",
        )

    def test_sessions_preflight_rejects_untrusted_origin(self) -> None:
        response = options("/api/sessions", "http://example.com")

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
