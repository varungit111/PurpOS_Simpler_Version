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


def journey_payload(stakeholder_id: str) -> dict[str, object]:
    return {
        "stakeholderId": stakeholder_id,
        "stakeholderName": "Clinic managers",
        "touchpoints": [
            {
                "moment": "Booking setup",
                "expectations": [{"summary": "Clear onboarding"}],
                "observedExperiences": [
                    {
                        "summary": "Setup requires repeated clarification.",
                        "supportingEvidence": ["Founder interview note"],
                    }
                ],
                "painPoints": ["Too many manual checks"],
                "gaps": [{"summary": "Expectation for clarity exceeds current flow."}],
                "opportunities": [{"summary": "Create a setup checklist."}],
                "supportingEvidence": ["Who Matters? stakeholder map"],
            }
        ],
        "supportingEvidence": ["Mapped from stakeholder discussion"],
    }


class StakeholderJourneysEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()

    def test_journey_activity_is_locked_without_stakeholders(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "GET",
            f"/api/sessions/{created['id']}/identify/stakeholder-journeys",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activity_status"], "locked")
        self.assertEqual(payload["progress"]["stakeholderCount"], 0)
        self.assertIn("Who Matters", payload["dependency_message"])

    def test_locked_journey_activity_rejects_save(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholder-journeys",
            {"journeys": []},
        )

        self.assertEqual(response.status_code, 423)

    def test_journey_activity_unlocks_when_stakeholder_exists(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        stakeholder_response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholders",
            {"stakeholders": [stakeholder_payload()]},
        ).json()

        response = request(
            "GET",
            f"/api/sessions/{created['id']}/identify/stakeholder-journeys",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activity_status"], "available")
        self.assertIsNone(payload["dependency_message"])
        self.assertEqual(
            payload["stakeholders"][0]["id"],
            stakeholder_response["stakeholders"][0]["id"],
        )

    def test_put_journey_saves_structured_evidence_with_provenance(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        stakeholder = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholders",
            {"stakeholders": [stakeholder_payload()]},
        ).json()["stakeholders"][0]

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholder-journeys",
            {"journeys": [journey_payload(stakeholder["id"])]},
        )

        self.assertEqual(response.status_code, 200)
        journey = response.json()["journeys"][0]
        self.assertEqual(journey["sourceActivity"], "day-in-their-shoes")
        self.assertEqual(journey["sourceLabel"], "A Day in Their Shoes")
        self.assertEqual(journey["touchpoints"][0]["moment"], "Booking setup")
        self.assertIn("collectedAt", journey)

    def test_put_journey_rejects_unknown_stakeholder(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholders",
            {"stakeholders": [stakeholder_payload()]},
        )

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholder-journeys",
            {"journeys": [journey_payload(str(uuid4()))]},
        )

        self.assertEqual(response.status_code, 422)

    def test_journey_missing_session_returns_not_found(self) -> None:
        response = request(
            "GET",
            f"/api/sessions/{uuid4()}/identify/stakeholder-journeys",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Assessment session not found.")


if __name__ == "__main__":
    unittest.main()
