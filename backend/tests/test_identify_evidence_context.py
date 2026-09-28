import unittest

from app.schemas.assessment import EvidenceSource, IdentifyEvidence, IdentifyState
from app.services.identify_evidence_context import (
    MAX_CLAIM_CHARS,
    build_identify_evidence_context,
)


class IdentifyEvidenceContextTests(unittest.TestCase):
    def test_context_is_deterministic_bounded_and_uses_concise_claims(self) -> None:
        state = IdentifyState(
            evidence=[
                IdentifyEvidence(
                    source=EvidenceSource(
                        title=f"Source {index}",
                        source_type="interview",
                    ),
                    claim=(f"Evidence {index} " + "detail " * 100),
                    sourceActivity=f"activity-{index}",
                    sourceReference=f"reference-{index}",
                )
                for index in range(30)
            ]
        )

        first = build_identify_evidence_context(state)
        second = build_identify_evidence_context(state)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 24)
        self.assertTrue(all(len(item["claim"]) <= MAX_CLAIM_CHARS for item in first))


if __name__ == "__main__":
    unittest.main()
