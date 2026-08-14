from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.bpmn.artifact import Artifact
from src.domain.bpmn.association import Association
from src.domain.bpmn.boundary_event import BoundaryEvent
from src.domain.bpmn.business_rule_task import BusinessRuleTask
from src.domain.bpmn.call_activity import CallActivity
from src.domain.bpmn.call_choreography import CallChoreography
from src.domain.bpmn.choreography_task import ChoreographyTask
from src.domain.bpmn.complex_gateway import ComplexGateway
from src.domain.bpmn.data_object import DataObject
from src.domain.bpmn.data_object_reference import DataObjectReference
from src.domain.bpmn.data_store_reference import DataStoreReference
from src.domain.bpmn.end_event import EndEvent
from src.domain.bpmn.event import Event
from src.domain.bpmn.event_based_gateway import EventBasedGateway
from src.domain.bpmn.exclusive_gateway import ExclusiveGateway
from src.domain.bpmn.flow_element import FlowElement
from src.domain.bpmn.group import Group
from src.domain.bpmn.implicit_throw_event import ImplicitThrowEvent
from src.domain.bpmn.inclusive_gateway import InclusiveGateway
from src.domain.bpmn.intermediate_catch_event import IntermediateCatchEvent
from src.domain.bpmn.intermediate_throw_event import IntermediateThrowEvent
from src.domain.bpmn.lane_set import LaneSet
from src.domain.bpmn.manual_task import ManualTask
from src.domain.bpmn.parallel_gateway import ParallelGateway
from src.domain.bpmn.receive_task import ReceiveTask
from src.domain.bpmn.script_task import ScriptTask
from src.domain.bpmn.send_task import SendTask
from src.domain.bpmn.sequence_flow import SequenceFlow
from src.domain.bpmn.service_task import ServiceTask
from src.domain.bpmn.start_event import StartEvent
from src.domain.bpmn.t_activity import TActivity
from src.domain.bpmn.t_ad_hoc_ordering import TAdHocOrdering
from src.domain.bpmn.t_choreography_activity import TChoreographyActivity
from src.domain.bpmn.t_expression import TExpression
from src.domain.bpmn.t_transaction_method_value import TTransactionMethodValue
from src.domain.bpmn.task import Task
from src.domain.bpmn.text_annotation import TextAnnotation
from src.domain.bpmn.user_task import UserTask

