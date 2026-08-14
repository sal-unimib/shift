from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.bpmn.bpmndiagram import Bpmndiagram
from src.domain.bpmn.cancel_event_definition import CancelEventDefinition
from src.domain.bpmn.category import Category
from src.domain.bpmn.choreography import Choreography
from src.domain.bpmn.collaboration import Collaboration
from src.domain.bpmn.compensate_event_definition import (
    CompensateEventDefinition,
)
from src.domain.bpmn.conditional_event_definition import (
    ConditionalEventDefinition,
)
from src.domain.bpmn.correlation_property import CorrelationProperty
from src.domain.bpmn.data_store import DataStore
from src.domain.bpmn.end_point import EndPoint
from src.domain.bpmn.error import Error
from src.domain.bpmn.error_event_definition import ErrorEventDefinition
from src.domain.bpmn.escalation import Escalation
from src.domain.bpmn.escalation_event_definition import (
    EscalationEventDefinition,
)
from src.domain.bpmn.event_definition import EventDefinition
from src.domain.bpmn.extension import Extension
from src.domain.bpmn.global_business_rule_task import GlobalBusinessRuleTask
from src.domain.bpmn.global_choreography_task import GlobalChoreographyTask
from src.domain.bpmn.global_conversation import GlobalConversation
from src.domain.bpmn.global_manual_task import GlobalManualTask
from src.domain.bpmn.global_script_task import GlobalScriptTask
from src.domain.bpmn.global_task import GlobalTask
from src.domain.bpmn.global_user_task import GlobalUserTask
from src.domain.bpmn.import_mod import Import
from src.domain.bpmn.interface import Interface
from src.domain.bpmn.item_definition import ItemDefinition
from src.domain.bpmn.link_event_definition import LinkEventDefinition
from src.domain.bpmn.message import Message
from src.domain.bpmn.message_event_definition import MessageEventDefinition
from src.domain.bpmn.partner_entity import PartnerEntity
from src.domain.bpmn.partner_role import PartnerRole
from src.domain.bpmn.process import Process
from src.domain.bpmn.relationship import Relationship
from src.domain.bpmn.resource import Resource
from src.domain.bpmn.root_element import RootElement
from src.domain.bpmn.signal import Signal
from src.domain.bpmn.signal_event_definition import SignalEventDefinition
from src.domain.bpmn.terminate_event_definition import TerminateEventDefinition
from src.domain.bpmn.timer_event_definition import TimerEventDefinition

__NAMESPACE__ = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class TDefinitions:
    class Meta:
        name = "tDefinitions"

    import_value: list[Import] = field(
        default_factory=list,
        metadata={
            "name": "import",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    extension: list[Extension] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    signal: list[Signal] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    resource: list[Resource] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    process: list[Process] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    partner_role: list[PartnerRole] = field(
        default_factory=list,
        metadata={
            "name": "partnerRole",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    partner_entity: list[PartnerEntity] = field(
        default_factory=list,
        metadata={
            "name": "partnerEntity",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    message: list[Message] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    item_definition: list[ItemDefinition] = field(
        default_factory=list,
        metadata={
            "name": "itemDefinition",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    interface: list[Interface] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    global_user_task: list[GlobalUserTask] = field(
        default_factory=list,
        metadata={
            "name": "globalUserTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    global_task: list[GlobalTask] = field(
        default_factory=list,
        metadata={
            "name": "globalTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    global_script_task: list[GlobalScriptTask] = field(
        default_factory=list,
        metadata={
            "name": "globalScriptTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    global_manual_task: list[GlobalManualTask] = field(
        default_factory=list,
        metadata={
            "name": "globalManualTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    global_business_rule_task: list[GlobalBusinessRuleTask] = field(
        default_factory=list,
        metadata={
            "name": "globalBusinessRuleTask",
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
    escalation: list[Escalation] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    error: list[Error] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    end_point: list[EndPoint] = field(
        default_factory=list,
        metadata={
            "name": "endPoint",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    data_store: list[DataStore] = field(
        default_factory=list,
        metadata={
            "name": "dataStore",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    correlation_property: list[CorrelationProperty] = field(
        default_factory=list,
        metadata={
            "name": "correlationProperty",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    global_conversation: list[GlobalConversation] = field(
        default_factory=list,
        metadata={
            "name": "globalConversation",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    global_choreography_task: list[GlobalChoreographyTask] = field(
        default_factory=list,
        metadata={
            "name": "globalChoreographyTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    choreography: list[Choreography] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    collaboration: list[Collaboration] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    category: list[Category] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    root_element: list[RootElement] = field(
        default_factory=list,
        metadata={
            "name": "rootElement",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    bpmndiagram: list[Bpmndiagram] = field(
        default_factory=list,
        metadata={
            "name": "BPMNDiagram",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/DI",
        },
    )
    relationship: list[Relationship] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    id: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    name: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    target_namespace: str = field(
        metadata={
            "name": "targetNamespace",
            "type": "Attribute",
        }
    )
    expression_language: str = field(
        default="http://www.w3.org/1999/XPath",
        metadata={
            "name": "expressionLanguage",
            "type": "Attribute",
        },
    )
    type_language: str = field(
        default="http://www.w3.org/2001/XMLSchema",
        metadata={
            "name": "typeLanguage",
            "type": "Attribute",
        },
    )
    exporter: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
    exporter_version: None | str = field(
        default=None,
        metadata={
            "name": "exporterVersion",
            "type": "Attribute",
        },
    )
    other_attributes: dict[str, str] = field(
        default_factory=dict,
        metadata={
            "type": "Attributes",
            "namespace": "##other",
        },
    )
