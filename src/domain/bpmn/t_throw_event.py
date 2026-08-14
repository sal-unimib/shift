from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree.ElementTree import QName

from src.domain.bpmn.cancel_event_definition import CancelEventDefinition
from src.domain.bpmn.compensate_event_definition import (
    CompensateEventDefinition,
)
from src.domain.bpmn.conditional_event_definition import (
    ConditionalEventDefinition,
)
from src.domain.bpmn.data_input import DataInput
from src.domain.bpmn.data_input_association import DataInputAssociation
from src.domain.bpmn.error_event_definition import ErrorEventDefinition
from src.domain.bpmn.escalation_event_definition import (
    EscalationEventDefinition,
)
from src.domain.bpmn.event_definition import EventDefinition
from src.domain.bpmn.input_set import InputSet
from src.domain.bpmn.link_event_definition import LinkEventDefinition
from src.domain.bpmn.message_event_definition import MessageEventDefinition
from src.domain.bpmn.signal_event_definition import SignalEventDefinition
from src.domain.bpmn.t_event import TEvent
from src.domain.bpmn.terminate_event_definition import TerminateEventDefinition
from src.domain.bpmn.timer_event_definition import TimerEventDefinition

__NAMESPACE__ = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class TThrowEvent(TEvent):
    class Meta:
        name = "tThrowEvent"

    data_input: list[DataInput] = field(
        default_factory=list,
        metadata={
            "name": "dataInput",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    data_input_association: list[DataInputAssociation] = field(
        default_factory=list,
        metadata={
            "name": "dataInputAssociation",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    input_set: None | InputSet = field(
        default=None,
        metadata={
            "name": "inputSet",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    timer_event_definition: list[TimerEventDefinition] = field(
        default_factory=list,
        metadata={
            "name": "timerEventDefinition",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    terminate_event_definition: list[TerminateEventDefinition] = field(
        default_factory=list,
        metadata={
            "name": "terminateEventDefinition",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    signal_event_definition: list[SignalEventDefinition] = field(
        default_factory=list,
        metadata={
            "name": "signalEventDefinition",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    message_event_definition: list[MessageEventDefinition] = field(
        default_factory=list,
        metadata={
            "name": "messageEventDefinition",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    link_event_definition: list[LinkEventDefinition] = field(
        default_factory=list,
        metadata={
            "name": "linkEventDefinition",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    escalation_event_definition: list[EscalationEventDefinition] = field(
        default_factory=list,
        metadata={
            "name": "escalationEventDefinition",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    error_event_definition: list[ErrorEventDefinition] = field(
        default_factory=list,
        metadata={
            "name": "errorEventDefinition",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    conditional_event_definition: list[ConditionalEventDefinition] = field(
        default_factory=list,
        metadata={
            "name": "conditionalEventDefinition",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    compensate_event_definition: list[CompensateEventDefinition] = field(
        default_factory=list,
        metadata={
            "name": "compensateEventDefinition",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    cancel_event_definition: list[CancelEventDefinition] = field(
        default_factory=list,
        metadata={
            "name": "cancelEventDefinition",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    event_definition: list[EventDefinition] = field(
        default_factory=list,
        metadata={
            "name": "eventDefinition",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    event_definition_ref: list[QName] = field(
        default_factory=list,
        metadata={
            "name": "eventDefinitionRef",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
