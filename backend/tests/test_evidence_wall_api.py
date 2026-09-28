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
        "relationship": "Primary buyer",
        "importance": "high",
        "influence": "medium",
        "needs": ["Reliable appointment flow"],
        "expectations": ["Fast support"],
        "notes": "They need clear support at quote and onboarding.",
        "evidenceSource": "Who Matters?",
        "insight": "Customers need confidence in daily operations.",
        "evidence_ids": [],
    }


class EvidenceWallEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()

    def test_evidence_wall_groups_existing_identify_evidence_by_coverage(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholders",
            {"stakeholders": [stakeholder_payload()]},
        )

        response = request(
            "GET",
            f"/api/sessions/{created['id']}/identify/evidence-wall",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activity_id"], "evidence-wall")
        self.assertGreaterEqual(payload["evidenceCount"], 1)
        self.assertTrue(
            any(group["id"] == "customer_needs" for group in payload["groups"])
        )
        customer_group = next(
            group for group in payload["groups"] if group["id"] == "customer_needs"
        )
        self.assertEqual(customer_group["cards"][0]["evidenceStatus"], "user-confirmed")

    def test_evidence_wall_save_rejects_unknown_group(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/evidence-wall",
            {"selectedGroupIds": ["missing-group"]},
        )

        self.assertEqual(response.status_code, 422)

    def test_evidence_wall_save_updates_themes_and_board_activity(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholders",
            {"stakeholders": [stakeholder_payload()]},
        )

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/evidence-wall",
            {"selectedGroupIds": ["customer_needs"]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selectedThemes"][0]["name"], "Customer needs")

        board = request(
            "GET",
            f"/api/sessions/{created['id']}/identify/board",
        ).json()
        activity_by_id = {
            item["activityId"]: item for item in board["activities"]
        }
        self.assertEqual(activity_by_id["evidence-wall"]["status"], "completed")

    def test_evidence_wall_missing_session_returns_not_found(self) -> None:
        response = request(
            "GET",
            f"/api/sessions/{uuid4()}/identify/evidence-wall",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Assessment session not found.")


if __name__ == "__main__":
    unittest.main()
