import asyncio
import json
import unittest
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.api import signal_hunt
from app.main import app
from app.schemas.assessment import (
    ExternalResearchDocument,
    ExternalResearchState,
    ResearchFinding,
)
from app.schemas.signal_hunt import SignalHuntGeneration
from app.services.ai_client import AIProviderError, MissingAIAPIKeyError
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
        output_schema: type[SignalHuntGeneration],
        system: str | None = None,
    ) -> SignalHuntGeneration:
        self.prompt = prompt
        self.system = system
        return output_schema(
            findings=[
                {
                    "category": "technological",
                    "signal": "AI-enabled service expectations are rising",
                    "description": (
                        "Customers increasingly expect faster, more tailored "
                        "service interactions."
                    ),
                    "whyItMatters": (
                        "This may change what credible service quality looks "
                        "like in the category."
                    ),
                    "opportunityOrRisk": (
                        "Opportunity to improve responsiveness, with risk if "
                        "competitors move faster."
                    ),
                    "evidenceSources": [
                        {
                            "title": "Signal Hunt demo synthesis",
                            "sourceType": "AI analysis",
                            "url": None,
                            "summary": "Mock AI output used in API tests.",
                        }
                    ],
                }
            ]
        )


class EmptyAIClient(FakeAIClient):
    def generate_structured(
        self,
        prompt: str,
        output_schema: type[SignalHuntGeneration],
        system: str | None = None,
    ) -> SignalHuntGeneration:
        self.prompt = prompt
        self.system = system
        return output_schema(findings=[])


class FailingAIClient:
    def generate_structured(
        self,
        prompt: str,
        output_schema: type[SignalHuntGeneration],
        system: str | None = None,
    ) -> SignalHuntGeneration:
        raise AIProviderError("Provider unavailable for test.")


def signal_payload() -> dict[str, object]:
    return {
        "category": "environmental",
        "signal": "Sustainability expectations are becoming buying criteria",
        "description": (
            "Customers and partners are asking for clearer proof of "
            "environmental practice."
        ),
        "whyItMatters": (
            "The playbook identifies sustainability as a broad force affecting "
            "organisations."
        ),
        "opportunityOrRisk": (
            "Opportunity to strengthen trust, with reputational risk if claims "
            "are thin."
        ),
        "evidenceSources": [
            {
                "title": "CORE Playbook desk research note",
                "sourceType": "playbook",
                "url": None,
                "summary": "PESTLE supports external-environment review.",
            }
        ],
    }


class SignalHuntEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()
        self.original_create_ai_client = signal_hunt.create_ai_client

    def tearDown(self) -> None:
        signal_hunt.create_ai_client = self.original_create_ai_client

    def test_get_signal_hunt_defaults_to_empty_review(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "GET", f"/api/sessions/{created['id']}/identify/signal-hunt"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activity_id"], "signal-hunt")
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["progress"]["findingsCount"], 0)

    def test_put_signal_hunt_saves_valid_findings(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        finding_payload = signal_payload()
        finding_payload["decision"] = "opportunity"
        finding_payload["impact"] = 78
        finding_payload["urgency"] = 72

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/signal-hunt",
            {"findings": [finding_payload]},
        )

        self.assertEqual(response.status_code, 200)
        finding = response.json()["findings"][0]
        self.assertEqual(finding["category"], "environmental")
        self.assertEqual(finding["signal"], signal_payload()["signal"])
        self.assertEqual(finding["evidenceSources"][0]["sourceType"], "playbook")
        self.assertEqual(finding["decision"], "opportunity")
        self.assertEqual(finding["impact"], 78)
        self.assertEqual(finding["urgency"], 72)
        self.assertIn("id", finding)

        state = request("GET", f"/api/sessions/{created['id']}/state").json()
        signal_evidence = [
            item
            for item in state["evidence"]
            if item["sourceActivity"] == "signal-hunt"
        ]
        self.assertEqual(len(signal_evidence), 1)
        self.assertIn("environmental_context", signal_evidence[0]["coverageAreaIds"])

        board = request(
            "GET", f"/api/sessions/{created['id']}/identify/board"
        ).json()
        activity_by_id = {
            item["activityId"]: item for item in board["activities"]
        }
        self.assertEqual(activity_by_id["signal-hunt"]["status"], "completed")

    def test_unplaced_signal_hunt_findings_do_not_create_coverage(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/signal-hunt",
            {"findings": [signal_payload()]},
        )

        self.assertEqual(response.status_code, 200)
        state = request("GET", f"/api/sessions/{created['id']}/state").json()
        self.assertEqual(
            [
                item
                for item in state["evidence"]
                if item["sourceActivity"] == "signal-hunt"
            ],
            [],
        )
        board = request(
            "GET", f"/api/sessions/{created['id']}/identify/board"
        ).json()
        activity_by_id = {
            item["activityId"]: item for item in board["activities"]
        }
        self.assertEqual(activity_by_id["signal-hunt"]["status"], "conditional")

    def test_generate_signal_hunt_uses_ai_client_and_saves_findings(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        client = FakeAIClient()
        signal_hunt.create_ai_client = lambda: client

        response = request(
            "POST", f"/api/sessions/{created['id']}/identify/signal-hunt/generate"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["ai_status"], "connected")
        self.assertEqual(payload["progress"]["findingsCount"], 1)
        self.assertEqual(payload["findings"][0]["category"], "technological")

        saved = request(
            "GET", f"/api/sessions/{created['id']}/identify/signal-hunt"
        ).json()
        self.assertEqual(
            saved["findings"][0]["signal"],
            payload["findings"][0]["signal"],
        )
        self.assertEqual(
            set(category.value for category in signal_hunt.PESTLECategory),
            {
                "political",
                "economic",
                "social",
                "technological",
                "legal",
                "environmental",
            },
        )
        self.assertIn("without forcing one finding per category", client.prompt)

    def test_signal_hunt_receives_verified_identify_evidence_with_provenance(
        self,
    ) -> None:
        created = request("POST", "/api/sessions", {}).json()
        session_id = UUID(created["id"])
        source_reference = "source:spark-sustainability"
        session_store.update_identify_ai_detective_research(
            session_id,
            findings=[
                ResearchFinding(
                    topic="Company sustainability statement",
                    summary="Spark reports a goal to reduce operational emissions.",
                    sourceType="public-website",
                    sourceLabel="Spark sustainability page",
                    sourceReference=source_reference,
                    classification="interesting",
                )
            ],
            external_research=ExternalResearchState(
                status="connected",
                documents=[
                    ExternalResearchDocument(
                        id=source_reference,
                        sourceType="public-website",
                        category="sustainability-impact",
                        url="https://www.spark.co.nz/sustainability",
                        title="Spark sustainability page",
                        status="retrieved",
                        content="<html>RAW-SIGNAL-HUNT-MARKER</html>",
                    )
                ],
            ),
        )
        client = EmptyAIClient()
        signal_hunt.create_ai_client = lambda: client

        response = request(
            "POST", f"/api/sessions/{session_id}/identify/signal-hunt/generate"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["findings"], [])
        self.assertIn("Spark reports a goal", client.prompt)
        self.assertIn(source_reference, client.prompt)
        self.assertIn("https://www.spark.co.nz/sustainability", client.prompt)
        self.assertNotIn("RAW-SIGNAL-HUNT-MARKER", client.prompt)

    def test_signal_hunt_excludes_unverified_public_website_finding(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/ai-detective",
            {
                "findings": [
                    {
                        "topic": "Unverified website claim",
                        "summary": "UNVERIFIED-PUBLIC-WEBSITE-CLAIM",
                        "sourceType": "public-website",
                        "sourceLabel": "Unverified page",
                        "sourceReference": "source:not-retrieved",
                    }
                ]
            },
        )
        client = EmptyAIClient()
        signal_hunt.create_ai_client = lambda: client

        response = request(
            "POST", f"/api/sessions/{created['id']}/identify/signal-hunt/generate"
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("UNVERIFIED-PUBLIC-WEBSITE-CLAIM", client.prompt)

    def test_signal_hunt_does_not_fill_unsupported_categories(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        client = EmptyAIClient()
        signal_hunt.create_ai_client = lambda: client

        response = request(
            "POST", f"/api/sessions/{created['id']}/identify/signal-hunt/generate"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["progress"]["findingsCount"], 0)
        self.assertEqual(response.json()["progress"]["categoriesCovered"], [])

    def test_signal_hunt_ai_failure_keeps_existing_findings(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/signal-hunt",
            {"findings": [signal_payload()]},
        )
        signal_hunt.create_ai_client = lambda: FailingAIClient()

        response = request(
            "POST", f"/api/sessions/{created['id']}/identify/signal-hunt/generate"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ai_status"], "error")
        self.assertEqual(
            response.json()["findings"][0]["signal"], signal_payload()["signal"]
        )

    def test_signal_hunt_never_receives_evidence_from_another_assessment(self) -> None:
        first = request(
            "POST",
            "/api/sessions",
            {"companyName": "Spark NZ", "website": "https://www.spark.co.nz"},
        ).json()
        second = request(
            "POST",
            "/api/sessions",
            {"companyName": "Spark NZ", "website": "https://www.spark.co.nz"},
        ).json()
        request(
            "PUT",
            f"/api/sessions/{first['id']}/identify/ai-detective",
            {
                "findings": [
                    {
                        "topic": "Assessment A only",
                        "summary": "ASSESSMENT-A-SIGNAL-PRIVATE",
                        "sourceType": "sme-provided",
                        "sourceLabel": "Assessment A interview",
                        "sourceReference": "assessment-a-note",
                    }
                ]
            },
        )
        client = EmptyAIClient()
        signal_hunt.create_ai_client = lambda: client

        response = request(
            "POST", f"/api/sessions/{second['id']}/identify/signal-hunt/generate"
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("ASSESSMENT-A-SIGNAL-PRIVATE", client.prompt)

    def test_generate_signal_hunt_without_ai_key_keeps_existing_findings(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/signal-hunt",
            {"findings": [signal_payload()]},
        )
        signal_hunt.create_ai_client = lambda: (_ for _ in ()).throw(
            MissingAIAPIKeyError("missing")
        )

        response = request(
            "POST", f"/api/sessions/{created['id']}/identify/signal-hunt/generate"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["ai_status"], "unavailable")
        self.assertEqual(
            payload["findings"][0]["signal"],
            signal_payload()["signal"],
        )

    def test_put_signal_hunt_rejects_invalid_category(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        finding = signal_payload()
        finding["category"] = "competitive"

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/signal-hunt",
            {"findings": [finding]},
        )

        self.assertEqual(response.status_code, 422)

    def test_signal_hunt_missing_session_returns_not_found(self) -> None:
        response = request("GET", f"/api/sessions/{uuid4()}/identify/signal-hunt")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Assessment session not found.")


if __name__ == "__main__":
    unittest.main()
