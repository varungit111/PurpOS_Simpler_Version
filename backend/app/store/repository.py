from collections.abc import MutableMapping
from typing import Protocol
from uuid import UUID

from app.schemas.assessment import AssessmentSession
from app.store.supabase import (
    AssessmentRepositoryConfigurationError,
    SupabaseAssessmentRepository,
)


class AssessmentRepository(Protocol):
    """Storage boundary for complete, structured assessment records."""

    def create(self, session: AssessmentSession) -> AssessmentSession: ...

    def get(self, session_id: UUID) -> AssessmentSession | None: ...

    def save(self, session: AssessmentSession) -> AssessmentSession: ...

    def clear(self) -> None: ...


class InMemoryAssessmentRepository:
    """Local/test adapter retained until a durable database is selected."""

    def __init__(
        self,
        records: MutableMapping[UUID, AssessmentSession] | None = None,
    ) -> None:
        self._records = records if records is not None else {}

    def create(self, session: AssessmentSession) -> AssessmentSession:
        if session.id in self._records:
            raise ValueError(f"Assessment {session.id} already exists.")
        self._records[session.id] = session.model_copy(deep=True)
        return session.model_copy(deep=True)

    def get(self, session_id: UUID) -> AssessmentSession | None:
        session = self._records.get(session_id)
        return None if session is None else session.model_copy(deep=True)

    def save(self, session: AssessmentSession) -> AssessmentSession:
        if session.id not in self._records:
            raise KeyError(f"Assessment {session.id} does not exist.")
        self._records[session.id] = session.model_copy(deep=True)
        return session.model_copy(deep=True)

    def clear(self) -> None:
        self._records.clear()


def create_assessment_repository(
    provider: str,
    *,
    supabase_url: str | None = None,
    supabase_service_role_key: str | None = None,
) -> AssessmentRepository:
    """Build the configured adapter and never silently downgrade durability."""
    normalized_provider = provider.strip().lower()
    if normalized_provider == "memory":
        return InMemoryAssessmentRepository()
    if normalized_provider == "supabase":
        if not supabase_url or not supabase_service_role_key:
            raise AssessmentRepositoryConfigurationError(
                "Supabase persistence requires SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY."
            )
        return SupabaseAssessmentRepository(
            supabase_url=supabase_url,
            service_role_key=supabase_service_role_key,
        )
    raise AssessmentRepositoryConfigurationError(
        "PURPOS_ASSESSMENT_REPOSITORY must be 'memory' or 'supabase'."
    )
