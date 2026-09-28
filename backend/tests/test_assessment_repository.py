import unittest

from app.schemas.assessment import AssessmentSession
from app.store.repository import InMemoryAssessmentRepository


class InMemoryAssessmentRepositoryTests(unittest.TestCase):
    def test_create_get_and_save_use_defensive_copies(self) -> None:
        repository = InMemoryAssessmentRepository()
        session = AssessmentSession()
        repository.create(session)

        loaded = repository.get(session.id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        loaded.version = 7

        self.assertEqual(repository.get(session.id).version, 1)  # type: ignore[union-attr]
        repository.save(loaded)
        self.assertEqual(repository.get(session.id).version, 7)  # type: ignore[union-attr]

    def test_get_unknown_assessment_returns_none(self) -> None:
        repository = InMemoryAssessmentRepository()
        session = AssessmentSession()

        self.assertIsNone(repository.get(session.id))


if __name__ == "__main__":
    unittest.main()
