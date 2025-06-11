"""The committed schemas/ files must match what the models generate today."""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from drones_comms_model.json_schema import DIALECT, wire_schemas

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
GENERATED = wire_schemas()


@pytest.mark.parametrize("filename", sorted(GENERATED))
def test_committed_schema_matches_models(filename: str) -> None:
    committed = (SCHEMA_DIR / filename).read_text(encoding="utf-8")
    assert committed == GENERATED[filename], "run: python scripts/export_schemas.py"


def test_no_stray_schema_files() -> None:
    assert sorted(path.name for path in SCHEMA_DIR.glob("*.json")) == sorted(GENERATED)


def load(filename: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(GENERATED[filename])
    return document


def test_command_schema_exposes_wire_names_and_discriminator() -> None:
    document = load("c2d-commands.v1.schema.json")
    assert document["$schema"] == DIALECT
    command = document["$defs"]["GimbalControlCommand"]
    assert set(command["properties"]) == {"command_id", "timestamp", "type", "payload"}
    assert command["additionalProperties"] is False
    assert set(command["required"]) == {"payload", "type"}
    assert command["properties"]["timestamp"]["format"] == "date-time"
    assert document["discriminator"]["propertyName"] == "type"


def test_message_schema_routes_on_type_then_status() -> None:
    document = load("d2c-messages.v1.schema.json")
    (by_status,) = document["oneOf"]
    assert by_status["discriminator"]["propertyName"] == "status"
    failure = document["$defs"]["CommandAckFailure"]
    assert {"command_id", "status", "error_code", "type"} <= set(failure["required"])
    assert "type" in document["$defs"]["CommandAckNominal"]["required"]
    assert "message" in failure["properties"]


ANGLE = {"mode": "angle", "pitch_deg": 10, "yaw_deg": 20}
COMMAND = {"type": "gimbal-controller", "payload": ANGLE}
ACK = {"type": "command_ack", "command_id": "11111111-1111-4111-8111-111111111111"}


@pytest.mark.parametrize(
    ("filename", "instance", "valid"),
    [
        ("c2d-commands.v1.schema.json", COMMAND, True),
        ("c2d-commands.v1.schema.json", {"payload": ANGLE}, False),
        ("c2d-commands.v1.schema.json", {"type": "other", "payload": ANGLE}, False),
        ("c2d-commands.v1.schema.json", {**COMMAND, "x": 1}, False),
        ("c2d-commands.v1.schema.json", {**COMMAND, "payload": {"mode": "spin"}}, False),
        ("d2c-messages.v1.schema.json", {**ACK, "status": "executed"}, True),
        ("d2c-messages.v1.schema.json", {**ACK, "status": "executed", "version": "2.0"}, False),
        (
            "d2c-messages.v1.schema.json",
            {**ACK, "status": "error", "error_code": "GENERAL_ERROR"},
            True,
        ),
        ("d2c-messages.v1.schema.json", {**ACK, "status": "error"}, False),
        (
            "d2c-messages.v1.schema.json",
            {"command_id": ACK["command_id"], "status": "executed"},
            False,
        ),
    ],
)
def test_plain_json_schema_validator_agrees_with_models(
    filename: str, instance: dict[str, Any], valid: bool
) -> None:
    validator = Draft202012Validator(load(filename))
    assert validator.is_valid(instance) is valid
