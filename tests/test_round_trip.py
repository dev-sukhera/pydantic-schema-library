"""Property tests: anything that validates must survive a JSON round trip unchanged."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter

from drones_comms_model import (
    AllCloudToDroneV1Commands,
    AllDroneToCloudV1Messages,
    SpecificErrorCode,
)

COMMANDS: TypeAdapter[AllCloudToDroneV1Commands] = TypeAdapter(AllCloudToDroneV1Commands)
MESSAGES: TypeAdapter[AllDroneToCloudV1Messages] = TypeAdapter(AllDroneToCloudV1Messages)

finite = st.floats(allow_nan=False, allow_infinity=False)
positive = st.floats(min_value=0, exclude_min=True, allow_infinity=False)
offsets = st.integers(min_value=-14 * 60, max_value=14 * 60).map(
    lambda minutes: timezone(timedelta(minutes=minutes))
)
aware_datetimes = st.datetimes(
    min_value=datetime(1970, 1, 2), max_value=datetime(2200, 1, 1), timezones=offsets
)
optional_extras = st.fixed_dictionaries(
    {},
    optional={"duration_s": positive, "relative": st.booleans()},
)


@st.composite
def gimbal_payloads(draw: st.DrawFn) -> dict[str, Any]:
    mode = draw(st.sampled_from(["angle", "angle_step", "rate"]))
    suffix = "_s" if mode == "rate" else ""
    return {
        "mode": mode,
        f"pitch_deg{suffix}": draw(finite),
        f"yaw_deg{suffix}": draw(finite),
        **draw(optional_extras),
    }


@given(payload=gimbal_payloads(), timestamp=aware_datetimes)
def test_commands_survive_json_round_trip(payload: dict[str, Any], timestamp: datetime) -> None:
    command = COMMANDS.validate_python(
        {"type": "gimbal-controller", "timestamp": timestamp, "payload": payload}
    )
    assert command.timestamp_utc == timestamp
    assert command.timestamp_utc.tzinfo is UTC
    wire = COMMANDS.dump_json(command)
    assert COMMANDS.validate_json(wire) == command


acks = st.one_of(
    st.fixed_dictionaries({"status": st.sampled_from(["received", "executed"])}),
    st.fixed_dictionaries(
        {"status": st.just("error"), "error_code": st.sampled_from(list(SpecificErrorCode))},
        optional={"message": st.text()},
    ),
)


@given(ack=acks, command_id=st.uuids(), timestamp=aware_datetimes)
def test_acknowledgements_survive_json_round_trip(
    ack: dict[str, Any], command_id: Any, timestamp: datetime
) -> None:
    message = MESSAGES.validate_python(
        {"type": "command_ack", "command_id": command_id, "timestamp": timestamp, **ack}
    )
    assert MESSAGES.validate_json(MESSAGES.dump_json(message)) == message
