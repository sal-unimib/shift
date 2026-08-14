from src.domain.bpmn.activity import Activity
from src.domain.bpmn.artifact import Artifact
from src.domain.bpmn.assignment import Assignment
from src.domain.bpmn.association import Association
from src.domain.bpmn.auditing import Auditing
from src.domain.bpmn.base_element import BaseElement
from src.domain.bpmn.base_element_with_mixed_content import (
    BaseElementWithMixedContent,
)
from src.domain.bpmn.boundary_event import BoundaryEvent
from src.domain.bpmn.bounds import Bounds
from src.domain.bpmn.bpmndiagram import Bpmndiagram
from src.domain.bpmn.bpmnedge import Bpmnedge
from src.domain.bpmn.bpmnlabel import Bpmnlabel
from src.domain.bpmn.bpmnlabel_style import BpmnlabelStyle
from src.domain.bpmn.bpmnplane import Bpmnplane
from src.domain.bpmn.bpmnshape import Bpmnshape
from src.domain.bpmn.business_rule_task import BusinessRuleTask
from src.domain.bpmn.call_activity import CallActivity
from src.domain.bpmn.call_choreography import CallChoreography
from src.domain.bpmn.call_conversation import CallConversation
from src.domain.bpmn.callable_element import CallableElement
from src.domain.bpmn.cancel_event_definition import CancelEventDefinition
from src.domain.bpmn.catch_event import CatchEvent
from src.domain.bpmn.category import Category
from src.domain.bpmn.category_value import CategoryValue
from src.domain.bpmn.choreography import Choreography
from src.domain.bpmn.choreography_activity import ChoreographyActivity
from src.domain.bpmn.choreography_task import ChoreographyTask
from src.domain.bpmn.collaboration import Collaboration
from src.domain.bpmn.compensate_event_definition import (
    CompensateEventDefinition,
)
from src.domain.bpmn.complex_behavior_definition import (
    ComplexBehaviorDefinition,
)
from src.domain.bpmn.complex_gateway import ComplexGateway
from src.domain.bpmn.conditional_event_definition import (
    ConditionalEventDefinition,
)
from src.domain.bpmn.conversation import Conversation
from src.domain.bpmn.conversation_association import ConversationAssociation
from src.domain.bpmn.conversation_link import ConversationLink
from src.domain.bpmn.conversation_node import ConversationNode
from src.domain.bpmn.correlation_key import CorrelationKey
from src.domain.bpmn.correlation_property import CorrelationProperty
from src.domain.bpmn.correlation_property_binding import (
    CorrelationPropertyBinding,
)
from src.domain.bpmn.correlation_property_retrieval_expression import (
    CorrelationPropertyRetrievalExpression,
)
from src.domain.bpmn.correlation_subscription import CorrelationSubscription
from src.domain.bpmn.data_association import DataAssociation
from src.domain.bpmn.data_input import DataInput
from src.domain.bpmn.data_input_association import DataInputAssociation
from src.domain.bpmn.data_object import DataObject
from src.domain.bpmn.data_object_reference import DataObjectReference
from src.domain.bpmn.data_output import DataOutput
from src.domain.bpmn.data_output_association import DataOutputAssociation
from src.domain.bpmn.data_state import DataState
from src.domain.bpmn.data_store import DataStore
from src.domain.bpmn.data_store_reference import DataStoreReference
from src.domain.bpmn.definitions import Definitions
from src.domain.bpmn.diagram import Diagram
from src.domain.bpmn.diagram_element import DiagramElement
from src.domain.bpmn.documentation import Documentation
from src.domain.bpmn.edge import Edge
from src.domain.bpmn.end_event import EndEvent
from src.domain.bpmn.end_point import EndPoint
from src.domain.bpmn.error import Error
from src.domain.bpmn.error_event_definition import ErrorEventDefinition
from src.domain.bpmn.escalation import Escalation
from src.domain.bpmn.escalation_event_definition import (
    EscalationEventDefinition,
)
from src.domain.bpmn.event import Event
from src.domain.bpmn.event_based_gateway import EventBasedGateway
from src.domain.bpmn.event_definition import EventDefinition
from src.domain.bpmn.exclusive_gateway import ExclusiveGateway
from src.domain.bpmn.expression import Expression
from src.domain.bpmn.extension import Extension
from src.domain.bpmn.extension_elements import ExtensionElements
from src.domain.bpmn.flow_element import FlowElement
from src.domain.bpmn.flow_node import FlowNode
from src.domain.bpmn.font import Font
from src.domain.bpmn.formal_expression import FormalExpression
from src.domain.bpmn.gateway import Gateway
from src.domain.bpmn.global_business_rule_task import GlobalBusinessRuleTask
from src.domain.bpmn.global_choreography_task import GlobalChoreographyTask
from src.domain.bpmn.global_conversation import GlobalConversation
from src.domain.bpmn.global_manual_task import GlobalManualTask
from src.domain.bpmn.global_script_task import GlobalScriptTask
from src.domain.bpmn.global_task import GlobalTask
from src.domain.bpmn.global_user_task import GlobalUserTask
from src.domain.bpmn.group import Group
from src.domain.bpmn.human_performer import HumanPerformer
from src.domain.bpmn.implicit_throw_event import ImplicitThrowEvent
from src.domain.bpmn.import_mod import Import
from src.domain.bpmn.inclusive_gateway import InclusiveGateway
from src.domain.bpmn.input_set import InputSet
from src.domain.bpmn.interface import Interface
from src.domain.bpmn.intermediate_catch_event import IntermediateCatchEvent
from src.domain.bpmn.intermediate_throw_event import IntermediateThrowEvent
from src.domain.bpmn.io_binding import IoBinding
from src.domain.bpmn.io_specification import IoSpecification
from src.domain.bpmn.item_definition import ItemDefinition
from src.domain.bpmn.label import Label
from src.domain.bpmn.labeled_edge import LabeledEdge
from src.domain.bpmn.labeled_shape import LabeledShape
from src.domain.bpmn.lane_set import LaneSet
from src.domain.bpmn.link_event_definition import LinkEventDefinition
from src.domain.bpmn.loop_characteristics import LoopCharacteristics
from src.domain.bpmn.manual_task import ManualTask
from src.domain.bpmn.message import Message
from src.domain.bpmn.message_event_definition import MessageEventDefinition
from src.domain.bpmn.message_flow import MessageFlow
from src.domain.bpmn.message_flow_association import MessageFlowAssociation
from src.domain.bpmn.message_visible_kind import MessageVisibleKind
from src.domain.bpmn.monitoring import Monitoring
from src.domain.bpmn.multi_instance_loop_characteristics import (
    MultiInstanceLoopCharacteristics,
)
from src.domain.bpmn.node import Node
from src.domain.bpmn.operation import Operation
from src.domain.bpmn.output_set import OutputSet
from src.domain.bpmn.parallel_gateway import ParallelGateway
from src.domain.bpmn.participant import Participant
from src.domain.bpmn.participant_association import ParticipantAssociation
from src.domain.bpmn.participant_band_kind import ParticipantBandKind
from src.domain.bpmn.participant_multiplicity import ParticipantMultiplicity
from src.domain.bpmn.partner_entity import PartnerEntity
from src.domain.bpmn.partner_role import PartnerRole
from src.domain.bpmn.performer import Performer
from src.domain.bpmn.plane import Plane
from src.domain.bpmn.point import Point
from src.domain.bpmn.potential_owner import PotentialOwner
from src.domain.bpmn.process import Process
from src.domain.bpmn.property import Property
from src.domain.bpmn.receive_task import ReceiveTask
from src.domain.bpmn.relationship import Relationship
from src.domain.bpmn.rendering import Rendering
from src.domain.bpmn.resource import Resource
from src.domain.bpmn.resource_assignment_expression import (
    ResourceAssignmentExpression,
)
from src.domain.bpmn.resource_parameter import ResourceParameter
from src.domain.bpmn.resource_parameter_binding import ResourceParameterBinding
from src.domain.bpmn.resource_role import ResourceRole
from src.domain.bpmn.root_element import RootElement
from src.domain.bpmn.script import Script
from src.domain.bpmn.script_task import ScriptTask
from src.domain.bpmn.send_task import SendTask
from src.domain.bpmn.sequence_flow import SequenceFlow
from src.domain.bpmn.service_task import ServiceTask
from src.domain.bpmn.shape import Shape
from src.domain.bpmn.signal import Signal
from src.domain.bpmn.signal_event_definition import SignalEventDefinition
from src.domain.bpmn.standard_loop_characteristics import (
    StandardLoopCharacteristics,
)
from src.domain.bpmn.start_event import StartEvent
from src.domain.bpmn.style import Style
from src.domain.bpmn.t_activity import TActivity
from src.domain.bpmn.t_ad_hoc_ordering import TAdHocOrdering
from src.domain.bpmn.t_artifact import TArtifact
from src.domain.bpmn.t_assignment import TAssignment
from src.domain.bpmn.t_association import TAssociation
from src.domain.bpmn.t_association_direction import TAssociationDirection
from src.domain.bpmn.t_auditing import TAuditing
from src.domain.bpmn.t_base_element import TBaseElement
from src.domain.bpmn.t_base_element_with_mixed_content import (
    TBaseElementWithMixedContent,
)
from src.domain.bpmn.t_boundary_event import TBoundaryEvent
from src.domain.bpmn.t_business_rule_task import TBusinessRuleTask
from src.domain.bpmn.t_call_activity import TCallActivity
from src.domain.bpmn.t_call_choreography import TCallChoreography
from src.domain.bpmn.t_call_conversation import TCallConversation
from src.domain.bpmn.t_callable_element import TCallableElement
from src.domain.bpmn.t_cancel_event_definition import TCancelEventDefinition
from src.domain.bpmn.t_catch_event import TCatchEvent
from src.domain.bpmn.t_category import TCategory
from src.domain.bpmn.t_category_value import TCategoryValue
from src.domain.bpmn.t_choreography import TChoreography
from src.domain.bpmn.t_choreography_activity import TChoreographyActivity
from src.domain.bpmn.t_choreography_loop_type import TChoreographyLoopType
from src.domain.bpmn.t_choreography_task import TChoreographyTask
from src.domain.bpmn.t_collaboration import TCollaboration
from src.domain.bpmn.t_compensate_event_definition import (
    TCompensateEventDefinition,
)
from src.domain.bpmn.t_complex_behavior_definition import (
    TComplexBehaviorDefinition,
)
from src.domain.bpmn.t_complex_gateway import TComplexGateway
from src.domain.bpmn.t_conditional_event_definition import (
    TConditionalEventDefinition,
)
from src.domain.bpmn.t_conversation import TConversation
from src.domain.bpmn.t_conversation_association import TConversationAssociation
from src.domain.bpmn.t_conversation_link import TConversationLink
from src.domain.bpmn.t_conversation_node import TConversationNode
from src.domain.bpmn.t_correlation_key import TCorrelationKey
from src.domain.bpmn.t_correlation_property import TCorrelationProperty
from src.domain.bpmn.t_correlation_property_binding import (
    TCorrelationPropertyBinding,
)
from src.domain.bpmn.t_correlation_property_retrieval_expression import (
    TCorrelationPropertyRetrievalExpression,
)
from src.domain.bpmn.t_correlation_subscription import TCorrelationSubscription
from src.domain.bpmn.t_data_association import TDataAssociation
from src.domain.bpmn.t_data_input import TDataInput
from src.domain.bpmn.t_data_input_association import TDataInputAssociation
from src.domain.bpmn.t_data_object import TDataObject
from src.domain.bpmn.t_data_object_reference import TDataObjectReference
from src.domain.bpmn.t_data_output import TDataOutput
from src.domain.bpmn.t_data_output_association import TDataOutputAssociation
from src.domain.bpmn.t_data_state import TDataState
from src.domain.bpmn.t_data_store import TDataStore
from src.domain.bpmn.t_data_store_reference import TDataStoreReference
from src.domain.bpmn.t_definitions import TDefinitions
from src.domain.bpmn.t_documentation import TDocumentation
from src.domain.bpmn.t_end_event import TEndEvent
from src.domain.bpmn.t_end_point import TEndPoint
from src.domain.bpmn.t_error import TError
from src.domain.bpmn.t_error_event_definition import TErrorEventDefinition
from src.domain.bpmn.t_escalation import TEscalation
from src.domain.bpmn.t_escalation_event_definition import (
    TEscalationEventDefinition,
)
from src.domain.bpmn.t_event import TEvent
from src.domain.bpmn.t_event_based_gateway import TEventBasedGateway
from src.domain.bpmn.t_event_based_gateway_type import TEventBasedGatewayType
from src.domain.bpmn.t_event_definition import TEventDefinition
from src.domain.bpmn.t_exclusive_gateway import TExclusiveGateway
from src.domain.bpmn.t_expression import TExpression
from src.domain.bpmn.t_extension import TExtension
from src.domain.bpmn.t_extension_elements import TExtensionElements
from src.domain.bpmn.t_flow_element import TFlowElement
from src.domain.bpmn.t_flow_node import TFlowNode
from src.domain.bpmn.t_formal_expression import TFormalExpression
from src.domain.bpmn.t_gateway import TGateway
from src.domain.bpmn.t_gateway_direction import TGatewayDirection
from src.domain.bpmn.t_global_business_rule_task import TGlobalBusinessRuleTask
from src.domain.bpmn.t_global_choreography_task import TGlobalChoreographyTask
from src.domain.bpmn.t_global_conversation import TGlobalConversation
from src.domain.bpmn.t_global_manual_task import TGlobalManualTask
from src.domain.bpmn.t_global_script_task import TGlobalScriptTask
from src.domain.bpmn.t_global_task import TGlobalTask
from src.domain.bpmn.t_global_user_task import TGlobalUserTask
from src.domain.bpmn.t_group import TGroup
from src.domain.bpmn.t_human_performer import THumanPerformer
from src.domain.bpmn.t_implementation_value import TImplementationValue
from src.domain.bpmn.t_implicit_throw_event import TImplicitThrowEvent
from src.domain.bpmn.t_import import TImport
from src.domain.bpmn.t_inclusive_gateway import TInclusiveGateway
from src.domain.bpmn.t_input_output_binding import TInputOutputBinding
from src.domain.bpmn.t_input_output_specification import (
    TInputOutputSpecification,
)
from src.domain.bpmn.t_input_set import TInputSet
from src.domain.bpmn.t_interface import TInterface
from src.domain.bpmn.t_intermediate_catch_event import TIntermediateCatchEvent
from src.domain.bpmn.t_intermediate_throw_event import TIntermediateThrowEvent
from src.domain.bpmn.t_item_definition import TItemDefinition
from src.domain.bpmn.t_item_kind import TItemKind
from src.domain.bpmn.t_lane import (
    Lane,
    TLane,
    TLaneSet,
)
from src.domain.bpmn.t_link_event_definition import TLinkEventDefinition
from src.domain.bpmn.t_loop_characteristics import TLoopCharacteristics
from src.domain.bpmn.t_manual_task import TManualTask
from src.domain.bpmn.t_message import TMessage
from src.domain.bpmn.t_message_event_definition import TMessageEventDefinition
from src.domain.bpmn.t_message_flow import TMessageFlow
from src.domain.bpmn.t_message_flow_association import TMessageFlowAssociation
from src.domain.bpmn.t_monitoring import TMonitoring
from src.domain.bpmn.t_multi_instance_flow_condition import (
    TMultiInstanceFlowCondition,
)
from src.domain.bpmn.t_multi_instance_loop_characteristics import (
    TMultiInstanceLoopCharacteristics,
)
from src.domain.bpmn.t_operation import TOperation
from src.domain.bpmn.t_output_set import TOutputSet
from src.domain.bpmn.t_parallel_gateway import TParallelGateway
from src.domain.bpmn.t_participant import TParticipant
from src.domain.bpmn.t_participant_association import TParticipantAssociation
from src.domain.bpmn.t_participant_multiplicity import TParticipantMultiplicity
from src.domain.bpmn.t_partner_entity import TPartnerEntity
from src.domain.bpmn.t_partner_role import TPartnerRole
from src.domain.bpmn.t_performer import TPerformer
from src.domain.bpmn.t_potential_owner import TPotentialOwner
from src.domain.bpmn.t_process import TProcess
from src.domain.bpmn.t_process_type import TProcessType
from src.domain.bpmn.t_property import TProperty
from src.domain.bpmn.t_receive_task import TReceiveTask
from src.domain.bpmn.t_relationship import TRelationship
from src.domain.bpmn.t_relationship_direction import TRelationshipDirection
from src.domain.bpmn.t_rendering import TRendering
from src.domain.bpmn.t_resource import TResource
from src.domain.bpmn.t_resource_assignment_expression import (
    TResourceAssignmentExpression,
)
from src.domain.bpmn.t_resource_parameter import TResourceParameter
from src.domain.bpmn.t_resource_parameter_binding import (
    TResourceParameterBinding,
)
from src.domain.bpmn.t_resource_role import TResourceRole
from src.domain.bpmn.t_root_element import TRootElement
from src.domain.bpmn.t_script import TScript
from src.domain.bpmn.t_script_task import TScriptTask
from src.domain.bpmn.t_send_task import TSendTask
from src.domain.bpmn.t_sequence_flow import TSequenceFlow
from src.domain.bpmn.t_service_task import TServiceTask
from src.domain.bpmn.t_signal import TSignal
from src.domain.bpmn.t_signal_event_definition import TSignalEventDefinition
from src.domain.bpmn.t_standard_loop_characteristics import (
    TStandardLoopCharacteristics,
)
from src.domain.bpmn.t_start_event import TStartEvent
from src.domain.bpmn.t_sub_choreography import (
    AdHocSubProcess,
    SubChoreography,
    SubProcess,
    TAdHocSubProcess,
    Transaction,
    TSubChoreography,
    TSubProcess,
    TTransaction,
)
from src.domain.bpmn.t_sub_conversation import (
    SubConversation,
    TSubConversation,
)
from src.domain.bpmn.t_task import TTask
from src.domain.bpmn.t_terminate_event_definition import (
    TTerminateEventDefinition,
)
from src.domain.bpmn.t_text import TText
from src.domain.bpmn.t_text_annotation import TTextAnnotation
from src.domain.bpmn.t_throw_event import TThrowEvent
from src.domain.bpmn.t_timer_event_definition import TTimerEventDefinition
from src.domain.bpmn.t_transaction_method_value import TTransactionMethodValue
from src.domain.bpmn.t_user_task import TUserTask
from src.domain.bpmn.task import Task
from src.domain.bpmn.terminate_event_definition import TerminateEventDefinition
from src.domain.bpmn.text import Text
from src.domain.bpmn.text_annotation import TextAnnotation
from src.domain.bpmn.throw_event import ThrowEvent
from src.domain.bpmn.timer_event_definition import TimerEventDefinition
from src.domain.bpmn.user_task import UserTask

