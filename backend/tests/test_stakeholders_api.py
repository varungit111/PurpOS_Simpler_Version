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
        "name": "Clinic managers",
        "groupType": "customer",
        "internalOrExternal": "external",
        "relationship": "Primary buyer and daily sponsor",
        "importance": "high",
        "influence": "medium",
        "needs": ["Reliable appointment flow"],
        "expectations": ["Fast support"],
        "notes": "They feel missed appointments quickly.",
        "evidenceSource": "Who Matters?",
        "insight": "They need confidence in daily operations.",
        "evidence_ids": [],
    }


class StakeholderEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()

    def test_get_stakeholders_defaults_to_empty_map(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "GET", f"/api/sessions/{created['id']}/identify/stakeholders"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["activity_id"], "who-matters")
        self.assertEqual(response.json()["stakeholders"], [])

    def test_put_stakeholders_saves_valid_map(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholders",
            {"stakeholders": [stakeholder_payload()]},
        )

        self.assertEqual(response.status_code, 200)
        stakeholder = response.json()["stakeholders"][0]
        self.assertEqual(stakeholder["name"], "Clinic managers")
        self.assertEqual(stakeholder["groupType"], "customer")
        self.assertEqual(stakeholder["internalOrExternal"], "external")
        self.assertEqual(stakeholder["evidenceSource"], "Who Matters?")
        self.assertIn("id", stakeholder)

    def test_get_stakeholders_returns_saved_map(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholders",
            {"stakeholders": [stakeholder_payload()]},
        )

        response = request(
            "GET", f"/api/sessions/{created['id']}/identify/stakeholders"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["stakeholders"][0]["needs"],
            ["Reliable appointment flow"],
        )

    def test_put_stakeholders_rejects_invalid_structured_data(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        stakeholder = stakeholder_payload()
        stakeholder["importance"] = "urgent"

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholders",
            {"stakeholders": [stakeholder]},
        )

        self.assertEqual(response.status_code, 422)

    def test_stakeholders_missing_session_returns_not_found(self) -> None:
        response = request(
            "GET", f"/api/sessions/{uuid4()}/identify/stakeholders"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Assessment session not found.")


if __name__ == "__main__":
    unittest.main()
