import json
import ssl
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

import certifi
from pydantic import ValidationError

from app.schemas.assessment import AssessmentSession


class AssessmentRepositoryError(RuntimeError):
    """Base error for durable assessment persistence failures."""


class AssessmentRepositoryConfigurationError(AssessmentRepositoryError):
    """Raised when a selected repository is missing required configuration."""


class AssessmentRepositoryConflictError(AssessmentRepositoryError):
    """Raised when an assessment ID already exists."""


class AssessmentRepositoryDataError(AssessmentRepositoryError):
    """Raised when stored data cannot be reconstructed safely."""


@dataclass(frozen=True)
class RestResponse:
    status: int
    body: bytes


class RestTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> RestResponse: ...


class UrlLibRestTransport:
    """Small standard-library HTTP transport for the Supabase PostgREST API."""

    def __init__(self) -> None:
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> RestResponse:
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(
                request,
                timeout=30,
                context=self._ssl_context,
            ) as response:
                return RestResponse(status=response.status, body=response.read())
        except HTTPError as exc:
            return RestResponse(status=exc.code, body=exc.read())
        except URLError as exc:
            raise AssessmentRepositoryError(
                f"Supabase request failed: {exc.reason}"
            ) from exc


class SupabaseAssessmentRepository:
    """Persist complete assessment records through Supabase PostgREST."""

    def __init__(
        self,
        supabase_url: str,
        service_role_key: str,
        *,
        transport: RestTransport | None = None,
        table: str = "assessments",
    ) -> None:
        if not supabase_url.strip():
            raise AssessmentRepositoryConfigurationError(
                "SUPABASE_URL is required for the Supabase repository."
            )
        if not service_role_key.strip():
            raise AssessmentRepositoryConfigurationError(
                "SUPABASE_SERVICE_ROLE_KEY is required for the Supabase repository."
            )
        self._base_url = f"{supabase_url.rstrip('/')}/rest/v1/{table}"
        self._service_role_key = service_role_key
        self._transport = transport or UrlLibRestTransport()

    def create(self, session: AssessmentSession) -> AssessmentSession:
        response = self._request(
            "POST",
            self._base_url,
            self._row_from_session(session),
            prefer="return=representation",
        )
        if response.status == 409:
            raise AssessmentRepositoryConflictError(
                f"Assessment {session.id} already exists."
            )
        return self._session_from_write_response(response, "create")

    def get(self, session_id: UUID) -> AssessmentSession | None:
        query = urlencode({"id": f"eq.{session_id}", "select": "*"})
        response = self._request("GET", f"{self._base_url}?{query}")
        self._require_success(response, "get")
        rows = self._decode_rows(response)
        if not rows:
            return None
        return self._session_from_row(rows[0])

    def save(self, session: AssessmentSession) -> AssessmentSession:
        expected_version = max(session.version - 1, 1)
        query = urlencode(
            {
                "id": f"eq.{session.id}",
                "version": f"eq.{expected_version}",
            }
        )
        response = self._request(
            "PATCH",
            f"{self._base_url}?{query}",
            self._row_from_session(session),
            prefer="return=representation",
        )
        saved = self._session_from_write_response(response, "save", allow_empty=True)
        if saved is None:
            if self.get(session.id) is None:
                raise KeyError(f"Assessment {session.id} does not exist.")
            raise AssessmentRepositoryConflictError(
                f"Assessment {session.id} was updated by another request."
            )
        return saved

    def clear(self) -> None:
        raise AssessmentRepositoryError(
            "Clearing all Supabase assessments is intentionally unsupported."
        )

    def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, object] | None = None,
        *,
        prefer: str | None = None,
    ) -> RestResponse:
        headers = {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Accept": "application/json",
        }
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if prefer is not None:
            headers["Prefer"] = prefer
        return self._transport.request(method, url, headers, body)

    def _row_from_session(self, session: AssessmentSession) -> dict[str, object]:
        assessment_data = session.model_dump(mode="json")
        return {
            "id": str(session.id),
            "lifecycle_status": session.lifecycle_status.value,
            "current_stage": session.stage.value,
            "stage_statuses": assessment_data["stage_statuses"],
            "assessment_data": assessment_data,
            "version": session.version,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }

    def _session_from_write_response(
        self,
        response: RestResponse,
        operation: str,
        *,
        allow_empty: bool = False,
    ) -> AssessmentSession | None:
        self._require_success(response, operation)
        rows = self._decode_rows(response)
        if not rows and allow_empty:
            return None
        if not rows:
            raise AssessmentRepositoryDataError(
                f"Supabase {operation} returned no assessment record."
            )
        return self._session_from_row(rows[0])

    def _session_from_row(self, row: dict[str, object]) -> AssessmentSession:
        assessment_data = row.get("assessment_data")
        if not isinstance(assessment_data, dict):
            raise AssessmentRepositoryDataError(
                "Supabase assessment_data must be a JSON object."
            )
        data = dict(assessment_data)
        data.update(
            {
                "id": row.get("id"),
                "stage": row.get("current_stage"),
                "lifecycle_status": row.get("lifecycle_status"),
                "stage_statuses": row.get("stage_statuses"),
                "version": row.get("version"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            }
        )
        try:
            return AssessmentSession.model_validate(data)
        except ValidationError as exc:
            raise AssessmentRepositoryDataError(
                "Stored Supabase assessment failed schema validation."
            ) from exc

    def _decode_rows(self, response: RestResponse) -> list[dict[str, object]]:
        try:
            decoded = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AssessmentRepositoryDataError(
                "Supabase returned invalid JSON."
            ) from exc
        if not isinstance(decoded, list) or not all(
            isinstance(row, dict) for row in decoded
        ):
            raise AssessmentRepositoryDataError(
                "Supabase response must be a list of records."
            )
        return decoded

    def _require_success(self, response: RestResponse, operation: str) -> None:
        if 200 <= response.status < 300:
            return
        detail = response.body.decode("utf-8", errors="replace")[:500]
        raise AssessmentRepositoryError(
            f"Supabase {operation} failed with HTTP {response.status}: {detail}"
        )
