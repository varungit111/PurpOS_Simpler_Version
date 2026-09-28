import asyncio
import json
import unittest
from dataclasses import dataclass
from uuid import uuid4

from app.api import ai_detective
from app.main import app
from app.schemas.ai_detective import AIDetectiveGeneration
from app.schemas.assessment import ExternalResearchState
from app.services.ai_client import AIProviderError
from app.services.research import ResearchCollectionResult
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


class FakeAIClient:
    def generate_structured(
        self,
        prompt: str,
        output_schema: type[AIDetectiveGeneration],
        system: str | None = None,
    ) -> AIDetectiveGeneration:
        self.prompt = prompt
        self.system = system
        return output_schema(
            findings=[
                {
                    "topic": "Stakeholder signal",
                    "summary": (
                        "Clinic managers need reliable appointment flow, based "
                        "on SME-provided stakeholder input."
                    ),
                    "sourceType": "ai-synthesis",
                    "sourceLabel": "Who Matters? stakeholder map",
                    "sourceReference": "Synthesized from saved Identify session inputs.",
                }
            ]
        )


class FailingAIClient:
    def generate_structured(
        self,
        prompt: str,
        output_schema: type[AIDetectiveGeneration],
        system: str | None = None,
    ) -> AIDetectiveGeneration:
        raise AIProviderError("Provider unavailable for test.")


class CapturingResearchProvider:
    def __init__(self) -> None:
        self.organisation = None

    def collect(self, state, organisation=None, *, refresh=False):
        self.organisation = organisation
        generation = AIDetectiveGeneration(
            findings=[
                {
                    "topic": "Organisation context",
                    "summary": "Public website research found supplied context.",
                    "sourceType": "ai-synthesis",
                    "sourceLabel": "AI Detective",
                    "sourceReference": (
                        "Synthesized from saved Identify session inputs."
                    ),
                }
            ]
        )
        return ResearchCollectionResult(
            findings=generation.findings,
            status="connected",
            message="Captured.",
            external_research=ExternalResearchState(status="connected"),
        )


def research_payload() -> dict[str, object]:
    return {
        "topic": "Organisation context",
        "summary": "The team sells scheduling support to clinic operators.",
        "sourceType": "sme-provided",
        "sourceLabel": "Founder interview",
        "sourceReference": "Hot Seat note",
        "collectedAt": "2026-09-07T00:00:00Z",
    }


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


class AIDetectiveEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()
        self.original_create_ai_client = ai_detective.create_ai_client
        self.original_get_research_provider = ai_detective._get_research_provider

    def tearDown(self) -> None:
        ai_detective.create_ai_client = self.original_create_ai_client
        ai_detective._get_research_provider = self.original_get_research_provider

    def test_get_ai_detective_defaults_to_empty_review(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "GET", f"/api/sessions/{created['id']}/identify/ai-detective"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activity_id"], "ai-detective")
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["progress"]["findingsCount"], 0)
        self.assertEqual(payload["externalResearch"]["status"], "idle")

    def test_put_ai_detective_saves_valid_findings(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        finding_payload = research_payload()
        finding_payload["classification"] = "wrong"
        finding_payload["reviewNote"] = "This is not how customers describe us."

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/ai-detective",
            {"findings": [finding_payload]},
        )

        self.assertEqual(response.status_code, 200)
        finding = response.json()["findings"][0]
        self.assertEqual(finding["topic"], "Organisation context")
        self.assertEqual(finding["sourceType"], "sme-provided")
        self.assertEqual(finding["classification"], "wrong")
        self.assertEqual(
            finding["reviewNote"],
            "This is not how customers describe us.",
        )
        self.assertIn("id", finding)

        board = request(
            "GET",
            f"/api/sessions/{created['id']}/identify/board",
        ).json()
        ai_evidence = [
            item
            for item in request("GET", f"/api/sessions/{created['id']}/state")
            .json()["evidence"]
            if item["sourceActivity"] == "ai-detective"
        ]
        self.assertEqual(len(ai_evidence), 1)
        self.assertIn("vulnerabilities", ai_evidence[0]["coverageAreaIds"])
        activity_by_id = {
            item["activityId"]: item for item in board["activities"]
        }
        self.assertEqual(activity_by_id["ai-detective"]["status"], "completed")

    def test_collect_without_inputs_reports_live_research_limitation(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        ai_detective.create_ai_client = lambda: FakeAIClient()

        response = request(
            "POST", f"/api/sessions/{created['id']}/identify/ai-detective/collect"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["research_status"], "limited")
        self.assertEqual(payload["findings"], [])
        self.assertIn("No public website", payload["message"])
        self.assertEqual(payload["externalResearch"]["status"], "limited")
        self.assertIn(
            "First-party category coverage",
            payload["progress"]["limitation"],
        )
        self.assertIn(
            "Broader external search categories",
            payload["progress"]["limitation"],
        )

    def test_collect_uses_ai_client_when_identify_inputs_exist(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/stakeholders",
            {"stakeholders": [stakeholder_payload()]},
        )
        ai_detective.create_ai_client = lambda: FakeAIClient()

        response = request(
            "POST", f"/api/sessions/{created['id']}/identify/ai-detective/collect"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["research_status"], "connected")
        self.assertEqual(payload["findings"][0]["sourceType"], "ai-synthesis")

        saved = request(
            "GET", f"/api/sessions/{created['id']}/identify/ai-detective"
        ).json()
        self.assertEqual(saved["findings"][0]["topic"], "Stakeholder signal")
        state = request("GET", f"/api/sessions/{created['id']}/state").json()
        ai_evidence = next(
            item for item in state["evidence"]
            if item["sourceActivity"] == "ai-detective"
        )
        self.assertEqual(ai_evidence["evidenceStatus"], "ai-inferred")
        self.assertEqual(
            ai_evidence["sourceReference"],
            "Synthesized from saved Identify session inputs.",
        )

    def test_collect_uses_organisation_context_as_identify_input(self) -> None:
        fake_provider = CapturingResearchProvider()
        ai_detective._get_research_provider = lambda: fake_provider
        created = request(
            "POST",
            "/api/sessions",
            {
                "companyName": "Meridian Joinery",
                "website": "https://meridianjoinery.co.uk",
            },
        ).json()

        response = request(
            "POST", f"/api/sessions/{created['id']}/identify/ai-detective/collect"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["research_status"], "connected")
        self.assertEqual(fake_provider.organisation.company_name, "Meridian Joinery")
        self.assertEqual(
            str(fake_provider.organisation.website),
            "https://meridianjoinery.co.uk/",
        )

    def test_collect_failure_does_not_complete_ai_detective(self) -> None:
        ai_detective.create_ai_client = lambda: FailingAIClient()
        created = request(
            "POST",
            "/api/sessions",
            {"companyName": "Failure Test", "website": "https://example.com"},
        ).json()

        response = request(
            "POST", f"/api/sessions/{created['id']}/identify/ai-detective/collect"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["research_status"], "unavailable")
        self.assertEqual(response.json()["findings"], [])
        board = request(
            "GET", f"/api/sessions/{created['id']}/identify/board"
        ).json()
        activity = next(
            item
            for item in board["activities"]
            if item["activityId"] == "ai-detective"
        )
        self.assertEqual(activity["status"], "available")

    def test_put_ai_detective_rejects_unknown_source_type(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        finding = research_payload()
        finding["sourceType"] = "web"

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/ai-detective",
            {"findings": [finding]},
        )

        self.assertEqual(response.status_code, 422)

    def test_ai_detective_missing_session_returns_not_found(self) -> None:
        response = request("GET", f"/api/sessions/{uuid4()}/identify/ai-detective")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Assessment session not found.")


if __name__ == "__main__":
    unittest.main()
