"""JSON Schema documents for the wire format, as published in ``schemas/``."""

import json
from typing import Any

from pydantic import TypeAdapter

from .c2d_commands import AllCloudToDroneV1Commands
from .d2c_acknowledgements import AllDroneToCloudV1Messages

DIALECT = "https://json-schema.org/draft/2020-12/schema"

_UNIONS: dict[str, tuple[str, Any]] = {
    "c2d-commands.v1.schema.json": ("Cloud-to-drone command (v1)", AllCloudToDroneV1Commands),
    "d2c-messages.v1.schema.json": ("Drone-to-cloud message (v1)", AllDroneToCloudV1Messages),
}


# Wire name of the message-type discriminator in both directions.
_ROUTING_TAG = "type"


def _require_routing_tag(schema: dict[str, Any]) -> None:
    # The tag has a Python default, so Pydantic lists it as optional, yet the
    # discriminated union rejects a message without it. Validators that ignore the
    # OpenAPI "discriminator" keyword need it in "required" to agree with the models.
    for definition in schema.get("$defs", {}).values():
        if _ROUTING_TAG in definition.get("properties", {}):
            required = definition.setdefault("required", [])
            if _ROUTING_TAG not in required:
                required.append(_ROUTING_TAG)


def wire_schemas() -> dict[str, str]:
    """Return ``{file name: JSON text}`` for every published schema."""
    documents: dict[str, str] = {}
    for filename, (title, union) in _UNIONS.items():
        schema = TypeAdapter(union).json_schema(by_alias=True, mode="validation")
        _require_routing_tag(schema)
        document = {"$schema": DIALECT, "title": title, **schema}
        documents[filename] = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    return documents
