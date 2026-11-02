from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import src.domain.bpmn as bpmn_model
from src.domain.enums import FHIRRelationshipType, CFGNodeType, CFGGatewayClass, CFGGatewayDirection, CFGEventType
from src.domain.temporal_constraint import FHIRTemporalConstraint, TemporalConstraint

class FHIRExecutionCondition:
    """
    Represents a condition on a node in the clinical pathway graph.
    It corresponds to the 'condition' field in FHIR PlanDefinition.action.
    """

    expression : str
    description : str

    def __init__(self, expression : str, description : str):
        self.expression = expression
        self.description = description
    
    def to_formal_expression(self) -> bpmn_model.TFormalExpression:
        """
        Preserve the source expression using the BPMN tFormalExpression type.

        Expression-language translation belongs to engine-specific enrichment.

        :return: Typed BPMN expression retaining the FHIR expression text.
        :rtype: bpmn_model.TFormalExpression
        """
        return bpmn_model.TFormalExpression(content=[self.expression])

    def to_json(self) -> Dict[str, Any]:
        """
        Convert the FHIRExecutionCondition to a JSON object.

        :return: JSON object representing the FHIRExecutionCondition.
        :rtype: Dict[str, Any]
        """
        return {
            "expression": self.expression,
            "description": self.description,
        }
    
    @staticmethod
    def from_json(json_payload: Dict[str, Any]) -> "FHIRExecutionCondition":
        """
        Convert a JSON object to a FHIRExecutionCondition.

        :param json_payload: JSON object representing the FHIRExecutionCondition.
        :type json_payload: Dict[str, Any]
        :return: FHIRExecutionCondition represented by the JSON object.
        :rtype: FHIRExecutionCondition
        """
        return FHIRExecutionCondition(
            expression=json_payload["expression"],
            description=json_payload["description"],
        )

class CFGEdge:
    """
    Represents an edge in the therapeutic plan graph intermediate representation.
    """

    id : str
    """Edge identifier."""
    source : "CFGNode"
    """Source node."""
    target : "CFGNode"
    """Target node."""
    relationship: FHIRRelationshipType
    """Relationship type. Corresponds to PlanDefinition.action.relatedAction.relationship."""
    execution_condition : Optional[FHIRExecutionCondition]
    """Execution condition of the target action. Corresponds to 'condition' field in FHIR PlanDefinition.action."""

    def __init__(
        self,
        source: "CFGNode",
        target: "CFGNode",
        relationship: FHIRRelationshipType,
        execution_condition: Optional[FHIRExecutionCondition] = None
    ):
        self.id = source.id + "_to_" + target.id
        self.source = source
        self.target = target
        self.relationship = relationship
        self.execution_condition = execution_condition
    
    def to_json(self) -> Dict[str, Any]:
        """
        Convert the Edge to a JSON object.

        :return: JSON object representing the Edge.
        :rtype: Dict[str, Any]
        """
        return {
            "id": self.id,
            "source": self.source.id,
            "target": self.target.id,
            "relationship": self.relationship.value,
            "execution_condition": self.execution_condition.to_json() if self.execution_condition else None,
        }
    
    def clone(self) -> "CFGEdge":
        """
        Returns a deep copy of the edge.

        :return: A deep copy of the edge.
        :rtype: CFGEdge
        """
        return CFGEdge(
            source=self.source,
            target=self.target,
            relationship=self.relationship,
            execution_condition=self.execution_condition,
        )

