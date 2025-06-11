from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .common_types import (
    WIRE_MODEL_CONFIG,
    CommandAckStatus,
    SpecificErrorCode,
    UtcDatetime,
    utc_now,
)


class BaseD2CMessage(BaseModel):
    """Envelope shared by every drone-to-cloud message.

    Unknown keys are ignored on purpose: the cloud should keep accepting
    acknowledgements from firmware that adds fields ahead of a schema release.
    """

    model_config = WIRE_MODEL_CONFIG

    message_id: UUID = Field(
        default_factory=uuid4,
        description="Unique ID for this D2C message instance.",
    )
    timestamp_utc: UtcDatetime = Field(
        default_factory=utc_now,
        alias="timestamp",
        description="When the drone generated the message. Must carry a UTC offset; normalised to UTC.",
    )
    version: Literal["1.0"] = "1.0"
    message_type_d2c: str = Field(
        ..., alias="type", description="Discriminator: Type of the D2C message."
    )


class BaseCommandAckPayload(BaseD2CMessage):
    message_type_d2c: Literal["command_ack"] = Field("command_ack", alias="type")
    command_id: UUID = Field(
        ...,
        description="The ID of the command this acknowledgement is for.",
    )


class CommandAckNominal(BaseCommandAckPayload):
    status: Literal[CommandAckStatus.RECEIVED, CommandAckStatus.EXECUTED]


class CommandAckFailure(BaseCommandAckPayload):
    status: Literal[CommandAckStatus.ERROR]
    error_code: SpecificErrorCode = Field(
        ...,
        description="A machine-readable error code if the command failed or was rejected.",
    )
    error_message: str | None = Field(
        None,
        alias="message",
        description="A human-readable message providing more details about an error.",
    )


CommandAcknowledgementUnion = Annotated[
    CommandAckNominal | CommandAckFailure, Field(discriminator="status")
]

# The outer discriminator routes by message type; today only acknowledgements exist,
# and new D2C message families are added as further members of this union.
AllDroneToCloudV1Messages = Annotated[
    CommandAcknowledgementUnion, Field(discriminator="message_type_d2c")
]
