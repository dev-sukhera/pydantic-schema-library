# Drone message contracts

A small shared Pydantic library for cloud-to-drone gimbal commands and drone-to-cloud command acknowledgements. It validates message shape and serializes Python models to wire JSON; it does not connect to a drone, execute a command, or prove that a physical action is safe.

The package name is `drones_comms_model`. Its present scope is narrower than a general telemetry platform: one command family and acknowledgement variants.

## A command on the wire

```json
{
  "type": "gimbal-controller",
  "timestamp": "2025-06-01T12:00:00Z",
  "payload": {
    "mode": "angle",
    "pitch_deg": 10,
    "yaw_deg": 20
  }
}
```

The exported `AllCloudToDroneV1Commands` adapter dispatches on the internal `command_type_c2d` field, aliased to `type` in JSON. The missing discriminator field was added to the command model so that this public adapter can actually be constructed.

```python
from pydantic import TypeAdapter
from drones_comms_model import AllCloudToDroneV1Commands

adapter = TypeAdapter(AllCloudToDroneV1Commands)
command = adapter.validate_python({
    "type": "gimbal-controller",
    "payload": {"mode": "angle", "pitch_deg": 10, "yaw_deg": 20},
})
wire_json = adapter.dump_json(command, by_alias=True)
```

A timestamp defaults to the current UTC time when omitted. Explicit timestamp input follows Pydantic's datetime parsing; the models do not currently reject naive timestamps or normalize every supplied offset to UTC. Use `by_alias=True` for the documented wire names.

## Mode-dependent validation

| Mode | Required payload fields | Optional fields |
| --- | --- | --- |
| `angle` | `pitch_deg`, `yaw_deg` | `duration_s`, `relative` |
| `angle_step` | `pitch_deg`, `yaw_deg` | `duration_s`, `relative` |
| `rate` | `pitch_deg_s`, `yaw_deg_s` | `duration_s`, `relative` |

When present, duration must be positive. This payload fails validation because the yaw rate is missing:

```json
{"type":"gimbal-controller","payload":{"mode":"rate","pitch_deg_s":1}}
```

Pitch/yaw bounds, finite-number enforcement, cross-mode extra-field exclusion, and hardware-specific limits are not implemented. Pydantic's normal coercion and extra-field defaults apply; do not treat these models as a safety interlock.

## Acknowledgements

`AllDroneToCloudV1Messages` selects command acknowledgements by `type`, then the nominal or failure variant by `status`. Nominal status is `received` or `executed`. An `error` acknowledgement also requires an enumerated `error_code`.

```json
{
  "type": "command_ack",
  "command_id": "11111111-1111-4111-8111-111111111111",
  "status": "error",
  "error_code": "INVALID_PARAMS",
  "message": "Synthetic validation failure"
}
```

Acknowledgements supply default message ID, timestamp, and version. The required `command_id` is provided by the surrounding protocol; the gimbal command model currently does not define that correlation field. A future protocol revision should settle that relationship explicitly rather than inventing a transport contract in the README.

## Install and verify

Python 3.12+ and Pydantic 2.11.5–2.x are declared in `pyproject.toml`. For a package environment, use Poetry with the supplied lockfile, or install the project into a disposable virtual environment. The library has no runtime service or UI.

From a checkout with compatible Pydantic installed:

```sh
python -m unittest discover -s tests -v
```

Four tests exercise exported-union round trips, missing rate fields, nonpositive duration, unknown command types, and acknowledgement variants. They validate software message contracts only. No drone, telemetry transport, hardware limits, or command execution was tested. Existing package author metadata is retained.
