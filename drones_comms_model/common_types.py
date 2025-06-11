from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, ConfigDict


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


# Naive datetimes are rejected because their offset is unknowable on the far side
# of the link; aware ones are normalised so every message carries a UTC instant.
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]


def utc_now() -> datetime:
    return datetime.now(UTC)


WIRE_MODEL_CONFIG = ConfigDict(
    validate_by_name=True,
    validate_by_alias=True,
    serialize_by_alias=True,
    # NaN/inf would serialise as JSON null and the message would no longer validate.
    allow_inf_nan=False,
)


class CommandType(StrEnum):
    GIMBAL_CONTROL = "gimbal-controller"


class GimbalControlMode(StrEnum):
    RATE = "rate"
    ANGLE = "angle"
    ANGLE_STEP = "angle_step"


class CommandAckStatus(StrEnum):
    RECEIVED = "received"
    EXECUTED = "executed"
    ERROR = "error"


class SpecificErrorCode(StrEnum):
    INVALID_PARAMS = "INVALID_PARAMS"
    UNSUPPORTED_COMMAND = "UNSUPPORTED_COMMAND"
    DUPLICATE_COMMAND = "DUPLICATE_COMMAND"
    HARDWARE_FAILURE = "HARDWARE_FAILURE"
    GENERAL_ERROR = "GENERAL_ERROR"
