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


def company_cards_payload() -> dict[str, object]:
    return {
        "currentCardIds": ["precision-tool"],
        "desiredCardIds": ["human-circle"],
        "explanation": "The current experience feels efficient but not human enough.",
    }


def create_unlocked_session() -> tuple[str, list[str]]:
    created = request("POST", "/api/sessions", {}).json()
    session_id = str(created["id"])
    stakeholder = request(
        "PUT",
        f"/api/sessions/{session_id}/identify/stakeholders",
        {"stakeholders": [stakeholder_payload()]},
    ).json()["stakeholders"][0]
    company_cards = request(
        "PUT",
        f"/api/sessions/{session_id}/identify/company-cards",
        company_cards_payload(),
    ).json()["evidence"]
    return session_id, [stakeholder["id"], company_cards["id"]]


def gap_payload(evidence_ids: list[str]) -> dict[str, object]:
    return {
        "topic": "Service experience",
        "perspectiveA": "The organisation says the service is fast and practical.",
        "perspectiveB": "Stakeholder evidence suggests the experience feels impersonal.",
        "difference": "Efficiency is clear, but the human experience is under-evidenced.",
        "supportingEvidenceIds": evidence_ids,
        "clarificationNeeded": True,
        "resolution": "unresolved",
        "resolutionNote": None,
    }


class PerceptionGapsEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()

    def test_perception_gaps_locked_until_two_meaningful_sources_exist(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "GET",
            f"/api/sessions/{created['id']}/identify/perception-gaps",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activity_status"], "locked")
        self.assertEqual(payload["progress"]["requiredSourceCount"], 2)
        self.assertIn("two meaningful", payload["dependency_message"])

    def test_perception_gaps_unlocks_with_two_evidence_sources(self) -> None:
        session_id, _ = create_unlocked_session()

        response = request(
            "GET",
            f"/api/sessions/{session_id}/identify/perception-gaps",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activity_status"], "available")
        self.assertGreaterEqual(payload["progress"]["evidenceSourceCount"], 2)
        self.assertGreaterEqual(len(payload["evidenceReferences"]), 2)

    def test_non_conflicting_evidence_does_not_suggest_a_gap(self) -> None:
        session_id, _ = create_unlocked_session()

        response = request(
            "GET",
            f"/api/sessions/{session_id}/identify/perception-gaps",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["suggestedGaps"], [])

    def test_locked_perception_gaps_rejects_save(self) -> None:
        created = request("POST", "/api/sessions", {}).json()

        response = request(
            "PUT",
            f"/api/sessions/{created['id']}/identify/perception-gaps",
            {"gaps": []},
        )

        self.assertEqual(response.status_code, 423)

    def test_put_perception_gap_requires_known_supporting_evidence(self) -> None:
        session_id, _ = create_unlocked_session()

        response = request(
            "PUT",
            f"/api/sessions/{session_id}/identify/perception-gaps",
            {"gaps": [gap_payload([str(uuid4())])]},
        )

        self.assertEqual(response.status_code, 422)

    def test_put_perception_gap_saves_with_evidence_links(self) -> None:
        session_id, evidence_ids = create_unlocked_session()

        response = request(
            "PUT",
            f"/api/sessions/{session_id}/identify/perception-gaps",
            {"gaps": [gap_payload(evidence_ids)]},
        )

        self.assertEqual(response.status_code, 200)
        gap = response.json()["gaps"][0]
        self.assertEqual(gap["supportingEvidenceIds"], evidence_ids)
        self.assertEqual(gap["resolution"], "unresolved")

        reloaded = request(
            "GET",
            f"/api/sessions/{session_id}/identify/perception-gaps",
        )
        self.assertEqual(reloaded.status_code, 200)
        self.assertEqual(reloaded.json()["gaps"][0]["id"], gap["id"])

    def test_review_confirm_updates_only_gap_and_dependent_output(self) -> None:
        session_id, evidence_ids = create_unlocked_session()
        saved_gap = request(
            "PUT",
            f"/api/sessions/{session_id}/identify/perception-gaps",
            {"gaps": [gap_payload(evidence_ids)]},
        ).json()["gaps"][0]

        response = request(
            "PATCH",
            f"/api/sessions/{session_id}/identify/perception-gaps/{saved_gap['id']}",
            {
                "resolution": "confirmed",
                "clarificationNeeded": False,
                "resolutionNote": "SME confirmed this is a real gap.",
            },
        )

        self.assertEqual(response.status_code, 200)
        reviewed = response.json()["gaps"][0]
        self.assertEqual(reviewed["resolution"], "confirmed")
        self.assertFalse(reviewed["clarificationNeeded"])
        state = session_store.get_identify_state(UUID(session_id))
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state.output.vulnerabilities_gaps, [])

    def test_review_correction_changes_target_gap_only(self) -> None:
        session_id, evidence_ids = create_unlocked_session()
        saved = request(
            "PUT",
            f"/api/sessions/{session_id}/identify/perception-gaps",
            {"gaps": [gap_payload(evidence_ids)]},
        ).json()["gaps"][0]

        response = request(
            "PATCH",
            f"/api/sessions/{session_id}/identify/perception-gaps/{saved['id']}",
            {
                "resolution": "corrected",
                "perspectiveB": "Stakeholders need warmth during onboarding.",
                "difference": "The practical promise needs a warmer onboarding proof point.",
                "clarificationNeeded": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        reviewed = response.json()["gaps"][0]
        self.assertEqual(reviewed["resolution"], "corrected")
        self.assertEqual(
            reviewed["difference"],
            "The practical promise needs a warmer onboarding proof point.",
        )

    def test_perception_gap_missing_session_returns_not_found(self) -> None:
        response = request(
            "GET",
            f"/api/sessions/{uuid4()}/identify/perception-gaps",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Assessment session not found.")


if __name__ == "__main__":
    unittest.main()
