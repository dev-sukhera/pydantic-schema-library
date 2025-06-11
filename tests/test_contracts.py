from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from drones_comms_model import (
    AllCloudToDroneV1Commands,
    AllDroneToCloudV1Messages,
    CommandAckFailure,
)

COMMANDS: TypeAdapter[AllCloudToDroneV1Commands] = TypeAdapter(AllCloudToDroneV1Commands)
MESSAGES: TypeAdapter[AllDroneToCloudV1Messages] = TypeAdapter(AllDroneToCloudV1Messages)
COMMAND_ID = "11111111-1111-4111-8111-111111111111"
ANGLE = {"mode": "angle", "pitch_deg": 1, "yaw_deg": 2}


def test_angle_command_round_trips_through_exported_union() -> None:
    command = COMMANDS.validate_python(
        {
            "type": "gimbal-controller",
            "timestamp": "2025-06-01T12:00:00Z",
            "payload": {"mode": "angle", "pitch_deg": 10, "yaw_deg": 20},
        }
    )
    wire = COMMANDS.dump_python(command, mode="json", by_alias=True)
    assert wire["type"] == "gimbal-controller"
    assert wire["timestamp"] == "2025-06-01T12:00:00Z"
    assert COMMANDS.validate_python(wire).payload.pitch_deg == 10


@pytest.mark.parametrize(
    "payload",
    [
        {"mode": "rate", "pitch_deg_s": 1},
        {"mode": "rate", "pitch_deg_s": 1, "yaw_deg_s": 2, "duration_s": 0},
    ],
)
def test_rate_command_requires_both_rates_and_positive_duration(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        COMMANDS.validate_python({"type": "gimbal-controller", "payload": payload})


def test_unknown_command_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        COMMANDS.validate_python({"type": "unknown", "payload": {}})


def test_acknowledgement_union_selects_nominal_and_failure() -> None:
    base = {"type": "command_ack", "command_id": COMMAND_ID}
    assert MESSAGES.validate_python({**base, "status": "received"}).status == "received"
    failure = MESSAGES.validate_python(
        {
            **base,
            "status": "error",
            "error_code": "INVALID_PARAMS",
            "message": "Synthetic validation failure",
        }
    )
    assert isinstance(failure, CommandAckFailure)
    assert failure.error_message == "Synthetic validation failure"
    with pytest.raises(ValidationError):
        MESSAGES.validate_python({**base, "status": "error"})


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_angles_are_rejected(bad: float) -> None:
    with pytest.raises(ValidationError):
        COMMANDS.validate_python(
            {
                "type": "gimbal-controller",
                "payload": {"mode": "angle", "pitch_deg": bad, "yaw_deg": 0},
            }
        )


def test_timestamps_must_be_aware_and_are_normalised_to_utc() -> None:
    with pytest.raises(ValidationError):
        COMMANDS.validate_python(
            {"type": "gimbal-controller", "timestamp": "2025-06-01T12:00:00", "payload": ANGLE}
        )
    command = COMMANDS.validate_python(
        {"type": "gimbal-controller", "timestamp": "2025-06-01T14:00:00+02:00", "payload": ANGLE}
    )
    assert command.model_dump(mode="json")["timestamp"] == "2025-06-01T12:00:00Z"


@pytest.mark.parametrize(
    "payload",
    [
        {**ANGLE, "pitch": 3},
        {"mode": "rate", "pitch_deg_s": 1, "yaw_deg_s": 2, "pitch_deg": 5},
    ],
)
def test_unknown_and_cross_mode_payload_fields_are_rejected(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        COMMANDS.validate_python({"type": "gimbal-controller", "payload": payload})
