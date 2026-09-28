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


def stakeholder_payload() -> dict[str, object]:
    return {
        "name": "Loyal customers",
        "groupType": "customer",
        "internalOrExternal": "external",
        "relationship": "Repeat buyers and referral source",
        "importance": "high",
        "influence": "medium",
        "needs": ["Reliable delivery", "Honest advice"],
        "expectations": ["Clear communication"],
        "notes": "Customers value trust and reliability.",
        "evidenceSource": "Who Matters?",
        "insight": "They reward dependable service.",
        "evidence_ids": [],
    }


class ListenSummaryEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()

    def test_listen_summary_synthesizes_saved_listen_evidence(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholders",
            {"stakeholders": [stakeholder_payload()]},
        )
        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/company-cards",
            {
                "currentCardIds": ["steady-compass"],
                "desiredCardIds": ["clear-window"],
                "explanation": (
                    "Customers choose honest reliable advice and want purpose "
                    "proof in future decisions."
                ),
            },
        )

        response = request(
            "GET", f"/api/sessions/{created['id']}/identify/listen-summary"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activity_id"], "listen-summary")
        self.assertEqual(payload["stakeholderCount"], 1)
        self.assertEqual(payload["companyCardsCount"], 2)
        self.assertGreaterEqual(payload["evidenceCount"], 2)
        self.assertGreaterEqual(len(payload["areasMoved"]), 1)
        self.assertGreaterEqual(len(payload["quotes"]), 1)

        board = request(
            "GET", f"/api/sessions/{created['id']}/identify/board"
        ).json()
        activity_by_id = {
            item["activityId"]: item for item in board["activities"]
        }
        self.assertIn(
            activity_by_id["listen-summary"]["status"],
            {"available", "completed"},
        )

    def test_listen_summary_missing_session_returns_not_found(self) -> None:
        response = request(
            "GET", f"/api/sessions/{uuid4()}/identify/listen-summary"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Assessment session not found.")


if __name__ == "__main__":
    unittest.main()
