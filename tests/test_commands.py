"""Field-level validation and discriminator routing for cloud-to-drone commands."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from drones_comms_model import (
    AllCloudToDroneV1Commands,
    CommandType,
    GimbalControlCommand,
    GimbalControlMode,
    GimbalControlPayload,
)

COMMANDS: TypeAdapter[AllCloudToDroneV1Commands] = TypeAdapter(AllCloudToDroneV1Commands)
ANGLE = {"mode": "angle", "pitch_deg": -30.0, "yaw_deg": 90.0}
RATE = {"mode": "rate", "pitch_deg_s": 5.0, "yaw_deg_s": -12.5}


def command(payload: dict[str, Any], **envelope: Any) -> dict[str, Any]:
    return {"type": "gimbal-controller", "payload": payload, **envelope}


def error_types(exc: pytest.ExceptionInfo[ValidationError]) -> set[str]:
    return {error["type"] for error in exc.value.errors()}


class TestModes:
    @pytest.mark.parametrize("mode", ["angle", "angle_step"])
    def test_angle_modes_require_pitch_and_yaw(self, mode: str) -> None:
        parsed = COMMANDS.validate_python(command({**ANGLE, "mode": mode}))
        assert parsed.payload.mode is GimbalControlMode(mode)
        for missing in ("pitch_deg", "yaw_deg"):
            partial = {k: v for k, v in ANGLE.items() if k != missing}
            with pytest.raises(ValidationError, match="pitch_deg and yaw_deg are required"):
                COMMANDS.validate_python(command({**partial, "mode": mode}))

    def test_rate_mode_requires_both_rates(self) -> None:
        assert COMMANDS.validate_python(command(RATE)).payload.yaw_deg_s == -12.5
        for missing in ("pitch_deg_s", "yaw_deg_s"):
            partial = {k: v for k, v in RATE.items() if k != missing}
            with pytest.raises(ValidationError, match="pitch_deg_s and yaw_deg_s are required"):
                COMMANDS.validate_python(command(partial))

    @pytest.mark.parametrize(
        ("payload", "offending"),
        [
            ({**ANGLE, "pitch_deg_s": 1.0}, "pitch_deg_s"),
            ({**ANGLE, "mode": "angle_step", "yaw_deg_s": 1.0}, "yaw_deg_s"),
            ({**RATE, "yaw_deg": 0.0}, "yaw_deg"),
        ],
    )
    def test_fields_from_the_other_mode_are_rejected(
        self, payload: dict[str, Any], offending: str
    ) -> None:
        with pytest.raises(ValidationError, match=f"{offending} not allowed"):
            COMMANDS.validate_python(command(payload))

    def test_unknown_mode_is_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            COMMANDS.validate_python(command({**ANGLE, "mode": "orbit"}))
        assert "enum" in error_types(exc)


class TestNumericFields:
    @pytest.mark.parametrize("field", ["pitch_deg", "yaw_deg"])
    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_angles_must_be_finite(self, field: str, value: float) -> None:
        with pytest.raises(ValidationError) as exc:
            COMMANDS.validate_python(command({**ANGLE, field: value}))
        assert "finite_number" in error_types(exc)

    @pytest.mark.parametrize("field", ["pitch_deg_s", "yaw_deg_s"])
    def test_rates_must_be_finite(self, field: str) -> None:
        with pytest.raises(ValidationError):
            COMMANDS.validate_python(command({**RATE, field: float("nan")}))

    def test_non_finite_values_are_rejected_in_json_too(self) -> None:
        with pytest.raises(ValidationError):
            COMMANDS.validate_json(
                '{"type":"gimbal-controller","payload":{"mode":"angle","pitch_deg":NaN,"yaw_deg":0}}'
            )

    def test_integers_are_accepted_as_floats(self) -> None:
        parsed = COMMANDS.validate_python(command({"mode": "angle", "pitch_deg": 10, "yaw_deg": 0}))
        assert parsed.payload.pitch_deg == 10.0

    @pytest.mark.parametrize("value", ["10", True, b"1"])
    def test_angles_do_not_coerce_strings_or_bools(self, value: object) -> None:
        with pytest.raises(ValidationError):
            COMMANDS.validate_python(command({**ANGLE, "pitch_deg": value}))

    def test_angle_strings_are_rejected_in_json(self) -> None:
        with pytest.raises(ValidationError):
            COMMANDS.validate_json(
                '{"type":"gimbal-controller","payload":{"mode":"angle","pitch_deg":"10","yaw_deg":0}}'
            )

    @pytest.mark.parametrize("value", [-720.0, -0.0, 0.0, 359.999, 1e6])
    def test_angles_have_no_built_in_hardware_limits(self, value: float) -> None:
        payload = COMMANDS.validate_python(command({**ANGLE, "yaw_deg": value})).payload
        assert payload.yaw_deg == value

    @pytest.mark.parametrize("value", [1e-9, 0.5, 30])
    def test_positive_durations_are_accepted(self, value: float) -> None:
        payload = COMMANDS.validate_python(command({**RATE, "duration_s": value})).payload
        assert payload.duration_s == value

    @pytest.mark.parametrize("value", [0, 0.0, -0.0, -1, float("nan"), float("inf")])
    def test_duration_must_be_positive_and_finite(self, value: float) -> None:
        with pytest.raises(ValidationError):
            COMMANDS.validate_python(command({**RATE, "duration_s": value}))

    def test_optional_fields_default_to_none(self) -> None:
        payload = COMMANDS.validate_python(command(ANGLE)).payload
        assert payload.duration_s is None
        assert payload.relative is None


class TestRelativeFlag:
    @pytest.mark.parametrize("value", [True, False])
    def test_bools_are_accepted(self, value: bool) -> None:
        payload = COMMANDS.validate_python(command({**ANGLE, "relative": value})).payload
        assert payload.relative is value

    @pytest.mark.parametrize("value", ["true", "yes", 1, 0])
    def test_truthy_lookalikes_are_rejected(self, value: object) -> None:
        with pytest.raises(ValidationError):
            COMMANDS.validate_python(command({**ANGLE, "relative": value}))


class TestTimestamps:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2025-06-01T12:00:00Z", datetime(2025, 6, 1, 12, tzinfo=UTC)),
            ("2025-06-01T14:30:00+02:30", datetime(2025, 6, 1, 12, tzinfo=UTC)),
            ("2025-06-01T07:00:00-05:00", datetime(2025, 6, 1, 12, tzinfo=UTC)),
            ("2025-06-01T00:30:00+12:30", datetime(2025, 5, 31, 12, tzinfo=UTC)),
            (0, datetime(1970, 1, 1, tzinfo=UTC)),
        ],
    )
    def test_aware_input_is_normalised_to_utc(self, raw: object, expected: datetime) -> None:
        parsed = COMMANDS.validate_python(command(ANGLE, timestamp=raw)).timestamp_utc
        assert parsed == expected
        assert parsed.utcoffset() == timedelta(0)

    @pytest.mark.parametrize("raw", ["2025-06-01T12:00:00", datetime(2025, 6, 1, 12)])
    def test_naive_timestamps_are_rejected(self, raw: object) -> None:
        with pytest.raises(ValidationError) as exc:
            COMMANDS.validate_python(command(ANGLE, timestamp=raw))
        assert "timezone_aware" in error_types(exc)

    @pytest.mark.parametrize("raw", ["yesterday", "2025-13-01T00:00:00Z", ""])
    def test_unparseable_timestamps_are_rejected(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            COMMANDS.validate_python(command(ANGLE, timestamp=raw))

    def test_default_timestamp_is_current_utc(self) -> None:
        before = datetime.now(UTC)
        stamp = COMMANDS.validate_python(command(ANGLE)).timestamp_utc
        assert stamp.tzinfo is UTC
        assert before <= stamp <= datetime.now(UTC)

    def test_wire_format_uses_z_suffix(self) -> None:
        parsed = COMMANDS.validate_python(command(ANGLE, timestamp="2025-06-01T14:00:00+02:00"))
        assert parsed.model_dump(mode="json")["timestamp"] == "2025-06-01T12:00:00Z"


class TestEnvelope:
    def test_unknown_envelope_keys_are_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            COMMANDS.validate_python(command(ANGLE, priority="high"))
        assert "extra_forbidden" in error_types(exc)

    def test_misspelled_payload_key_is_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            COMMANDS.validate_python(command({**ANGLE, "pitch": 3}))
        assert "extra_forbidden" in error_types(exc)

    def test_python_field_names_are_accepted_as_well_as_aliases(self) -> None:
        parsed = COMMANDS.validate_python(
            {
                "command_type_c2d": "gimbal-controller",
                "timestamp_utc": "2025-06-01T12:00:00Z",
                "payload": ANGLE,
            }
        )
        assert parsed.timestamp_utc == datetime(2025, 6, 1, 12, tzinfo=UTC)

    def test_command_id_defaults_to_a_fresh_uuid(self) -> None:
        first = COMMANDS.validate_python(command(ANGLE)).command_id
        second = COMMANDS.validate_python(command(ANGLE)).command_id
        assert first.version == 4
        assert first != second

    def test_supplied_command_id_is_kept(self) -> None:
        command_id = "22222222-2222-4222-8222-222222222222"
        parsed = COMMANDS.validate_python(command(ANGLE, command_id=command_id))
        assert parsed.command_id == UUID(command_id)
        assert parsed.model_dump(mode="json")["command_id"] == command_id

    @pytest.mark.parametrize("command_id", ["cmd-1", "", 7])
    def test_command_id_must_be_a_uuid(self, command_id: object) -> None:
        with pytest.raises(ValidationError):
            COMMANDS.validate_python(command(ANGLE, command_id=command_id))

    def test_payload_is_required(self) -> None:
        with pytest.raises(ValidationError) as exc:
            COMMANDS.validate_python({"type": "gimbal-controller"})
        assert "missing" in error_types(exc)


class TestDiscriminator:
    def test_type_routes_to_gimbal_command(self) -> None:
        parsed = COMMANDS.validate_python(command(ANGLE))
        assert isinstance(parsed, GimbalControlCommand)
        assert parsed.command_type_c2d is CommandType.GIMBAL_CONTROL

    @pytest.mark.parametrize("tag", ["unknown", "gimbal_controller", "GIMBAL-CONTROLLER", ""])
    def test_unknown_type_is_rejected(self, tag: str) -> None:
        with pytest.raises(ValidationError) as exc:
            COMMANDS.validate_python({"type": tag, "payload": ANGLE})
        assert "union_tag_invalid" in error_types(exc)

    def test_missing_type_is_rejected_by_the_union(self) -> None:
        with pytest.raises(ValidationError) as exc:
            COMMANDS.validate_python({"payload": ANGLE})
        assert "union_tag_not_found" in error_types(exc)

    def test_direct_construction_fills_in_the_type(self) -> None:
        built = GimbalControlCommand(payload=GimbalControlPayload.model_validate(ANGLE))
        assert built.model_dump(mode="json")["type"] == "gimbal-controller"
