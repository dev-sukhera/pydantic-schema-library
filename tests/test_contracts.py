import unittest
from pydantic import TypeAdapter, ValidationError
from drones_comms_model import AllCloudToDroneV1Commands, AllDroneToCloudV1Messages

class MessageContractTests(unittest.TestCase):
    def test_angle_command_round_trips_through_exported_union(self):
        adapter=TypeAdapter(AllCloudToDroneV1Commands)
        command=adapter.validate_python({"type":"gimbal-controller","timestamp":"2025-06-01T12:00:00Z","payload":{"mode":"angle","pitch_deg":10,"yaw_deg":20}})
        wire=adapter.dump_python(command,mode="json",by_alias=True)
        self.assertEqual(wire["type"],"gimbal-controller")
        self.assertEqual(wire["timestamp"],"2025-06-01T12:00:00Z")
        self.assertEqual(adapter.validate_python(wire).payload.pitch_deg,10)
    def test_rate_command_requires_both_rates_and_positive_duration(self):
        adapter=TypeAdapter(AllCloudToDroneV1Commands)
        for payload in [{"mode":"rate","pitch_deg_s":1},{"mode":"rate","pitch_deg_s":1,"yaw_deg_s":2,"duration_s":0}]:
            with self.assertRaises(ValidationError):adapter.validate_python({"type":"gimbal-controller","payload":payload})
    def test_unknown_command_type_is_rejected(self):
        with self.assertRaises(ValidationError):TypeAdapter(AllCloudToDroneV1Commands).validate_python({"type":"unknown","payload":{}})
    def test_acknowledgement_union_selects_nominal_and_failure(self):
        adapter=TypeAdapter(AllDroneToCloudV1Messages)
        base={"type":"command_ack","command_id":"11111111-1111-4111-8111-111111111111"}
        self.assertEqual(adapter.validate_python({**base,"status":"received"}).status,"received")
        failure=adapter.validate_python({**base,"status":"error","error_code":"INVALID_PARAMS","message":"Synthetic validation failure"})
        self.assertEqual(failure.error_message,"Synthetic validation failure")
        with self.assertRaises(ValidationError):adapter.validate_python({**base,"status":"error"})
    def test_non_finite_angles_are_rejected(self):
        adapter=TypeAdapter(AllCloudToDroneV1Commands)
        for bad in [float("nan"),float("inf"),float("-inf")]:
            with self.assertRaises(ValidationError):adapter.validate_python({"type":"gimbal-controller","payload":{"mode":"angle","pitch_deg":bad,"yaw_deg":0}})
    def test_timestamps_must_be_aware_and_are_normalised_to_utc(self):
        adapter=TypeAdapter(AllCloudToDroneV1Commands)
        payload={"mode":"angle","pitch_deg":1,"yaw_deg":2}
        with self.assertRaises(ValidationError):adapter.validate_python({"type":"gimbal-controller","timestamp":"2025-06-01T12:00:00","payload":payload})
        command=adapter.validate_python({"type":"gimbal-controller","timestamp":"2025-06-01T14:00:00+02:00","payload":payload})
        self.assertEqual(command.model_dump(mode="json")["timestamp"],"2025-06-01T12:00:00Z")
    def test_unknown_and_cross_mode_payload_fields_are_rejected(self):
        adapter=TypeAdapter(AllCloudToDroneV1Commands)
        for payload in [{"mode":"angle","pitch_deg":1,"yaw_deg":2,"pitch":3},{"mode":"rate","pitch_deg_s":1,"yaw_deg_s":2,"pitch_deg":5}]:
            with self.assertRaises(ValidationError):adapter.validate_python({"type":"gimbal-controller","payload":payload})

if __name__ == "__main__":unittest.main()
