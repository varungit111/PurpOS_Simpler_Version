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
        "notes": "Customers need clear support through quote and onboarding.",
        "evidenceSource": "Who Matters?",
        "insight": "Customers need confidence in daily operations.",
        "evidence_ids": [],
    }


def journey_payload(stakeholder_id: str) -> dict[str, object]:
    return {
        "stakeholderId": stakeholder_id,
        "stakeholderName": "Clinic managers",
        "touchpoints": [
            {
                "moment": "Getting a quote",
                "expectations": [{"summary": "Clear quote process"}],
                "observedExperiences": [
                    {
                        "summary": "The quote took nine days and felt painful.",
                        "supportingEvidence": ["Journey note"],
                    }
                ],
                "painPoints": ["Quote took nine days"],
                "gaps": [{"summary": "Quote speed and care need more proof."}],
                "opportunities": [{"summary": "Create a quote checklist."}],
                "supportingEvidence": ["A Day in Their Shoes"],
            }
        ],
        "supportingEvidence": ["Journey mapping"],
    }


def complete_identify_inputs() -> str:
    created = request("POST", "/api/sessions", {"companyName": "Meridian"}).json()
    session_id = str(created["id"])
    stakeholder = request(
        "PUT",
        f"/api/sessions/{session_id}/identify/stakeholders",
        {"stakeholders": [stakeholder_payload()]},
    ).json()["stakeholders"][0]
    request(
        "PUT",
        f"/api/sessions/{session_id}/identify/ai-detective",
        {
            "findings": [
                {
                    "topic": "Customer experience",
                    "summary": "Meridian is known for reliable clinic operations support.",
                    "sourceType": "sme-provided",
                    "sourceLabel": "AI Detective review",
                    "classification": "correct",
                    "reviewNote": "Use as Discover evidence.",
                }
            ]
        },
    )
    request(
        "PUT",
        f"/api/sessions/{session_id}/identify/company-cards",
        {
            "currentCardIds": ["precision-tool"],
            "desiredCardIds": ["human-circle"],
            "explanation": "Efficient delivery is clear, but the human experience needs proof.",
        },
    )
    request(
        "POST",
        f"/api/sessions/{session_id}/identify/discover-synthesis/generate",
    )
    request(
        "PUT",
        f"/api/sessions/{session_id}/identify/stakeholder-journeys",
        {"journeys": [journey_payload(stakeholder["id"])]},
    )
    request(
        "PUT",
        f"/api/sessions/{session_id}/identify/where-do-you-stand",
        {
            "responses": [
                {
                    "topic": "current-positioning",
                    "prompt": "How is the organisation positioned today?",
                    "response": "Today the organisation leads with Offer.",
                    "supportingEvidence": ["Positioning spectrum"],
                },
                {
                    "topic": "social-contribution",
                    "prompt": "What wider contribution is already visible?",
                    "response": "Contribution level: Shared value.",
                    "supportingEvidence": ["Contribution ladder"],
                },
            ]
        },
    )
    suggested_gaps = request(
        "GET",
        f"/api/sessions/{session_id}/identify/perception-gaps",
    ).json()["suggestedGaps"]
    if suggested_gaps:
        suggested_gaps[0]["resolution"] = "clarified"
        suggested_gaps[0]["clarificationNeeded"] = False
        suggested_gaps[0]["resolutionNote"] = (
            "The efficient internal process and painful customer quote journey "
            "refer to different parts of the experience."
        )
        request(
            "PUT",
            f"/api/sessions/{session_id}/identify/perception-gaps",
            {"gaps": [suggested_gaps[0]]},
        )
    evidence_wall = request(
        "GET",
        f"/api/sessions/{session_id}/identify/evidence-wall",
    ).json()
    request(
        "PUT",
        f"/api/sessions/{session_id}/identify/evidence-wall",
        {"selectedGroupIds": [evidence_wall["groups"][0]["id"]]},
    )
    return session_id


class IdentifyBriefEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()

    def test_empty_identify_brief_is_not_ready_for_handoff(self) -> None:
        created = request("POST", "/api/sessions", {"companyName": "Meridian"}).json()

        response = request(
            "GET",
            f"/api/sessions/{created['id']}/identify/brief",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activity_id"], "identify-brief")
        self.assertFalse(payload["readiness"]["isReady"])
        self.assertIn("Discover evidence", payload["readiness"]["missing"])

    def test_identify_brief_synthesizes_cross_stage_evidence(self) -> None:
        session_id = complete_identify_inputs()

        response = request(
            "GET",
            f"/api/sessions/{session_id}/identify/brief",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["readiness"]["isReady"])
        self.assertGreater(payload["sourceBreakdown"]["discover"], 0)
        self.assertGreater(payload["sourceBreakdown"]["listen"], 0)
        self.assertGreater(payload["sourceBreakdown"]["understand"], 0)
        self.assertGreater(len(payload["themes"]), 0)
        self.assertGreater(len(payload["strongestEvidence"]), 0)
        self.assertIn("evidenceStatus", payload["strongestEvidence"][0])
        self.assertIn("derivedFromEvidenceIds", payload["strongestEvidence"][0])
        self.assertIn("Meridian", payload["statement"])

    def test_board_keeps_identify_brief_locked_until_evidence_wall_theme(self) -> None:
        created = request("POST", "/api/sessions", {"companyName": "Meridian"}).json()
        session_id = str(created["id"])
        request(
            "PUT",
            f"/api/sessions/{session_id}/identify/company-cards",
            {
                "currentCardIds": ["precision-tool"],
                "desiredCardIds": ["human-circle"],
                "explanation": "The human experience still needs proof.",
            },
        )

        response = request(
            "GET",
            f"/api/sessions/{session_id}/identify/board",
        )

        self.assertEqual(response.status_code, 200)
        identify_brief = next(
            activity
            for activity in response.json()["activities"]
            if activity["activityId"] == "identify-brief"
        )
        self.assertEqual(identify_brief["status"], "locked")

    def test_brief_open_questions_include_unresolved_gaps_or_coverage_gaps(self) -> None:
        session_id = complete_identify_inputs()

        response = request(
            "GET",
            f"/api/sessions/{session_id}/identify/brief",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(len(payload["openQuestions"]), 1)
        self.assertTrue(
            any(
                item["source"] in {"Coverage gap", "Perception Gap", "Open question"}
                for item in payload["openQuestions"]
            )
        )

    def test_board_distinguishes_ready_for_review_from_completed(self) -> None:
        session_id = complete_identify_inputs()

        board = request(
            "GET",
            f"/api/sessions/{session_id}/identify/board",
        ).json()
        activity_by_id = {
            item["activityId"]: item for item in board["activities"]
        }

        self.assertEqual(
            activity_by_id["identify-brief"]["status"], "ready-for-review"
        )

        request("POST", f"/api/sessions/{session_id}/identify/complete")
        completed_board = request(
            "GET", f"/api/sessions/{session_id}/identify/board"
        ).json()
        completed_activity = next(
            item
            for item in completed_board["activities"]
            if item["activityId"] == "identify-brief"
        )
        self.assertEqual(completed_activity["status"], "completed")

    def test_identify_brief_missing_session_returns_not_found(self) -> None:
        response = request(
            "GET",
            f"/api/sessions/{uuid4()}/identify/brief",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Assessment session not found.")

    def test_incomplete_identify_cannot_complete(self) -> None:
        created = request("POST", "/api/sessions", {"companyName": "Meridian"}).json()

        response = request(
            "POST", f"/api/sessions/{created['id']}/identify/complete"
        )

        self.assertEqual(response.status_code, 409)
        detail = response.json()["detail"]
        self.assertFalse(detail["canComplete"])
        codes = {item["code"] for item in detail["blockingIssues"]}
        self.assertTrue(
            {"discover-evidence", "listen-evidence", "understand-evidence"}
            <= codes
        )
        self.assertIn("evidence-wall-theme", codes)

    def test_valid_identify_completion_creates_define_ready_handoff(self) -> None:
        session_id = complete_identify_inputs()

        response = request(
            "POST", f"/api/sessions/{session_id}/identify/complete"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["readiness"]["status"], "completed")
        handoff = payload["handoff"]
        self.assertEqual(handoff["assessmentId"], session_id)
        self.assertEqual(handoff["fromStage"], "identify")
        self.assertEqual(handoff["toStage"], "define")
        self.assertGreater(len(handoff["evidenceReferences"]), 0)
        self.assertGreater(len(handoff["strongestEvidenceIds"]), 0)
        self.assertTrue(handoff["output"]["themes"])

        session = request("GET", f"/api/sessions/{session_id}").json()
        self.assertEqual(session["stage"], "identify")
        self.assertEqual(session["next_stage"], "define")
        self.assertEqual(session["lifecycle_status"], "stage_completed")
        self.assertEqual(session["stage_statuses"]["identify"], "completed")
        self.assertEqual(session["stage_statuses"]["define"], "not_started")
        self.assertEqual(session["identify"]["completion_status"], "completed")
        self.assertIsNotNone(session["identify"]["completed_at"])

    def test_non_blocking_open_questions_are_preserved_in_handoff(self) -> None:
        session_id = complete_identify_inputs()

        response = request(
            "POST", f"/api/sessions/{session_id}/identify/complete"
        )

        self.assertEqual(response.status_code, 200)
        open_questions = response.json()["handoff"]["openQuestions"]
        self.assertGreater(len(open_questions), 0)
        self.assertTrue(
            any("political" in question.lower() for question in open_questions)
        )

    def test_completed_identify_resumes_with_same_handoff(self) -> None:
        session_id = complete_identify_inputs()
        completed = request(
            "POST", f"/api/sessions/{session_id}/identify/complete"
        ).json()

        from app.orchestrator.orchestrator import orchestrator

        orchestrator.clear()
        resumed = request(
            "GET", f"/api/sessions/{session_id}/identify/completion"
        )

        self.assertEqual(resumed.status_code, 200)
        payload = resumed.json()
        self.assertEqual(payload["readiness"]["status"], "completed")
        self.assertEqual(
            payload["handoff"]["completedAt"], completed["handoff"]["completedAt"]
        )
        self.assertEqual(
            payload["handoff"]["evidenceReferences"],
            completed["handoff"]["evidenceReferences"],
        )

    def test_completion_is_idempotent(self) -> None:
        session_id = complete_identify_inputs()
        first = request(
            "POST", f"/api/sessions/{session_id}/identify/complete"
        ).json()
        second = request(
            "POST", f"/api/sessions/{session_id}/identify/complete"
        ).json()

        self.assertEqual(
            first["handoff"]["completedAt"], second["handoff"]["completedAt"]
        )
        session = request("GET", f"/api/sessions/{session_id}").json()
        self.assertEqual(len(session["handoffs"]), 1)

    def test_unresolved_cross_check_blocks_completion(self) -> None:
        session_id = complete_identify_inputs()
        request(
            "PUT",
            f"/api/sessions/{session_id}/identify/company-cards",
            {
                "currentCardIds": ["precision-tool"],
                "desiredCardIds": ["human-circle"],
                "explanation": (
                    "Customers experience a simple, clear and easy quote process."
                ),
            },
        )

        response = request(
            "POST", f"/api/sessions/{session_id}/identify/complete"
        )

        self.assertEqual(response.status_code, 409)
        issues = response.json()["detail"]["blockingIssues"]
        cross_check = next(
            issue for issue in issues if issue["code"] == "unresolved-cross-check"
        )
        self.assertEqual(len(cross_check["evidenceIds"]), 2)
        session = request("GET", f"/api/sessions/{session_id}").json()
        self.assertEqual(session["stage_statuses"]["identify"], "in_progress")
        self.assertTrue(session["identify"]["output"]["themes"])


if __name__ == "__main__":
    unittest.main()
