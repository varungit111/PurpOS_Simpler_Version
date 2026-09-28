import asyncio
import json
import unittest
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.api import conversation
from app.main import app
from app.orchestrator.orchestrator import orchestrator
from app.schemas.assessment import (
    ExternalResearchDocument,
    ExternalResearchState,
    ResearchFinding,
)
from app.schemas.conversation import (
    AIConversationRecommendation,
    ConversationAction,
    StructuredEvidenceUpdate,
)
from app.services.ai_client import AIMessage, MissingAIAPIKeyError
from app.store.sessions import session_store


@dataclass(frozen=True)
class ASGIResponse:
    status_code: int
    body: bytes

    def json(self) -> dict[str, object]:
        return json.loads(self.body.decode("utf-8"))


class FakeAIClient:
    def __init__(self) -> None:
        self.prompt = ""

    def generate_text(self, prompt: str, system: str | None = None) -> str:
        return prompt

    def generate_structured(
        self,
        prompt: str,
        output_schema: type[AIConversationRecommendation],
        system: str | None = None,
    ) -> AIConversationRecommendation:
        self.prompt = prompt
        return output_schema(
            recommended_action=ConversationAction.ask_question,
            next_question="Who should we interview next?",
            structured_updates=[
                StructuredEvidenceUpdate(
                    field="stakeholder_insights",
                    value="Employees see faster clinic support as the key strength.",
                    confidence=0.75,
                    evidence_required=False,
                )
            ],
        )

    def chat(self, messages: list[AIMessage], system: str | None = None) -> str:
        return messages[-1].content


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


class ConversationEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()
        orchestrator.clear()
        self.original_create_ai_client = conversation.create_ai_client

    def tearDown(self) -> None:
        conversation.create_ai_client = self.original_create_ai_client

    def test_hot_seat_conversation_returns_assistant_message_and_progress(self) -> None:
        conversation.create_ai_client = lambda: FakeAIClient()
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "POST",
            f"/api/sessions/{created['id']}/conversation",
            {
                "activity_id": "hot-seat",
                "message": "Our employees say support speed is what customers value.",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["assistant_message"], "Who should we interview next?")
        self.assertEqual(payload["activity_id"], "hot-seat")
        self.assertEqual(payload["next_action"], "ask_question")
        self.assertEqual(payload["ai_status"], "connected")
        self.assertGreaterEqual(payload["progress"]["current"], 1)
        self.assertEqual(payload["evidence_updates"][0]["source"]["title"], "Hot Seat")

    def test_hot_seat_persists_structured_evidence_to_identify_state(self) -> None:
        conversation.create_ai_client = lambda: FakeAIClient()
        created = request("POST", "/api/sessions", {}).json()

        request(
            "POST",
            f"/api/sessions/{created['id']}/conversation",
            {
                "activity_id": "hot-seat",
                "message": "Our employees say support speed is what customers value.",
            },
        )
        state = request("GET", f"/api/sessions/{created['id']}/state").json()

        self.assertEqual(state["evidence"][0]["source"]["source_type"], "hot_seat")
        self.assertEqual(
            state["evidence"][0]["claim"],
            "Employees see faster clinic support as the key strength.",
        )
        self.assertEqual(
            state["output"]["evidence_references"][0],
            state["evidence"][0]["id"],
        )

    def test_hot_seat_receives_verified_ai_detective_evidence_without_raw_page(
        self,
    ) -> None:
        created = request("POST", "/api/sessions", {}).json()
        session_id = UUID(created["id"])
        source_reference = "source:spark-purpose"
        session_store.update_identify_ai_detective_research(
            session_id,
            findings=[
                ResearchFinding(
                    topic="Purpose commitment",
                    summary="Spark says digital equity is central to its purpose.",
                    sourceType="public-website",
                    sourceLabel="Spark purpose page",
                    sourceReference=source_reference,
                    classification="correct",
                )
            ],
            external_research=ExternalResearchState(
                status="connected",
                documents=[
                    ExternalResearchDocument(
                        id=source_reference,
                        sourceType="public-website",
                        category="leadership-values-purpose",
                        url="https://www.spark.co.nz/about/purpose",
                        title="Spark purpose page",
                        status="retrieved",
                        content="<html>RAW-WEBSITE-DOCUMENT-MARKER</html>",
                        snippet="Digital equity is central to Spark's purpose.",
                    )
                ],
            ),
        )
        orchestrator.clear()
        client = FakeAIClient()
        conversation.create_ai_client = lambda: client

        response = request(
            "POST",
            f"/api/sessions/{session_id}/conversation",
            {
                "activity_id": "hot-seat",
                "message": (
                    "We help New Zealand organisations connect through reliable "
                    "digital services and practical customer support."
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Spark says digital equity", client.prompt)
        self.assertIn(source_reference, client.prompt)
        self.assertIn("https://www.spark.co.nz/about/purpose", client.prompt)
        self.assertNotIn("RAW-WEBSITE-DOCUMENT-MARKER", client.prompt)

    def test_hot_seat_never_receives_evidence_from_another_assessment(self) -> None:
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
                        "summary": "ASSESSMENT-A-PRIVATE-EVIDENCE",
                        "sourceType": "sme-provided",
                        "sourceLabel": "Assessment A interview",
                        "sourceReference": "assessment-a-note",
                    }
                ]
            },
        )
        orchestrator.clear()
        client = FakeAIClient()
        conversation.create_ai_client = lambda: client

        response = request(
            "POST",
            f"/api/sessions/{second['id']}/conversation",
            {
                "activity_id": "hot-seat",
                "message": "We provide connectivity services to New Zealand customers.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("ASSESSMENT-A-PRIVATE-EVIDENCE", client.prompt)

    def test_conversation_missing_session_returns_not_found(self) -> None:
        response = request(
            "POST",
            f"/api/sessions/{uuid4()}/conversation",
            {"activity_id": "hot-seat", "message": "Hello from Hot Seat."},
        )

        self.assertEqual(response.status_code, 404)

    def test_conversation_rejects_unimplemented_activity(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "POST",
            f"/api/sessions/{created['id']}/conversation",
            {"activity_id": "signal-hunt", "message": "Run this one."},
        )

        self.assertEqual(response.status_code, 400)

    def test_missing_ai_key_uses_deterministic_fallback(self) -> None:
        conversation.create_ai_client = lambda: (_ for _ in ()).throw(
            MissingAIAPIKeyError()
        )
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "POST",
            f"/api/sessions/{created['id']}/conversation",
            {
                "activity_id": "hot-seat",
                "message": (
                    "We build scheduling software for regional clinics and help "
                    "managers reduce missed appointments."
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ai_status"], "unavailable")

        evidence = response.json()["evidence_updates"]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["sourceActivity"], "hot-seat")
        self.assertEqual(evidence[0]["evidenceStatus"], "user-confirmed")
        self.assertTrue(evidence[0]["sourceReference"].startswith("conversation-turn:"))

    def test_saved_activity_coverage_prevents_duplicate_hot_seat_question(self) -> None:
        conversation.create_ai_client = lambda: (_ for _ in ()).throw(
            MissingAIAPIKeyError()
        )
        created = request("POST", "/api/sessions", {}).json()
        request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/company-cards",
            {
                "currentCardIds": ["precision-tool"],
                "desiredCardIds": ["human-circle"],
                "explanation": "At our best, reliable support helps clinics choose us.",
            },
        )
        orchestrator.clear()

        response = request(
            "POST",
            f"/api/sessions/{created['id']}/conversation",
            {
                "activity_id": "hot-seat",
                "message": (
                    "We provide scheduling software to regional clinics and "
                    "help managers reduce missed appointments."
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            "What problem does the organisation solve when it is at its best?",
            response.json()["assistant_message"],
        )

    def test_hot_seat_cross_checks_saved_positioning_without_resetting_progress(self) -> None:
        conversation.create_ai_client = lambda: (_ for _ in ()).throw(
            MissingAIAPIKeyError()
        )
        created = request("POST", "/api/sessions", {}).json()
        session_id = created["id"]
        request(
            "PUT",
            f"/api/sessions/{session_id}/identify/where-do-you-stand",
            {
                "responses": [
                    {
                        "topic": "current-positioning",
                        "prompt": "How is the organisation positioned today?",
                        "response": "Our market position is premium quality support.",
                        "supportingEvidence": ["Leadership workshop"],
                    }
                ]
            },
        )
        orchestrator.clear()

        response = request(
            "POST",
            f"/api/sessions/{session_id}/conversation",
            {
                "activity_id": "hot-seat",
                "message": (
                    "Customers say our market position is the lowest-cost budget "
                    "option rather than premium support."
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["next_action"], "revisit_topic")
        session = request("GET", f"/api/sessions/{session_id}").json()
        findings = session["identify"]["output"]["cross_check_findings"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(len(findings[0]["evidenceIds"]), 2)
        self.assertIn("where-do-you-stand", findings[0]["sourceActivities"])
        self.assertTrue(session["identify"]["output"]["where_do_you_stand_evidence"])
        self.assertEqual(session["stage"], "identify")
        self.assertEqual(session["revisit_routes"][-1]["topic"], "positioning")

        gaps = request(
            "GET", f"/api/sessions/{session_id}/identify/perception-gaps"
        ).json()
        self.assertEqual(
            gaps["suggestedGaps"][0]["supportingEvidenceIds"],
            findings[0]["evidenceIds"],
        )

        wall = request(
            "GET", f"/api/sessions/{session_id}/identify/evidence-wall"
        ).json()
        cross_checks = next(
            group for group in wall["groups"] if group["id"] == "cross-checks"
        )
        self.assertEqual(
            cross_checks["cards"][0]["derivedFromEvidenceIds"],
            findings[0]["evidenceIds"],
        )


if __name__ == "__main__":
    unittest.main()
