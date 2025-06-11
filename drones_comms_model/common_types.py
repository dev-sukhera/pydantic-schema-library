import datetime
from enum import Enum
from typing import Union as PyUnion

from pydantic import BaseModel, Field

MODEL_CONFIG_WITH_DATETIME_ENCODER = {
    "json_encoders": {
        datetime: lambda v: v.strftime("%Y-%m-%dT%H:%M:%SZ") if v else None
    }
}

class CommandType(str, Enum):
    GIMBAL_CONTROL = "gimbal-controller"


class GimbalControlMode(str, Enum):
    RATE = "rate"
    ANGLE = "angle"
    ANGLE_STEP = "angle_step"

class CommandAckStatus(str, Enum):
    RECEIVED = "received"
    EXECUTED = "executed"
    ERROR = "error"


class SpecificErrorCode(str, Enum):
    INVALID_PARAMS = "INVALID_PARAMS"
    UNSUPPORTED_COMMAND = "UNSUPPORTED_COMMAND"
    DUPLICATE_COMMAND = "DUPLICATE_COMMAND"
    HARDWARE_FAILURE = "HARDWARE_FAILURE"
    GENERAL_ERROR = "GENERAL_ERROR"