__all__ = [
    "Activity",
    "Artifact",
    "Assignment",
    "Association",
    "Auditing",
    "BaseElement",
    "BaseElementWithMixedContent",
    "BoundaryEvent",
    "Bounds",
    "Bpmndiagram",
    "Bpmnedge",
    "Bpmnlabel",
    "BpmnlabelStyle",
    "Bpmnplane",
    "Bpmnshape",
    "BusinessRuleTask",
    "CallActivity",
    "CallChoreography",
    "CallConversation",
    "CallableElement",
    "CancelEventDefinition",
    "CatchEvent",
    "Category",
    "CategoryValue",
    "Choreography",
    "ChoreographyActivity",
    "ChoreographyTask",
    "Collaboration",
    "CompensateEventDefinition",
    "ComplexBehaviorDefinition",
    "ComplexGateway",
    "ConditionalEventDefinition",
    "Conversation",
    "ConversationAssociation",
    "ConversationLink",
    "ConversationNode",
    "CorrelationKey",
    "CorrelationProperty",
    "CorrelationPropertyBinding",
    "CorrelationPropertyRetrievalExpression",
    "CorrelationSubscription",
    "DataAssociation",
    "DataInput",
    "DataInputAssociation",
    "DataObject",
    "DataObjectReference",
    "DataOutput",
    "DataOutputAssociation",
    "DataState",
    "DataStore",
    "DataStoreReference",
    "Definitions",
    "Diagram",
    "DiagramElement",
    "Documentation",
    "Edge",
    "EndEvent",
    "EndPoint",
    "Error",
    "ErrorEventDefinition",
    "Escalation",
    "EscalationEventDefinition",
    "Event",
    "EventBasedGateway",
    "EventDefinition",
    "ExclusiveGateway",
    "Expression",
    "Extension",
    "ExtensionElements",
    "FlowElement",
    "FlowNode",
    "Font",
    "FormalExpression",
    "Gateway",
    "GlobalBusinessRuleTask",
    "GlobalChoreographyTask",
    "GlobalConversation",
    "GlobalManualTask",
    "GlobalScriptTask",
    "GlobalTask",
    "GlobalUserTask",
    "Group",
    "HumanPerformer",
    "ImplicitThrowEvent",
    "Import",
    "InclusiveGateway",
    "InputSet",
    "Interface",
    "IntermediateCatchEvent",
    "IntermediateThrowEvent",
    "IoBinding",
    "IoSpecification",
    "ItemDefinition",
    "Label",
    "LabeledEdge",
    "LabeledShape",
    "LaneSet",
    "LinkEventDefinition",
    "LoopCharacteristics",
    "ManualTask",
    "Message",
    "MessageEventDefinition",
    "MessageFlow",
    "MessageFlowAssociation",
    "MessageVisibleKind",
    "Monitoring",
    "MultiInstanceLoopCharacteristics",
    "Node",
    "Operation",
    "OutputSet",
    "ParallelGateway",
    "Participant",
    "ParticipantAssociation",
    "ParticipantBandKind",
    "ParticipantMultiplicity",
    "PartnerEntity",
    "PartnerRole",
    "Performer",
    "Plane",
    "Point",
    "PotentialOwner",
    "Process",
    "Property",
    "ReceiveTask",
    "Relationship",
    "Rendering",
    "Resource",
    "ResourceAssignmentExpression",
    "ResourceParameter",
    "ResourceParameterBinding",
    "ResourceRole",
    "RootElement",
    "Script",
    "ScriptTask",
    "SendTask",
    "SequenceFlow",
    "ServiceTask",
    "Shape",
    "Signal",
    "SignalEventDefinition",
    "StandardLoopCharacteristics",
    "StartEvent",
    "Style",
    "TActivity",
    "TAdHocOrdering",
    "TArtifact",
    "TAssignment",
    "TAssociation",
    "TAssociationDirection",
    "TAuditing",
    "TBaseElement",
    "TBaseElementWithMixedContent",
    "TBoundaryEvent",
    "TBusinessRuleTask",
    "TCallActivity",
    "TCallChoreography",
    "TCallConversation",
    "TCallableElement",
    "TCancelEventDefinition",
    "TCatchEvent",
    "TCategory",
    "TCategoryValue",
    "TChoreography",
    "TChoreographyActivity",
    "TChoreographyLoopType",
    "TChoreographyTask",
    "TCollaboration",
    "TCompensateEventDefinition",
    "TComplexBehaviorDefinition",
    "TComplexGateway",
    "TConditionalEventDefinition",
    "TConversation",
    "TConversationAssociation",
    "TConversationLink",
    "TConversationNode",
    "TCorrelationKey",
    "TCorrelationProperty",
    "TCorrelationPropertyBinding",
    "TCorrelationPropertyRetrievalExpression",
    "TCorrelationSubscription",
    "TDataAssociation",
    "TDataInput",
    "TDataInputAssociation",
    "TDataObject",
    "TDataObjectReference",
    "TDataOutput",
    "TDataOutputAssociation",
    "TDataState",
    "TDataStore",
    "TDataStoreReference",
    "TDefinitions",
    "TDocumentation",
    "TEndEvent",
    "TEndPoint",
    "TError",
    "TErrorEventDefinition",
    "TEscalation",
    "TEscalationEventDefinition",
    "TEvent",
    "TEventBasedGateway",
    "TEventBasedGatewayType",
    "TEventDefinition",
    "TExclusiveGateway",
    "TExpression",
    "TExtension",
    "TExtensionElements",
    "TFlowElement",
    "TFlowNode",
    "TFormalExpression",
    "TGateway",
    "TGatewayDirection",
    "TGlobalBusinessRuleTask",
    "TGlobalChoreographyTask",
    "TGlobalConversation",
    "TGlobalManualTask",
    "TGlobalScriptTask",
    "TGlobalTask",
    "TGlobalUserTask",
    "TGroup",
    "THumanPerformer",
    "TImplementationValue",
    "TImplicitThrowEvent",
    "TImport",
    "TInclusiveGateway",
    "TInputOutputBinding",
    "TInputOutputSpecification",
    "TInputSet",
    "TInterface",
    "TIntermediateCatchEvent",
    "TIntermediateThrowEvent",
    "TItemDefinition",
    "TItemKind",
    "Lane",
    "TLane",
    "TLaneSet",
    "TLinkEventDefinition",
    "TLoopCharacteristics",
    "TManualTask",
    "TMessage",
    "TMessageEventDefinition",
    "TMessageFlow",
    "TMessageFlowAssociation",
    "TMonitoring",
    "TMultiInstanceFlowCondition",
    "TMultiInstanceLoopCharacteristics",
    "TOperation",
    "TOutputSet",
    "TParallelGateway",
    "TParticipant",
    "TParticipantAssociation",
    "TParticipantMultiplicity",
    "TPartnerEntity",
    "TPartnerRole",
    "TPerformer",
    "TPotentialOwner",
    "TProcess",
    "TProcessType",
    "TProperty",
    "TReceiveTask",
    "TRelationship",
    "TRelationshipDirection",
    "TRendering",
    "TResource",
    "TResourceAssignmentExpression",
    "TResourceParameter",
    "TResourceParameterBinding",
    "TResourceRole",
    "TRootElement",
    "TScript",
    "TScriptTask",
    "TSendTask",
    "TSequenceFlow",
    "TServiceTask",
    "TSignal",
    "TSignalEventDefinition",
    "TStandardLoopCharacteristics",
    "TStartEvent",
    "AdHocSubProcess",
    "SubChoreography",
    "SubProcess",
    "TAdHocSubProcess",
    "TSubChoreography",
    "TSubProcess",
    "TTransaction",
    "Transaction",
    "SubConversation",
    "TSubConversation",
    "TTask",
    "TTerminateEventDefinition",
    "TText",
    "TTextAnnotation",
    "TThrowEvent",
    "TTimerEventDefinition",
    "TTransactionMethodValue",
    "TUserTask",
    "Task",
    "TerminateEventDefinition",
    "Text",
    "TextAnnotation",
    "ThrowEvent",
    "TimerEventDefinition",
    "UserTask",
]
