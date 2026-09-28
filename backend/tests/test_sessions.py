import asyncio
import json
import unittest
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.main import app
from app.schemas.assessment import (
    AssessmentSessionCreate,
    EvidenceSource,
    IdentifyEvidence,
)
from app.store.repository import InMemoryAssessmentRepository
from app.store.sessions import SessionStore, session_store


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


class SessionEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()

    def test_create_session_defaults_to_identify_stage(self) -> None:
        response = request("POST", "/api/sessions", {})

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        UUID(payload["id"])
        self.assertEqual(payload["stage"], "identify")
        self.assertIsNone(payload["organisation"]["companyName"])
        self.assertIn("ai-detective", payload["identify"]["activity_states"])
        self.assertEqual(len(payload["identify"]["playbook_coverage"]), 20)
        self.assertEqual(payload["identify"]["output"]["themes"], [])
        self.assertEqual(payload["identify"]["output"]["open_questions"], [])

    def test_create_session_accepts_organisation_context(self) -> None:
        response = request(
            "POST",
            "/api/sessions",
            {
                "companyName": "Meridian Joinery",
                "website": "https://meridianjoinery.co.uk",
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(
            payload["organisation"]["companyName"],
            "Meridian Joinery",
        )
        self.assertEqual(
            payload["organisation"]["website"],
            "https://meridianjoinery.co.uk/",
        )

    def test_create_session_rejects_unknown_stage(self) -> None:
        response = request("POST", "/api/sessions", {"stage": "complete"})

        self.assertEqual(response.status_code, 422)

    def test_create_session_rejects_stage_without_registered_config(self) -> None:
        response = request("POST", "/api/sessions", {"stage": "define"})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"],
            "The requested assessment stage is not implemented.",
        )

    def test_get_session_returns_created_session_for_resume(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request("GET", f"/api/sessions/{created['id']}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], created["id"])
        self.assertEqual(response.json()["stage"], "identify")
        self.assertEqual(response.json()["lifecycle_status"], "active")
        self.assertEqual(
            response.json()["stage_statuses"]["identify"],
            "in_progress",
        )

    def test_store_reinstantiation_preserves_state_in_repository(self) -> None:
        repository = InMemoryAssessmentRepository()
        first_store = SessionStore(repository)
        created = first_store.create(AssessmentSessionCreate())
        identify = first_store.get_identify_state(created.id)
        self.assertIsNotNone(identify)
        assert identify is not None
        evidence = IdentifyEvidence(
            source=EvidenceSource(title="Resume fixture", source_type="test"),
            claim="Customers value reliable delivery.",
            sourceActivity="hot-seat",
            coverageAreaIds=["customer_needs"],
        )
        first_store.update_identify_state(
            created.id,
            identify.output,
            [evidence],
        )

        reloaded_store = SessionStore(repository)
        reloaded = reloaded_store.get(created.id)

        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertEqual(reloaded.identify.evidence[0].id, evidence.id)
        self.assertGreater(reloaded.version, created.version)

    def test_get_session_state_returns_identify_state(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request("GET", f"/api/sessions/{created['id']}/state")

        self.assertEqual(response.status_code, 200)
        state = response.json()
        self.assertIn("output", state)
        self.assertEqual(state["evidence"], [])

    def test_get_identify_board_state_returns_backend_derived_foundation(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request("GET", f"/api/sessions/{created['id']}/identify/board")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activity_id"], "investigation-board")
        self.assertEqual(payload["confidence"]["overall"], 0)
        self.assertEqual(payload["confidence"]["totalAreas"], 20)
        self.assertEqual(len(payload["activities"]), 12)
        self.assertEqual(len(payload["playbookCoverage"]), 20)
        identify_brief = next(
            activity
            for activity in payload["activities"]
            if activity["activityId"] == "identify-brief"
        )
        self.assertEqual(identify_brief["status"], "locked")

    def test_activity_evidence_contributes_to_playbook_coverage(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        save_response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/company-cards",
            {
                "currentCardIds": ["clear-window"],
                "desiredCardIds": ["steady-compass"],
                "explanation": (
                    "Customers choose us for honest reliable work, and our "
                    "future purpose proof should connect decisions to goals."
                ),
            },
        )

        self.assertEqual(save_response.status_code, 200)
        state = request("GET", f"/api/sessions/{created['id']}/state").json()
        activity_evidence = [
            item
            for item in state["evidence"]
            if item["sourceActivity"] == "company-cards"
        ]
        self.assertEqual(len(activity_evidence), 1)
        self.assertIn(
            "purpose_driven_proof",
            activity_evidence[0]["coverageAreaIds"],
        )

        board = request(
            "GET",
            f"/api/sessions/{created['id']}/identify/board",
        ).json()
        coverage_by_area = {
            item["areaId"]: item["status"] for item in board["playbookCoverage"]
        }
        self.assertNotEqual(coverage_by_area["purpose_driven_proof"], "uncovered")
        self.assertGreater(board["confidence"]["overall"], 0)

    def test_playbook_coverage_tracks_uncovered_partial_and_sufficient(self) -> None:
        created = request("POST", "/api/sessions", {}).json()
        session_id = UUID(created["id"])
        state = session_store.get_identify_state(session_id)
        self.assertIsNotNone(state)
        assert state is not None

        source = EvidenceSource(title="Coverage fixture", source_type="test")
        updated = session_store.update_identify_state(
            session_id,
            state.output,
            [
                IdentifyEvidence(
                    source=source,
                    claim="Customers need more confidence during onboarding.",
                    sourceActivity="who-matters",
                    coverageAreaIds=["customer_needs"],
                ),
                IdentifyEvidence(
                    source=source,
                    claim="The offer is positioned around reliability.",
                    sourceActivity="where-do-you-stand",
                    coverageAreaIds=["market_position"],
                ),
                IdentifyEvidence(
                    source=source,
                    claim="Alternatives compete mainly on speed.",
                    sourceActivity="ai-detective",
                    coverageAreaIds=["market_position"],
                ),
            ],
        )

        self.assertIsNotNone(updated)
        board = request(
            "GET",
            f"/api/sessions/{created['id']}/identify/board",
        ).json()
        coverage_by_area = {
            item["areaId"]: item["status"] for item in board["playbookCoverage"]
        }
        self.assertEqual(coverage_by_area["customer_needs"], "partial")
        self.assertEqual(coverage_by_area["market_position"], "sufficient")
        self.assertEqual(coverage_by_area["founding_story"], "uncovered")

    def test_get_session_returns_not_found_for_unknown_uuid(self) -> None:
        response = request("GET", f"/api/sessions/{uuid4()}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Assessment session not found.")

    def test_get_session_rejects_invalid_uuid(self) -> None:
        response = request("GET", "/api/sessions/not-a-uuid")

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
