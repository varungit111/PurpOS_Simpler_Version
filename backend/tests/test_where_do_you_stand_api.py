import asyncio
import json
import unittest
from dataclasses import dataclass
from uuid import UUID, uuid4

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


def where_do_you_stand_payload() -> dict[str, object]:
    return {
        "responses": [
            {
                "topic": "who-served",
                "prompt": "Who does the organisation primarily serve?",
                "response": "Clinic managers and operations teams.",
                "supportingEvidence": ["Who Matters? stakeholder map"],
            },
            {
                "topic": "distinctiveness",
                "prompt": "What feels distinctive compared with alternatives?",
                "response": "Fast operational support and practical setup help.",
                "supportingEvidence": ["AI Detective synthesis"],
            },
            {
                "topic": "social-contribution",
                "prompt": "What wider contribution is already visible?",
                "response": "Reduced appointment friction improves access to care.",
                "supportingEvidence": ["Signal Hunt finding"],
            },
        ]
    }


class WhereDoYouStandEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()

    def test_get_where_do_you_stand_defaults_to_empty_evidence(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "GET",
            f"/api/sessions/{created['id']}/identify/where-do-you-stand",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activity_id"], "where-do-you-stand")
        self.assertIsNone(payload["evidence"])
        self.assertEqual(payload["progress"]["responseCount"], 0)

    def test_put_saves_evidence_with_provenance(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/where-do-you-stand",
            where_do_you_stand_payload(),
        )

        self.assertEqual(response.status_code, 200)
        evidence = response.json()["evidence"]
        self.assertEqual(evidence["sourceActivity"], "where-do-you-stand")
        self.assertEqual(evidence["sourceLabel"], "Where Do You Stand?")
        self.assertEqual(len(evidence["responses"]), 3)
        self.assertIn("collectedAt", evidence)

    def test_put_populates_positioning_and_social_contribution_evidence(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/where-do-you-stand",
            where_do_you_stand_payload(),
        )

        actual = session_store.get_identify_state(UUID(str(created["id"])))
        self.assertIsNotNone(actual)
        assert actual is not None
        self.assertEqual(len(actual.output.positioning_evidence), 2)
        self.assertEqual(len(actual.output.social_contribution_evidence), 1)

    def test_put_rejects_empty_response_list(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/where-do-you-stand",
            {"responses": []},
        )

        self.assertEqual(response.status_code, 422)

    def test_put_does_not_generate_final_positioning_statement(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/where-do-you-stand",
            where_do_you_stand_payload(),
        )

        payload = response.json()
        self.assertNotIn("positioningStatement", payload)
        self.assertNotIn("finalPositioningStatement", payload)

    def test_where_do_you_stand_missing_session_returns_not_found(self) -> None:
        response = request(
            "GET",
            f"/api/sessions/{uuid4()}/identify/where-do-you-stand",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Assessment session not found.")
if __name__ == "__main__":
    unittest.main()
