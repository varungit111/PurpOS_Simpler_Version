import asyncio
import json
import unittest
from dataclasses import dataclass
from uuid import uuid4

from app.main import app
from app.store.sessions import session_store


@dataclass(frozen=True)
class ASGIResponse:
    status_code: int
    body: bytes

    def json(self) -> dict[str, object]:
        return json.loads(self.body.decode("utf-8"))


def request(
    method: str, path: str, body: dict[str, object] | None = None
) -> ASGIResponse:
    return asyncio.run(_request(method, path, body))


async def _request(
    method: str, path: str, body: dict[str, object] | None = None
) -> ASGIResponse:
    request_body = b"" if body is None else json.dumps(body).encode("utf-8")
    messages: list[dict[str, object]] = []

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": request_body, "more_body": False}

    async def send(message: dict[str, object]) -> None:
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )

    status_code = 500
    response_body = b""
    for message in messages:
        if message["type"] == "http.response.start":
            status_code = int(message["status"])
        if message["type"] == "http.response.body":
            response_body += message.get("body", b"")

    return ASGIResponse(status_code=status_code, body=response_body)


def research_payload() -> dict[str, object]:
    return {
        "topic": "Customer trust",
        "summary": "Customers choose the team for reliable plain-language advice.",
        "sourceType": "sme-provided",
        "sourceLabel": "Founder note",
        "sourceReference": "Discovery input",
        "classification": "correct",
        "reviewNote": "Useful identity proof.",
        "collectedAt": "2026-09-07T00:00:00Z",
    }


class DiscoverSynthesisEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()

    def test_generate_discover_synthesis_uses_reviewed_discover_evidence(
        self,
    ) -> None:
        created = request("POST", "/api/sessions", {}).json()
        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/ai-detective",
            {"findings": [research_payload()]},
        )

        response = request(
            "POST",
            f"/api/sessions/{created['id']}/identify/discover-synthesis/generate",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activity_id"], "discover-synthesis")
        self.assertIn("reliable plain-language advice", payload["statement"])
        self.assertEqual(payload["progress"]["evidenceCount"], 1)

        state = request("GET", f"/api/sessions/{created['id']}/state").json()
        synthesis_evidence = [
            item
            for item in state["evidence"]
            if item["sourceActivity"] == "discover-synthesis"
        ]
        self.assertEqual(len(synthesis_evidence), 1)
        self.assertIn("market_position", synthesis_evidence[0]["coverageAreaIds"])

        board = request(
            "GET", f"/api/sessions/{created['id']}/identify/board"
        ).json()
        activity_by_id = {
            item["activityId"]: item for item in board["activities"]
        }
        self.assertEqual(activity_by_id["discover-synthesis"]["status"], "completed")

    def test_discover_synthesis_missing_session_returns_not_found(self) -> None:
        response = request(
            "GET", f"/api/sessions/{uuid4()}/identify/discover-synthesis"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Assessment session not found.")


if __name__ == "__main__":
    unittest.main()
