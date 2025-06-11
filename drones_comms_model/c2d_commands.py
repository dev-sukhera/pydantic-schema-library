from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import (
    WIRE_MODEL_CONFIG,
    CommandType,
    GimbalControlMode,
    UtcDatetime,
    utc_now,
)

_ANGLE_FIELDS = ("pitch_deg", "yaw_deg")
_RATE_FIELDS = ("pitch_deg_s", "yaw_deg_s")


class BaseC2DCommand(BaseModel):
    """Envelope shared by every cloud-to-drone command.

    Unknown keys are rejected: a misspelled field on a command must fail loudly
    instead of being dropped before it reaches the aircraft.
    """

    model_config = ConfigDict(**WIRE_MODEL_CONFIG, extra="forbid")

    timestamp_utc: UtcDatetime = Field(
        default_factory=utc_now,
        alias="timestamp",
        description="When the command was issued. Must carry a UTC offset; normalised to UTC.",
    )


class GimbalControlPayload(BaseModel):
    model_config = ConfigDict(**WIRE_MODEL_CONFIG, extra="forbid")

    mode: GimbalControlMode
    pitch_deg: float | None = Field(None, strict=True)
    yaw_deg: float | None = Field(None, strict=True)
    pitch_deg_s: float | None = Field(None, strict=True)
    yaw_deg_s: float | None = Field(None, strict=True)
    duration_s: float | None = Field(None, gt=0, strict=True)
    relative: bool | None = Field(None, strict=True)

    @model_validator(mode="after")
    def check_fields_match_mode(self) -> Self:
        if self.mode is GimbalControlMode.RATE:
            required, forbidden = _RATE_FIELDS, _ANGLE_FIELDS
        else:
            required, forbidden = _ANGLE_FIELDS, _RATE_FIELDS
        if any(getattr(self, name) is None for name in required):
            raise ValueError(f"{' and '.join(required)} are required for '{self.mode.value}' mode")
        present = [name for name in forbidden if getattr(self, name) is not None]
        if present:
            raise ValueError(f"{', '.join(present)} not allowed in '{self.mode.value}' mode")
        return self


class GimbalControlCommand(BaseC2DCommand):
    command_type_c2d: Literal[CommandType.GIMBAL_CONTROL] = Field(
        CommandType.GIMBAL_CONTROL, alias="type"
    )
    payload: GimbalControlPayload


AllCloudToDroneV1Commands = Annotated[
    GimbalControlCommand,
    Field(discriminator="command_type_c2d"),
]
