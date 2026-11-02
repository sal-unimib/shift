import copy
from decimal import Decimal
from typing import Any, Dict, Optional, Set, Tuple, Union

import owlready2 as or2
from src.domain import bpmn as bpmn_model
from src.domain.bpmn_ontology import bbo
from src.domain.cfg import ControlFlowGraph
from src.domain.enums import CFGNodeType, CFGEventType, CFGGatewayClass, TemporalCategory
from src.domain.exceptions import BPMNGenerationException
from src.domain.nodes import BlockNode, CFGNode, CFGEdge, EventNode, TimerEventNode
from src.utils.serializers import from_camel_to_snake
from src.mappers.bpmn_diagram_generator import BPMNDiagramGenerator
from src.mappers.temporal_schedule_mapper import TemporalScheduleMapper
from src.utils.settings import settings


class BPMNStandardMapper:
    """Map each CFG scope independently, retaining the original graph."""

    @staticmethod
    def get_namespaces() -> Dict[str, str]:
        """Return the namespaces used by the standard BPMN serializer.

        :return: Namespace prefixes and URIs.
        :rtype: Dict[str, str]
        """
        return {
            "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
            "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
            "di": "http://www.omg.org/spec/DD/20100524/DI",
            "dc": "http://www.omg.org/spec/DD/20100524/DC",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        }

    @staticmethod
    def _is_default(condition) -> bool:
        """Recognize an explicit default marker without interpreting clinical text.

        :param condition: Optional FHIR execution condition.
        :type condition: Optional[FHIRExecutionCondition]
        :return: Whether the expression is exactly otherwise or default.
        :rtype: bool
        """
        return condition is not None and str(condition.expression).strip().casefold() in {"otherwise", "default"}

    @staticmethod
    def _duration(value, unit) -> str:
        """Encode a non-negative UCUM duration without calendar approximations.

        :param value: Duration magnitude.
        :type value: float
        :param unit: Supported UCUM unit.
        :type unit: UCUMUnitOfTime
        :return: ISO 8601 duration.
        :rtype: str
        :raises ValueError: If the magnitude or unit is invalid.
        """
        number = Decimal(str(value))
        code = getattr(unit, "value", unit)
        suffix = {"s": "S", "min": "M", "h": "H", "d": "D", "wk": "W", "mo": "M", "a": "Y"}
        if not number.is_finite() or number < 0 or code not in suffix:
            raise ValueError("Invalid timer duration or UCUM unit")
        if code in {"mo", "a"} and number != number.to_integral_value():
            raise ValueError("Fractional calendar durations are not supported")
        # Express fractional weeks/days using seconds for interoperable ISO durations.
        if code in {"wk", "d"} and number != number.to_integral_value():
            number *= Decimal(604800 if code == "wk" else 86400)
            code = "s"
        return ("PT" if code in {"s", "min", "h"} else "P") + format(number.normalize(), "f") + suffix[code]

    @classmethod
    def _cycle_duration(cls, period: Decimal, frequency: Decimal, unit: str) -> str:
        """Distribute interval occurrences uniformly without rounding their spacing.

        :param period: Positive period magnitude.
        :type period: Decimal
        :param frequency: Positive integral occurrence count per period.
        :type frequency: Decimal
        :param unit: UCUM period unit.
        :type unit: str
        :return: ISO 8601 interval between successive activations.
        :rtype: str
        :raises ValueError: If the spacing requires fractional seconds or calendar units.
        """
        if frequency == 1:
            return cls._duration(period, unit)
        code = getattr(unit, "value", unit)
        seconds_per_unit = {"s": 1, "min": 60, "h": 3600, "d": 86400, "wk": 604800}
        if code in seconds_per_unit:
            seconds = period * seconds_per_unit[code]
            if seconds % frequency:
                raise ValueError("Uniform recurrence spacing with fractional seconds is not supported")
            interval = seconds / frequency
            # Prefer compact hour/minute durations, keeping weekly fractions exact.
            for divisor, interval_unit in ((3600, "h"), (60, "min"), (1, "s")):
                if interval % divisor == 0:
                    return cls._duration(interval / divisor, interval_unit)
        if code in {"mo", "a"}:
            if period % frequency:
                raise ValueError("Uniform recurrence spacing with fractional calendar units is not supported")
            return cls._duration(period / frequency, code)
        raise ValueError("Invalid recurrence period unit")

    @classmethod
    def _timer_binding(cls, node: TimerEventNode) -> Optional[Tuple[str, str]]:
        """Resolve deterministic timers and calendars using configured UTC conventions.

        :param node: Timer node with concrete temporal metadata.
        :type node: TimerEventNode
        :return: BPMN timer field and literal, or None for an unspecified cycle/lifetime.
        :rtype: Optional[Tuple[str, str]]
        :raises ValueError: If the specified schedule cannot be resolved automatically.
        """
        p = node.temporal_constraint.to_json()
        category = node.temporal_constraint.temporal_category
        if category == TemporalCategory.STANDARD_CYCLE:
            if all(p.get(k) is None for k in ("period", "period_unit", "frequency", "period_max", "frequency_max", "count", "count_max")):
                return None
            if any(p.get(k) is not None for k in ("period_max", "frequency_max", "count_max")):
                raise ValueError("Recurrence ranges are not supported")
            period, frequency = Decimal(str(p.get("period"))), Decimal(str(p["frequency"] if p.get("frequency") is not None else 1))
            if not period.is_finite() or not frequency.is_finite() or period <= 0 or frequency <= 0:
                raise ValueError("Recurrence period and frequency must be positive")
            if frequency != frequency.to_integral_value():
                raise ValueError("Recurrence frequency must be a positive integer")
            interval = cls._cycle_duration(period, frequency, p['period_unit'])
            count = p.get("count")
            if count is not None and (count < 1 or int(count) != count):
                raise ValueError("Recurrence count must be a positive integer")
            return "time_cycle", f"R{int(count) if count is not None else ''}/{interval}"
        if category == TemporalCategory.INSTANCE_CYCLE:
            return "time_cycle", TemporalScheduleMapper.to_cron(node.temporal_constraint, settings.temporal)
        if category == TemporalCategory.EXACT:
            return "time_date", p["event"]
        if category == TemporalCategory.OFFSET:
            return "time_duration", cls._duration(p["offset_duration"], p["offset_duration_unit"])
        if category == TemporalCategory.EXECUTION_BOUND:
            if p.get("duration_max") is not None:
                return "time_duration", cls._duration(p["duration_max"], p["duration_unit"])
            raise ValueError("Execution bounds require a maximum duration")
        if category == TemporalCategory.KEEP_ALIVE_BOUND:
            if p.get("bounds_period_start") is not None:
                raise ValueError("Lifetime start bounds require an explicit activation policy")
            if p.get("bounds_period_end") is not None:
                return "time_date", p["bounds_period_end"]
            if p.get("bounds_duration") is not None:
                return "time_duration", cls._duration(p["bounds_duration"], p["bounds_duration_unit"])
            return None
        raise ValueError(f"Unsupported timer category: {category}")

    @classmethod
    def _map_cfg_node(cls, node: CFGNode) -> Tuple[Any, or2.ThingClass]:
        """Map a non-container node using scope-local adjacency.

        :param node: Normalized node to map.
        :type node: CFGNode
        :return: BPMN element and ontology class used by the container mapping.
        :rtype: Tuple[Any, or2.ThingClass]
        :raises ValueError: If a node or temporal constraint is unsupported.
        """
        attrs = dict(id=node.id, incoming=[e.id for e in node.incoming], outgoing=[e.id for e in node.outgoing])
        if node.node_type == CFGNodeType.ACTION:
            return bpmn_model.Task(name=node.title, **attrs), bbo.Task
        if node.node_type == CFGNodeType.GATEWAY:
            direction = (bpmn_model.TGatewayDirection.MIXED if len(node.incoming) > 1 and len(node.outgoing) > 1
                         else bpmn_model.TGatewayDirection.DIVERGING if len(node.outgoing) > 1
                         else bpmn_model.TGatewayDirection.CONVERGING if len(node.incoming) > 1
                         else bpmn_model.TGatewayDirection.UNSPECIFIED)
            if node.gateway_class == CFGGatewayClass.EXCLUSIVE:
                return bpmn_model.ExclusiveGateway(gateway_direction=direction, **attrs), bbo.ExclusiveGateway
            if node.gateway_class == CFGGatewayClass.PARALLEL:
                return bpmn_model.ParallelGateway(gateway_direction=direction, **attrs), bbo.ParallelGateway
        if node.node_type == CFGNodeType.EVENT:
            if node.event_type == CFGEventType.START:
                if node.incoming:
                    raise ValueError(f"Start event {node.id} cannot have incoming flows")
                return bpmn_model.StartEvent(**attrs), bbo.StartEvent
            if node.event_type == CFGEventType.END:
                if node.outgoing:
                    raise ValueError(f"End event {node.id} cannot have outgoing flows")
                return bpmn_model.EndEvent(terminate_event_definition=[bpmn_model.TerminateEventDefinition()] if getattr(node, "_terminate", False) else [], **attrs), bbo.EndEvent
        if node.node_type == CFGNodeType.TIMER_EVENT:
            try:
                binding = cls._timer_binding(node)
            except ValueError as exc:
                raise ValueError(f"Timer {node.id} ({node.temporal_constraint.action_id}): {exc}") from exc
            definition = bpmn_model.TimerEventDefinition(id=f"{node.id}_definition")
            if binding is not None:
                if (not isinstance(binding, tuple) or len(binding) != 2 or
                        binding[0] not in {"time_cycle", "time_date", "time_duration"} or
                        not isinstance(binding[1], str) or not binding[1].strip()):
                    raise ValueError(f"Invalid resolved timer definition for {node.id}")
                if binding[0] == "time_cycle" and node.event_type != CFGEventType.START:
                    raise ValueError(f"Repeating timer not supported on this catch/boundary event: {node.id}")
                setattr(definition, binding[0], bpmn_model.TFormalExpression(content=[binding[1]]))
            attrs.update(name=node.temporal_constraint.label, timer_event_definition=[definition])
            if node.event_type == CFGEventType.START:
                if node.incoming:
                    raise ValueError(f"Start timer {node.id} cannot have incoming flows")
                return bpmn_model.StartEvent(is_interrupting=not getattr(node, "_non_interrupting", False), **attrs), bbo.StartEvent
            if node.event_type == CFGEventType.INTERMEDIATE:
                return bpmn_model.IntermediateCatchEvent(**attrs), bbo.IntermediateCatchEvent
            if node.event_type == CFGEventType.BOUNDARY:
                if len(node.incoming) != 1 or node.incoming[0].source.node_type not in {CFGNodeType.ACTION, CFGNodeType.BLOCK}:
                    raise ValueError(f"Boundary {node.id} must attach to one activity in its scope")
                attrs.pop("incoming")
                return bpmn_model.BoundaryEvent(attached_to_ref=node.incoming[0].source.id,
                                               cancel_activity=True, **attrs), bbo.BoundaryEvent
        raise ValueError(f"Unsupported CFG node: {node.id} ({node.node_type})")

    @classmethod
    def _normalize_scope(cls, scope) -> None:
        """Bypass fake connectors on a private graph and restore scope adjacency.

        :param scope: Copied CFG or block.
        :type scope: Union[ControlFlowGraph, BlockNode]
        :return: None.
        :rtype: None
        :raises ValueError: If connector removal would discard or combine conditions.
        """
        while any(n.node_type == CFGNodeType.FAKE for n in scope.nodes.values()):
            node = next(n for n in scope.nodes.values() if n.node_type == CFGNodeType.FAKE)
            incoming = [e for e in scope.edges.values() if e.target is node]
            outgoing = [e for e in scope.edges.values() if e.source is node]
            if not incoming or not outgoing or any(e.source is node for e in incoming):
                raise ValueError(f"Dangling or cyclic fake connector: {node.id}")
            for left in incoming:
                for right in outgoing:
                    lc, rc = left.execution_condition, right.execution_condition
                    if lc is not None and rc is not None and lc.to_json() != rc.to_json():
                        raise ValueError(f"Connector {node.id} requires explicit condition composition")
                    edge = CFGEdge(left.source, right.target, left.relationship, lc if lc is not None else rc)
                    if edge.id in scope.edges:
                        raise ValueError(f"Connector bypass would overwrite edge {edge.id}")
                    scope.edges[edge.id] = edge
            scope.edges = {k: e for k, e in scope.edges.items() if e.source is not node and e.target is not node}
            del scope.nodes[node.id]
        for node in scope.nodes.values():
            node.incoming = [e for e in scope.edges.values() if e.target is node]
            node.outgoing = [e for e in scope.edges.values() if e.source is node]
            if isinstance(node, BlockNode):
                # Preserve the block's external adjacency while normalizing its body.
                cls._normalize_scope(node)
        for edge in scope.edges.values():
            if scope.nodes.get(edge.source.id) is not edge.source or scope.nodes.get(edge.target.id) is not edge.target:
                raise ValueError(f"Edge {edge.id} crosses a scope or references a foreign node")

    @classmethod
    def _lower_cycle_scopes(cls, scope, reserved) -> None:
        """Represent timer-start/Keep Alive lanes as non-interrupting event subprocesses.

        :param scope: Private presentation graph scope.
        :type scope: Union[ControlFlowGraph, BlockNode]
        :param reserved: Global identifiers reserved by the copied graph.
        :type reserved: set
        :return: None.
        :rtype: None
        :raises ValueError: If the scheduler and lifetime lanes are not independent.
        """
        if getattr(scope, "_event_subprocess", False):
            return
        for node in list(scope.nodes.values()):
            if isinstance(node, BlockNode):
                cls._lower_cycle_scopes(node, reserved)
        starts = [n for n in scope.nodes.values() if isinstance(n, TimerEventNode)
                  and n.event_type == CFGEventType.START]
        keepers = [n for n in scope.nodes.values() if isinstance(n, TimerEventNode)
                   and n.temporal_constraint.temporal_category == TemporalCategory.KEEP_ALIVE_BOUND]
        if not starts or not keepers:
            if starts and isinstance(scope, BlockNode):
                raise ValueError(f"Timer-started block {scope.id} needs a Keep Alive scope")
            return
        if len(starts) != 1 or len(keepers) != 1:
            raise ValueError("Expected one scheduler and one Keep Alive lane per scope")
        start, keeper = starts[0], keepers[0]
        if start.temporal_constraint.temporal_category == TemporalCategory.INSTANCE_CYCLE and TemporalScheduleMapper.is_immediate(start.temporal_constraint):
            lifetime_nodes = {keeper.id}
            lifetime_nodes.update(e.source.id for e in keeper.incoming)
            lifetime_nodes.update(e.target.id for e in keeper.outgoing)
            for nid in lifetime_nodes:
                scope.nodes.pop(nid)
            scope.edges = {eid: edge for eid, edge in scope.edges.items()
                           if edge.source.id not in lifetime_nodes and edge.target.id not in lifetime_nodes}
            immediate_start = EventNode(start.id, CFGEventType.START)
            immediate_start.incoming, immediate_start.outgoing = start.incoming, start.outgoing
            for edge in immediate_start.outgoing:
                edge.source = immediate_start
            scope.nodes[start.id] = immediate_start
            if getattr(scope, 'start_node', None) is start:
                scope.start_node = immediate_start
            return
        body, pending = set(), [start.id]
        while pending:
            nid = pending.pop()
            if nid in body:
                continue
            body.add(nid)
            pending.extend(e.target.id for e in scope.edges.values() if e.source.id == nid)
        if keeper.id in body or any((e.source.id in body) != (e.target.id in body) for e in scope.edges.values()):
            raise ValueError("Scheduler and Keep Alive lanes must be independent")
        wrapper_id = f"{start.id}_cycle_scope"
        while wrapper_id in reserved:
            wrapper_id += "_"
        reserved.add(wrapper_id)
        wrapper = BlockNode(wrapper_id, "Scheduled execution")
        wrapper._event_subprocess = True
        wrapper.nodes = {k: n for k, n in scope.nodes.items() if k in body}
        wrapper.edges = {k: e for k, e in scope.edges.items() if e.source.id in body}
        scope.nodes = {k: n for k, n in scope.nodes.items() if k not in body}
        scope.edges = {k: e for k, e in scope.edges.items() if e.source.id not in body}
        scope.nodes[wrapper.id] = wrapper
        start._non_interrupting = True
        for edge in keeper.outgoing:
            if edge.target.node_type != CFGNodeType.EVENT or edge.target.event_type != CFGEventType.END:
                raise ValueError("Keep Alive must end in a scope-local end event")
            edge.target._terminate = True

    @classmethod
    def _map_scope(
        cls,
        scope: Union[ControlFlowGraph, BlockNode],
        container: Union[bpmn_model.Process, bpmn_model.SubProcess],
        mapped_ids: Set[str],
        synthetic_edges: Set[str],
    ) -> None:
        """Recursively emit nodes, default branches and valid sequence flows.

        :param scope: Normalized copied graph scope.
        :type scope: Union[ControlFlowGraph, BlockNode]
        :param container: Destination BPMN process or subprocess.
        :type container: Union[bpmn_model.Process, bpmn_model.SubProcess]
        :param mapped_ids: Global set used to reject duplicate BPMN IDs.
        :type mapped_ids: Set[str]
        :param synthetic_edges: Attachment edges excluded from model and diagram.
        :type synthetic_edges: Set[str]
        :return: None.
        :rtype: None
        :raises ValueError: If graph IDs, branches or boundary attachments are invalid.
        """
        mapped = {}
        boundary_edges = {e.id for n in scope.nodes.values() if isinstance(n, TimerEventNode)
                          and n.event_type == CFGEventType.BOUNDARY for e in n.incoming}
        synthetic_edges.update(boundary_edges)
        for node in scope.nodes.values():
            if node.id in mapped_ids:
                raise ValueError(f"Duplicate BPMN ID: {node.id}")
            mapped_ids.add(node.id)
            if isinstance(node, BlockNode):
                element = bpmn_model.SubProcess(id=node.id, name=node.title,
                    triggered_by_event=getattr(node, "_event_subprocess", False),
                    incoming=[e.id for e in node.incoming], outgoing=[e.id for e in node.outgoing])
                cls._map_scope(node, element, mapped_ids, synthetic_edges)
                container.sub_process.append(element)
            else:
                element, ontology_type = cls._map_cfg_node(node)
                getattr(container, from_camel_to_snake(ontology_type.name)).append(element)
            if isinstance(node, TimerEventNode) and getattr(element, "timer_event_definition", None):
                timer_id = element.timer_event_definition[0].id
                if timer_id in mapped_ids:
                    raise ValueError(f"Duplicate BPMN ID: {timer_id}")
                mapped_ids.add(timer_id)
            element.outgoing = [eid for eid in element.outgoing if eid not in boundary_edges]
            mapped[node.id] = element
        for edge in scope.edges.values():
            if edge.id in boundary_edges:
                if edge.execution_condition:
                    raise ValueError(f"Attachment {edge.id} cannot carry a condition")
                continue
            if edge.id in mapped_ids:
                raise ValueError(f"Duplicate BPMN ID: {edge.id}")
            mapped_ids.add(edge.id)
            condition = edge.execution_condition
            default = cls._is_default(condition)
            if default:
                source = mapped[edge.source.id]
                if not isinstance(source, bpmn_model.ExclusiveGateway) or len(source.outgoing) < 2:
                    raise ValueError(f"Default branch {edge.id} requires an exclusive split")
                if source.default is not None:
                    raise ValueError(f"Multiple default branches on {source.id}")
                source.default = edge.id
            elif condition is not None and isinstance(mapped[edge.source.id], bpmn_model.ParallelGateway):
                raise ValueError(f"Parallel branch {edge.id} cannot carry a condition")
            container.sequence_flow.append(bpmn_model.SequenceFlow(id=edge.id,
                source_ref=edge.source.id, target_ref=edge.target.id,
                name=condition.description if condition else None,
                condition_expression=condition.to_formal_expression() if condition is not None and not default else None))

    @classmethod
    def _diagram(cls, graph, process, synthetic_edges):
        """Render emitted elements and place boundary shapes on their activities.

        :param graph: Private presentation graph, disposable after rendering.
        :type graph: ControlFlowGraph
        :param process: Mapped BPMN process.
        :type process: bpmn_model.Process
        :param synthetic_edges: Non-flow attachment edge identifiers.
        :type synthetic_edges: Set[str]
        :return: BPMN diagram whose references match the semantic model.
        :rtype: bpmn_model.Bpmndiagram
        """
        pending = [process]
        boundaries = {}
        receive_ids = set()
        while pending:
            container = pending.pop()
            pending.extend(container.sub_process)
            boundaries.update({n.id: str(n.attached_to_ref) for n in container.boundary_event})
            receive_ids.update(n.id for n in container.receive_task)
        scopes = [graph]
        while scopes:
            scope = scopes.pop()
            for node in scope.nodes.values():
                if isinstance(node, BlockNode):
                    scopes.append(node)
                elif node.id in receive_ids:
                    node.node_type = CFGNodeType.ACTION
                    node.title = "Keep Alive"
        diagram = BPMNDiagramGenerator.generate(graph.name, graph)
        plane = diagram.bpmnplane
        plane.bpmnedge = [e for e in plane.bpmnedge if str(e.bpmn_element) not in synthetic_edges]
        shapes = {str(s.bpmn_element): s for s in plane.bpmnshape}
        for nid, owner in boundaries.items():
            boundary, activity = shapes[nid].bounds, shapes[owner].bounds
            boundary.x = activity.x + activity.width - boundary.width
            boundary.y = activity.y + activity.height - boundary.height / 2
            # Existing routes retain their bends, with their origin moved to the attachment.
        containers = [process]
        outgoing = {}
        while containers:
            container = containers.pop()
            containers.extend(container.sub_process)
            outgoing.update({e.id: str(e.source_ref) for e in container.sequence_flow})
        for edge in plane.bpmnedge:
            source = outgoing.get(str(edge.bpmn_element))
            if source in boundaries and edge.waypoint:
                bounds = shapes[source].bounds
                edge.waypoint[0].x = bounds.x + bounds.width
                edge.waypoint[0].y = bounds.y + bounds.height / 2
        return diagram

    @classmethod
    def prepare_cfg(cls, cfg: ControlFlowGraph) -> ControlFlowGraph:
        """Create the private presentation graph shared by BPMN mapping and registration.

        :param cfg: Source CFG, retained unchanged.
        :type cfg: ControlFlowGraph
        :return: Independent graph with fake connectors bypassed and cycle scopes lowered.
        :rtype: ControlFlowGraph
        :raises ValueError: If normalization would lose graph semantics.
        """
        graph = copy.deepcopy(cfg)
        cls._normalize_scope(graph)
        reserved = {graph.name, f"Definition_{graph.id}"}
        scopes = [graph]
        while scopes:
            scope = scopes.pop()
            reserved.update(scope.nodes)
            reserved.update(scope.edges)
            scopes.extend(n for n in scope.nodes.values() if isinstance(n, BlockNode))
        cls._lower_cycle_scopes(graph, reserved)
        return graph

    @classmethod
    def map(cls, cfg: ControlFlowGraph) -> bpmn_model.Definitions:
        """Map a CFG recursively, resolving timers from FHIR metadata and settings.

        :param cfg: Source CFG, retained unchanged even if mapping fails.
        :type cfg: ControlFlowGraph
        :return: Standard BPMN definition with a diagram referencing emitted elements.
        :rtype: bpmn_model.Definitions
        :raises BPMNGenerationException: If a construct or temporal constraint is unsupported or invalid.
        """
        try:
            graph = cls.prepare_cfg(cfg)
            process = bpmn_model.Process(id=graph.name, name=graph.title)
            definition = bpmn_model.Definitions(id=f"Definition_{graph.id}",
                target_namespace="http://bpmn.io/schema/bpmn", exporter="SHIFT", exporter_version="1.0.0-beta")
            synthetic_edges = set()
            cls._map_scope(graph, process, {process.id, definition.id}, synthetic_edges)
            definition.process.append(process)
            diagram = cls._diagram(graph, process, synthetic_edges)
            definition.bpmndiagram.append(diagram)
            return definition
        except Exception as exc:
            raise BPMNGenerationException(f"Something went wrong while mapping CFG into BPMN model: {exc}") from exc