__NAMESPACE__ = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class TSubChoreography(TChoreographyActivity):
    class Meta:
        name = "tSubChoreography"

    user_task: list[UserTask] = field(
        default_factory=list,
        metadata={
            "name": "userTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    transaction: list[Transaction] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    task: list[Task] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    sub_process: list[SubProcess] = field(
        default_factory=list,
        metadata={
            "name": "subProcess",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    sub_choreography: list[SubChoreography] = field(
        default_factory=list,
        metadata={
            "name": "subChoreography",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    start_event: list[StartEvent] = field(
        default_factory=list,
        metadata={
            "name": "startEvent",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    service_task: list[ServiceTask] = field(
        default_factory=list,
        metadata={
            "name": "serviceTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    sequence_flow: list[SequenceFlow] = field(
        default_factory=list,
        metadata={
            "name": "sequenceFlow",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    send_task: list[SendTask] = field(
        default_factory=list,
        metadata={
            "name": "sendTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    script_task: list[ScriptTask] = field(
        default_factory=list,
        metadata={
            "name": "scriptTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    receive_task: list[ReceiveTask] = field(
        default_factory=list,
        metadata={
            "name": "receiveTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    parallel_gateway: list[ParallelGateway] = field(
        default_factory=list,
        metadata={
            "name": "parallelGateway",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    manual_task: list[ManualTask] = field(
        default_factory=list,
        metadata={
            "name": "manualTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    intermediate_throw_event: list[IntermediateThrowEvent] = field(
        default_factory=list,
        metadata={
            "name": "intermediateThrowEvent",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    intermediate_catch_event: list[IntermediateCatchEvent] = field(
        default_factory=list,
        metadata={
            "name": "intermediateCatchEvent",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    inclusive_gateway: list[InclusiveGateway] = field(
        default_factory=list,
        metadata={
            "name": "inclusiveGateway",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    implicit_throw_event: list[ImplicitThrowEvent] = field(
        default_factory=list,
        metadata={
            "name": "implicitThrowEvent",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    exclusive_gateway: list[ExclusiveGateway] = field(
        default_factory=list,
        metadata={
            "name": "exclusiveGateway",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    event_based_gateway: list[EventBasedGateway] = field(
        default_factory=list,
        metadata={
            "name": "eventBasedGateway",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    event: list[Event] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    end_event: list[EndEvent] = field(
        default_factory=list,
        metadata={
            "name": "endEvent",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    data_store_reference: list[DataStoreReference] = field(
        default_factory=list,
        metadata={
            "name": "dataStoreReference",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    data_object_reference: list[DataObjectReference] = field(
        default_factory=list,
        metadata={
            "name": "dataObjectReference",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    data_object: list[DataObject] = field(
        default_factory=list,
        metadata={
            "name": "dataObject",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    complex_gateway: list[ComplexGateway] = field(
        default_factory=list,
        metadata={
            "name": "complexGateway",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    choreography_task: list[ChoreographyTask] = field(
        default_factory=list,
        metadata={
            "name": "choreographyTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    call_choreography: list[CallChoreography] = field(
        default_factory=list,
        metadata={
            "name": "callChoreography",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    call_activity: list[CallActivity] = field(
        default_factory=list,
        metadata={
            "name": "callActivity",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    business_rule_task: list[BusinessRuleTask] = field(
        default_factory=list,
        metadata={
            "name": "businessRuleTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    boundary_event: list[BoundaryEvent] = field(
        default_factory=list,
        metadata={
            "name": "boundaryEvent",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    ad_hoc_sub_process: list[AdHocSubProcess] = field(
        default_factory=list,
        metadata={
            "name": "adHocSubProcess",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    flow_element: list[FlowElement] = field(
        default_factory=list,
        metadata={
            "name": "flowElement",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    text_annotation: list[TextAnnotation] = field(
        default_factory=list,
        metadata={
            "name": "textAnnotation",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    group: list[Group] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    association: list[Association] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    artifact: list[Artifact] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )


@dataclass(kw_only=True)
class SubChoreography(TSubChoreography):
    class Meta:
        name = "subChoreography"
        namespace = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class TSubProcess(TActivity):
    class Meta:
        name = "tSubProcess"

    lane_set: list[LaneSet] = field(
        default_factory=list,
        metadata={
            "name": "laneSet",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    user_task: list[UserTask] = field(
        default_factory=list,
        metadata={
            "name": "userTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    transaction: list[Transaction] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    task: list[Task] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    sub_process: list[SubProcess] = field(
        default_factory=list,
        metadata={
            "name": "subProcess",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    sub_choreography: list[SubChoreography] = field(
        default_factory=list,
        metadata={
            "name": "subChoreography",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    start_event: list[StartEvent] = field(
        default_factory=list,
        metadata={
            "name": "startEvent",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    service_task: list[ServiceTask] = field(
        default_factory=list,
        metadata={
            "name": "serviceTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    sequence_flow: list[SequenceFlow] = field(
        default_factory=list,
        metadata={
            "name": "sequenceFlow",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    send_task: list[SendTask] = field(
        default_factory=list,
        metadata={
            "name": "sendTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    script_task: list[ScriptTask] = field(
        default_factory=list,
        metadata={
            "name": "scriptTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    receive_task: list[ReceiveTask] = field(
        default_factory=list,
        metadata={
            "name": "receiveTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    parallel_gateway: list[ParallelGateway] = field(
        default_factory=list,
        metadata={
            "name": "parallelGateway",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    manual_task: list[ManualTask] = field(
        default_factory=list,
        metadata={
            "name": "manualTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    intermediate_throw_event: list[IntermediateThrowEvent] = field(
        default_factory=list,
        metadata={
            "name": "intermediateThrowEvent",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    intermediate_catch_event: list[IntermediateCatchEvent] = field(
        default_factory=list,
        metadata={
            "name": "intermediateCatchEvent",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    inclusive_gateway: list[InclusiveGateway] = field(
        default_factory=list,
        metadata={
            "name": "inclusiveGateway",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    implicit_throw_event: list[ImplicitThrowEvent] = field(
        default_factory=list,
        metadata={
            "name": "implicitThrowEvent",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    exclusive_gateway: list[ExclusiveGateway] = field(
        default_factory=list,
        metadata={
            "name": "exclusiveGateway",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    event_based_gateway: list[EventBasedGateway] = field(
        default_factory=list,
        metadata={
            "name": "eventBasedGateway",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    event: list[Event] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    end_event: list[EndEvent] = field(
        default_factory=list,
        metadata={
            "name": "endEvent",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    data_store_reference: list[DataStoreReference] = field(
        default_factory=list,
        metadata={
            "name": "dataStoreReference",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    data_object_reference: list[DataObjectReference] = field(
        default_factory=list,
        metadata={
            "name": "dataObjectReference",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    data_object: list[DataObject] = field(
        default_factory=list,
        metadata={
            "name": "dataObject",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    complex_gateway: list[ComplexGateway] = field(
        default_factory=list,
        metadata={
            "name": "complexGateway",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    choreography_task: list[ChoreographyTask] = field(
        default_factory=list,
        metadata={
            "name": "choreographyTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    call_choreography: list[CallChoreography] = field(
        default_factory=list,
        metadata={
            "name": "callChoreography",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    call_activity: list[CallActivity] = field(
        default_factory=list,
        metadata={
            "name": "callActivity",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    business_rule_task: list[BusinessRuleTask] = field(
        default_factory=list,
        metadata={
            "name": "businessRuleTask",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    boundary_event: list[BoundaryEvent] = field(
        default_factory=list,
        metadata={
            "name": "boundaryEvent",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    ad_hoc_sub_process: list[AdHocSubProcess] = field(
        default_factory=list,
        metadata={
            "name": "adHocSubProcess",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    flow_element: list[FlowElement] = field(
        default_factory=list,
        metadata={
            "name": "flowElement",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    text_annotation: list[TextAnnotation] = field(
        default_factory=list,
        metadata={
            "name": "textAnnotation",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    group: list[Group] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    association: list[Association] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    artifact: list[Artifact] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    triggered_by_event: bool = field(
        default=False,
        metadata={
            "name": "triggeredByEvent",
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class SubProcess(TSubProcess):
    class Meta:
        name = "subProcess"
        namespace = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class TAdHocSubProcess(TSubProcess):
    class Meta:
        name = "tAdHocSubProcess"

    completion_condition: None | TExpression = field(
        default=None,
        metadata={
            "name": "completionCondition",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    cancel_remaining_instances: bool = field(
        default=True,
        metadata={
            "name": "cancelRemainingInstances",
            "type": "Attribute",
        },
    )
    ordering: None | TAdHocOrdering = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class TTransaction(TSubProcess):
    class Meta:
        name = "tTransaction"

    method: str | TTransactionMethodValue = field(
        default=TTransactionMethodValue.COMPENSATE,
        metadata={
            "type": "Attribute",
        },
    )


@dataclass(kw_only=True)
class AdHocSubProcess(TAdHocSubProcess):
    class Meta:
        name = "adHocSubProcess"
        namespace = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class Transaction(TTransaction):
    class Meta:
        name = "transaction"
        namespace = "http://www.omg.org/spec/BPMN/20100524/MODEL"
