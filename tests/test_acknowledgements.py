"""Validation and two-level routing for drone-to-cloud acknowledgements."""

from typing import Any
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from drones_comms_model import (
    AllDroneToCloudV1Messages,
    CommandAckFailure,
    CommandAckNominal,
    CommandAckStatus,
    SpecificErrorCode,
)

MESSAGES: TypeAdapter[AllDroneToCloudV1Messages] = TypeAdapter(AllDroneToCloudV1Messages)
COMMAND_ID = "11111111-1111-4111-8111-111111111111"
BASE = {"type": "command_ack", "command_id": COMMAND_ID}
ERROR = {**BASE, "status": "error", "error_code": "HARDWARE_FAILURE"}


def error_types(exc: pytest.ExceptionInfo[ValidationError]) -> set[str]:
    return {error["type"] for error in exc.value.errors()}


@pytest.mark.parametrize("status", ["received", "executed"])
def test_nominal_statuses_route_to_nominal(status: str) -> None:
    ack = MESSAGES.validate_python({**BASE, "status": status})
    assert isinstance(ack, CommandAckNominal)
    assert ack.status is CommandAckStatus(status)
    assert ack.command_id == UUID(COMMAND_ID)


def test_error_status_routes_to_failure() -> None:
    ack = MESSAGES.validate_python(ERROR)
    assert isinstance(ack, CommandAckFailure)
    assert ack.error_code is SpecificErrorCode.HARDWARE_FAILURE
    assert ack.error_message is None


@pytest.mark.parametrize("code", [code.value for code in SpecificErrorCode])
def test_every_error_code_is_accepted(code: str) -> None:
    ack = MESSAGES.validate_python({**ERROR, "error_code": code})
    assert isinstance(ack, CommandAckFailure)


def test_error_requires_an_error_code() -> None:
    with pytest.raises(ValidationError) as exc:
        MESSAGES.validate_python({**BASE, "status": "error"})
    assert "missing" in error_types(exc)


@pytest.mark.parametrize("code", ["TIMEOUT", "invalid_params", ""])
def test_unknown_error_code_is_rejected(code: str) -> None:
    with pytest.raises(ValidationError):
        MESSAGES.validate_python({**ERROR, "error_code": code})


@pytest.mark.parametrize("status", ["done", "ERROR", ""])
def test_unknown_status_is_rejected(status: str) -> None:
    with pytest.raises(ValidationError) as exc:
        MESSAGES.validate_python({**BASE, "status": status})
    assert "union_tag_invalid" in error_types(exc)


def test_missing_status_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        MESSAGES.validate_python(BASE)
    assert "union_tag_not_found" in error_types(exc)


@pytest.mark.parametrize("tag", ["telemetry", "command-ack", ""])
def test_unknown_message_type_is_rejected(tag: str) -> None:
    with pytest.raises(ValidationError) as exc:
        MESSAGES.validate_python({**BASE, "type": tag, "status": "received"})
    assert "union_tag_invalid" in error_types(exc)


@pytest.mark.parametrize("command_id", ["not-a-uuid", "", 42])
def test_command_id_must_be_a_uuid(command_id: object) -> None:
    with pytest.raises(ValidationError):
        MESSAGES.validate_python({**BASE, "command_id": command_id, "status": "received"})


def test_command_id_is_required() -> None:
    with pytest.raises(ValidationError):
        MESSAGES.validate_python({"type": "command_ack", "status": "received"})


@pytest.mark.parametrize("version", ["2.0", "1", 1.0])
def test_only_version_1_0_is_accepted(version: object) -> None:
    with pytest.raises(ValidationError):
        MESSAGES.validate_python({**BASE, "status": "received", "version": version})


def test_defaults_are_filled_in() -> None:
    first = MESSAGES.validate_python({**BASE, "status": "received"})
    second = MESSAGES.validate_python({**BASE, "status": "received"})
    assert first.version == "1.0"
    assert first.message_id != second.message_id
    assert first.timestamp_utc.utcoffset() is not None


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        MESSAGES.validate_python({**BASE, "status": "received", "timestamp": "2025-06-01T12:00:00"})
    assert "timezone_aware" in error_types(exc)


def test_unknown_keys_are_ignored_for_forward_compatibility() -> None:
    raw: dict[str, Any] = {**BASE, "status": "executed", "battery_pct": 81, "error_code": "X"}
    ack = MESSAGES.validate_python(raw)
    assert isinstance(ack, CommandAckNominal)
    assert "battery_pct" not in ack.model_dump()
    assert "error_code" not in ack.model_dump()


def test_message_alias_maps_to_error_message() -> None:
    ack = MESSAGES.validate_python({**ERROR, "message": "gimbal motor stalled"})
    assert isinstance(ack, CommandAckFailure)
    assert ack.model_dump(mode="json")["message"] == "gimbal motor stalled"
