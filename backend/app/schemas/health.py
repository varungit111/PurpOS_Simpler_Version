from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Validated response model for the `/health` endpoint."""

    model_config = ConfigDict(extra="forbid")

    status: str
    service: str