class CFGNode(ABC):
    """Base CFG node class."""

    id :  str
    """Node identifier. Corresponds to PlanDefinition.action.linkId."""
    node_type : CFGNodeType
    """Type of the node."""
    incoming : List[CFGEdge]
    """List of incoming edges."""
    outgoing : List[CFGEdge]
    """List of outgoing edges."""

    def __init__(self, id: str, node_type: CFGNodeType):
        self.id = id
        self.node_type = node_type
        self.incoming = []
        self.outgoing = []
    
    @abstractmethod
    def to_json(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def clone(self) -> "CFGNode":
        pass

class FakeNode(CFGNode):

    def __init__(self, id):
        super().__init__(id, CFGNodeType.FAKE)

    def to_json(self) -> Dict[str, Any]:
        """
        Convert the FakeNode to a JSON object.

        :return: JSON object representing the FakeNode.
        :rtype: Dict[str, Any]
        """
        return {
            "id": self.id,
            "node_type" : self.node_type.value,
            "incoming": [e.id for e in self.incoming],
            "outgoing": [e.id for e in self.outgoing],
        }
    
    def clone(self) -> 'FakeNode':
        """
        Clone the FakeNode.

        :return: Cloned FakeNode.
        :rtype: FakeNode
        """
        return FakeNode(
            id=self.id
        )

class ActionNode(CFGNode):
    """Represents an action from the clinical pathway extracted from PlanDefinition"""

    title : str
    """Node title. Corresponds to PlanDefinition.action.title."""
    activity_definition : str
    """ActivityDefinition identifier of the action. Extracted from to PlanDefinition.action.definitionCanonical."""
    fhir_temporal_constraint : Optional[FHIRTemporalConstraint]
    """Temporal constraint of the action. Extracted from PlanDefinition.action.timing and PlanDefinition.action.relatedAction.offsetDuration."""
    temporal_constraint : Optional[TemporalConstraint]
    """Temporal constraint of the action. Extracted from PlanDefinition.action.timing and PlanDefinition.action.relatedAction.offsetDuration."""
    temporal_constraints: List[TemporalConstraint]
    """Complete action-level declarations when duration and iteration coexist."""
    attributes : Dict[str, str]
    """Node attributes. Derived from PlanDefinition.action.dynamicValue."""

    def __init__(
        self,
        id: str,
        title: str,
        activity_definition: str,
        fhir_temporal_constraint: Optional[FHIRTemporalConstraint] = None,
        temporal_constraint: Optional[TemporalConstraint] = None,
        attributes: Optional[Dict[str, str]] = None,
        temporal_constraints: Optional[List[TemporalConstraint]] = None,
    ):
        """
        Initialize temporal/action metadata without dropping optional combined constraints.

        :param id: CFG node identifier.
        :type id: str
        :param title: Action title.
        :type title: str
        :param activity_definition: Referenced ActivityDefinition logical ID.
        :type activity_definition: str
        :param fhir_temporal_constraint: Source FHIR temporal metadata.
        :type fhir_temporal_constraint: Optional[FHIRTemporalConstraint]
        :param temporal_constraint: Legacy scalar declaration retained for compatibility.
        :type temporal_constraint: Optional[TemporalConstraint]
        :param attributes: Action parameters, copied into a new dictionary.
        :type attributes: Optional[Dict[str, str]]
        :param temporal_constraints: Complete action declarations when duration and iteration coexist.
        :type temporal_constraints: Optional[List[TemporalConstraint]]
        """
        super().__init__(id, CFGNodeType.ACTION)
        self.title = title
        self.activity_definition = activity_definition
        self.fhir_temporal_constraint = fhir_temporal_constraint
        self.temporal_constraint = temporal_constraint
        self.attributes = dict(attributes or {})
        self.temporal_constraints = list(temporal_constraints) if temporal_constraints is not None else (
            [temporal_constraint] if temporal_constraint is not None else [])
        if self.temporal_constraint is None and self.temporal_constraints:
            self.temporal_constraint = self.temporal_constraints[-1]
        elif self.temporal_constraint is not None:
            for constraint in self.temporal_constraints:
                if constraint.to_json() == self.temporal_constraint.to_json():
                    self.temporal_constraint = constraint
                    break
    
    def to_json(self) -> Dict[str, Any]:
        """
        Convert the ActionNode to a JSON object.

        :return: JSON object representing the ActionNode.
        :rtype: Dict[str, Any]
        """
        result = {
            "id": self.id,
            "node_type" : self.node_type.value,
            "title": self.title,
            "activity_definition": self.activity_definition,
            "fhir_temporal_constraint": self.fhir_temporal_constraint.to_json() if self.fhir_temporal_constraint else None,
            "temporal_constraint": self.temporal_constraint.to_json() if self.temporal_constraint else None,
            "attributes": self.attributes,
            "incoming": [e.id for e in self.incoming],
            "outgoing": [e.id for e in self.outgoing],
        }
        if len(self.temporal_constraints) > 1:
            result["temporal_constraints"] = [constraint.to_json() for constraint in self.temporal_constraints]
        return result
    
    def clone(self) -> 'ActionNode':
        """
        Clone the ActionNode.

        :return: Cloned ActionNode.
        :rtype: ActionNode
        """
        return ActionNode(
            id=self.id,
            title=self.title,
            activity_definition=self.activity_definition,
            fhir_temporal_constraint=self.fhir_temporal_constraint,
            temporal_constraint=self.temporal_constraint,
            attributes=self.attributes.copy(),
            temporal_constraints=list(self.temporal_constraints),
        )

class GatewayNode(CFGNode):
    """Represents a gateway in the clinical pathway for the Control Flow Graph representation."""

    gateway_class : CFGGatewayClass
    """Type of the gateway."""
    gateway_direction : CFGGatewayDirection
    """Direction of the gateway."""
    
    def __init__(self, id: str, gateway_class: CFGGatewayClass, gateway_direction: CFGGatewayDirection):
        super().__init__(id, CFGNodeType.GATEWAY)
        self.gateway_class = gateway_class
        self.gateway_direction = gateway_direction
        
    def to_json(self) -> Dict[str, Any]:
        """
        Convert the GatewayNode to a JSON object.

        :return: JSON object representing the GatewayNode.
        :rtype: Dict[str, Any]
        """
        return {
            "id": self.id,
            "node_type" : self.node_type.value,
            "gateway_class": self.gateway_class.value,
            "gateway_direction": self.gateway_direction.value,
            "incoming": [e.id for e in self.incoming],
            "outgoing": [e.id for e in self.outgoing],
        }
    
    def clone(self) -> "GatewayNode":
        """
        Clone the GatewayNode.

        :return: Cloned GatewayNode.
        :rtype: GatewayNode
        """
        return GatewayNode(
            id=self.id,
            gateway_class=self.gateway_class,
            gateway_direction=self.gateway_direction,
        )

class EventNode(CFGNode):
    """Represents an event in the clinical pathway for the Control Flow Graph representation."""

    event_type : CFGEventType
    """Type of the event."""
    
    def __init__(self, id: str, event_type: CFGEventType, node_type: CFGNodeType = CFGNodeType.EVENT):
        if node_type not in [CFGNodeType.EVENT, CFGNodeType.TIMER_EVENT]:
            raise ValueError("Invalid node type for event node")
        super().__init__(id, node_type)
        self.event_type = event_type
        
    def to_json(self) -> Dict[str, Any]:
        """
        Convert the EventNode to a JSON object.

        :return: JSON object representing the EventNode.
        :rtype: Dict[str, Any]
        """
        return {
            "id": self.id,
            "node_type" : self.node_type.value,
            "event_type": self.event_type.value,
            "incoming": [e.id for e in self.incoming],
            "outgoing": [e.id for e in self.outgoing],
        }
    
    def clone(self) -> "EventNode":
        """
        Clone the EventNode.

        :return: Cloned EventNode.
        :rtype: EventNode
        """
        return EventNode(
            id=self.id,
            event_type=self.event_type,
            node_type=self.node_type,
        )

class TimerEventNode(EventNode):
    """Represents a timer event in the clinical pathway for the Control Flow Graph representation."""

    temporal_constraint : TemporalConstraint
    """Temporal constraint of the event."""
    
    def __init__(self, id: str, event_type: CFGEventType, temporal_constraint: TemporalConstraint):
        if event_type == CFGEventType.END:
            raise ValueError("End events cannot have a temporal constraint")
        super().__init__(id, event_type, CFGNodeType.TIMER_EVENT)
        self.temporal_constraint = temporal_constraint
        
    def to_json(self) -> Dict[str, Any]:
        """
        Convert the TimerEventNode to a JSON object.

        :return: JSON object representing the TimerEventNode.
        :rtype: Dict[str, Any]
        """
        return {
            "id": self.id,
            "node_type" : CFGNodeType.TIMER_EVENT.value,
            "event_type": self.event_type.value,
            "temporal_constraint": self.temporal_constraint.to_json(),
            "incoming": [e.id for e in self.incoming],
            "outgoing": [e.id for e in self.outgoing],
        }
    
    def clone(self) -> 'TimerEventNode':
        """
        Clone the TimerEventNode.

        :return: Cloned TimerEventNode.
        :rtype: TimerEventNode
        """
        return TimerEventNode(
            id=self.id,
            event_type=self.event_type,
            temporal_constraint=self.temporal_constraint,
        )

class BlockNode(CFGNode):
    """Represents a block of nodes in the clinical pathway for the Control Flow Graph representation."""
    
    title : Optional[str]
    """Title of the block."""
    nodes : Dict[str, CFGNode]
    """Dictionary of nodes in the block."""
    edges : Dict[str, CFGEdge]
    """Dictionary of edges in the block."""
    
    def __init__(self, id: str, title: Optional[str] = None):
        super().__init__(id, CFGNodeType.BLOCK)
        self.title = title
        self.nodes = {}
        self.edges = {}
    
    def add_node(self, node: CFGNode):
        """
        Add a node to the block.

        :param node: Node to add.
        :type node: CFGNode
        """
        self.nodes[node.id] = node
    
    def add_edge(self, edge: CFGEdge, update_nodes: bool = False):
        """
        Add an edge to the block.

        :param edge: Edge to add.
        :type edge: CFGEdge
        """
        self.edges[edge.id] = edge
        if update_nodes:
            self.nodes[edge.source.id].outgoing.append(self.edges[edge.id])
            self.nodes[edge.target.id].incoming.append(self.edges[edge.id])
    
    def to_json(self) -> Dict[str, Any]:
        """
        Convert the BlockNode to a JSON object.

        :return: JSON object representing the BlockNode.
        :rtype: Dict[str, Any]
        """
        return {
            "id": self.id,
            "node_type" : self.node_type.value,
            "title": self.title,
            "nodes": {k: v.to_json() for k, v in self.nodes.items()},
            "edges": {k: v.to_json() for k, v in self.edges.items()},
            "incoming": [e.id for e in self.incoming],
            "outgoing": [e.id for e in self.outgoing],
        }
    
    def clone(self) -> 'BlockNode':
        """
        Clone the BlockNode.

        :return: Cloned BlockNode.
        :rtype: BlockNode
        """
        node = BlockNode(
            id=self.id,
            title=self.title,
        )
        
        for n in self.nodes.values():
            node.add_node(n.clone())
        for e in self.edges.values():
            node.add_edge(e.clone())
        
        return node

    def remove_node(self, id: str, keep_edges: bool = False) -> Optional[CFGNode]:
        """
        Removes a node from the control flow graph and all associated edges.
        If keep_edges is True, the edges connected to the node remain in 
        incoming and outcoming lists of the edge source and target nodes, but 
        they are always removed from graph.
        If keep_edges is False, the edges connected to the node are always 
        removed also from incoming and outcoming lists of the edge source and 
        target nodes.

        :param id: Node identifier.
        :type id: str
        :param keep_edges: Whether to keep the edges connected to the node.
        :type keep_edges: bool
        :return: The removed node, None if not found.
        :rtype: Optional[CFGNode]
        """
        if id not in self.nodes:
            return None
        
        node = self.nodes.pop(id)

        if not keep_edges:
            for e in node.incoming:
                self.remove_edge(e.id)
            for e in node.outgoing:
                self.remove_edge(e.id)
        else:
            for e in node.incoming:
                self.edges.pop(e.id, None)
            for e in node.outgoing:
                self.edges.pop(e.id, None)

        return node
    
    def remove_edge(self, id: str) -> bool:
        """
        Removes an edge from the control flow graph and from the incoming and outcoming 
        lists of the edge source and target nodes.

        :param id: Edge identifier.
        :type id: str
        :return: True if the edge was removed, False otherwise.
        :rtype: bool
        """
        if id not in self.edges:
            return False
        
        edge = self.edges.pop(id)
        edge.source.outgoing.remove(edge)
        edge.target.incoming.remove(edge)
        return True

# TODO future ReferenceNode => for action.definitionCanonical = "PlanDefinition/<id>"

