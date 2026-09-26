"""Application setup, separate from browser preferences and provider secrets."""
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from scanner.config.application import (
    ApplicationConfiguration, ConfigurationConflict, ConfigurationUnavailable,
    SECIdentity, effective_sec_identity, read_configuration, save_sec_identity,
)
from scanner.migration.ownership import DataRootInUse

router = APIRouter(prefix="/api/v1/setup")


class SetupStatus(BaseModel):
    configuration: ApplicationConfiguration
    sec_configured: bool
    sec_source: Literal["environment", "saved", "missing"]
    sec_user_agent: str
    sec_error: str | None = None


class SetupMutation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)
    sec_identity: SECIdentity | None


def _status(configuration: ApplicationConfiguration) -> SetupStatus:
    try:
        identity = effective_sec_identity(configuration=configuration)
        return SetupStatus(configuration=configuration, sec_configured=bool(identity.user_agent),
                           sec_source=identity.source, sec_user_agent=identity.user_agent)
    except ConfigurationUnavailable as error:
        return SetupStatus(configuration=configuration, sec_configured=False,
                           sec_source="environment", sec_user_agent="", sec_error=str(error))


@router.get("", response_model=SetupStatus)
def get_setup(response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return _status(read_configuration())
    except ConfigurationUnavailable as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.put("", response_model=SetupStatus)
def update_setup(request: SetupMutation, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return _status(save_sec_identity(request.sec_identity, request.expected_revision))
    except (ConfigurationConflict, ConfigurationUnavailable, DataRootInUse) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
