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


def company_cards_payload() -> dict[str, object]:
    return {
        "currentCardIds": ["steady-compass", "precision-tool"],
        "desiredCardIds": ["springboard", "woven-network"],
        "explanation": "Today feels controlled; future needs more connected growth.",
    }


class CompanyCardsEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()

    def test_get_company_cards_defaults_to_empty_evidence(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "GET", f"/api/sessions/{created['id']}/identify/company-cards"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activity_id"], "company-cards")
        self.assertEqual(payload["content_status"], "prototype-config")
        self.assertIsNone(payload["evidence"])
        self.assertEqual(payload["progress"]["currentCount"], 0)

    def test_put_company_cards_saves_structured_evidence_with_provenance(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/company-cards",
            company_cards_payload(),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        evidence = payload["evidence"]
        self.assertEqual(payload["progress"]["currentCount"], 2)
        self.assertEqual(payload["progress"]["desiredCount"], 2)
        self.assertEqual(evidence["sourceActivity"], "company-cards")
        self.assertEqual(evidence["sourceLabel"], "Company Cards")
        self.assertIn("collectedAt", evidence)
        self.assertEqual(evidence["selections"][0]["state"], "current")
        self.assertEqual(evidence["selections"][2]["state"], "desired")

    def test_get_company_cards_returns_saved_evidence(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/company-cards",
            company_cards_payload(),
        )

        response = request(
            "GET", f"/api/sessions/{created['id']}/identify/company-cards"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["evidence"]["explanation"],
            company_cards_payload()["explanation"],
        )

    def test_put_company_cards_rejects_unknown_payload_fields(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        payload = company_cards_payload()
        payload["cardMeaningFormula"] = "invented"

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/company-cards",
            payload,
        )

        self.assertEqual(response.status_code, 422)

    def test_company_cards_missing_session_returns_not_found(self) -> None:
        response = request("GET", f"/api/sessions/{uuid4()}/identify/company-cards")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Assessment session not found.")


if __name__ == "__main__":
    unittest.main()
