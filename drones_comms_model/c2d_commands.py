from datetime import datetime, timezone
from typing import List, Optional, Union as PyUnion, Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from .common_types import (
    CommandType,
    GimbalControlMode,
    MODEL_CONFIG_WITH_DATETIME_ENCODER,
)

class BaseC2DCommand(BaseModel):
    timestamp_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="timestamp",
        description="Timestamp of the command in UTC. Aliased to timestamp for JSON.",
    )

    model_config = {
        **MODEL_CONFIG_WITH_DATETIME_ENCODER, 
        "populate_by_name": True,
    }

class GimbalControlPayload(BaseModel):
    mode: GimbalControlMode
    pitch_deg: Optional[float] = None
    yaw_deg: Optional[float] = None
    pitch_deg_s: Optional[float] = None
    yaw_deg_s: Optional[float] = None
    duration_s: Optional[float] = Field(None, gt=0)
    relative: Optional[bool] = None

    @model_validator(mode="after")
    def check_conditional_fields(
        values: "GimbalControlPayload"
    ) -> "GimbalControlPayload":
        mode = values.mode
        if mode == GimbalControlMode.ANGLE or mode == GimbalControlMode.ANGLE_STEP:
            if values.pitch_deg is None or values.yaw_deg is None:
                raise ValueError(
                    f"pitch_deg and yaw_deg are required for '{mode.value}' mode"
                )
        elif mode == GimbalControlMode.RATE:
            if values.pitch_deg_s is None or values.yaw_deg_s is None:
                raise ValueError(
                    f"pitch_deg_s and yaw_deg_s are required for '{mode.value}' mode"
                )
        return values


class GimbalControlCommand(BaseC2DCommand):
    command_type_c2d: Literal["gimbal-controller"] = Field("gimbal-controller", alias="type")

    payload: GimbalControlPayload

AllCloudToDroneV1Commands = Annotated[
    PyUnion[GimbalControlCommand,],
    Field(discriminator="command_type_c2d"),
]
