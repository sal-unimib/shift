from typing import Dict, FrozenSet, Iterable, Set, Tuple

from src.domain.cfg import ControlFlowGraph, ControlFlowGraphFactory
from src.domain.enums import CFGGatewayClass, CFGGatewayDirection, TemporalCategory
from src.domain.nodes import ActionNode, GatewayNode


class DefinitionAlignment:
    """Compare classic CFGs without modifying their source graphs."""

    _CYCLIC = frozenset({
        TemporalCategory.STANDARD_CYCLE,
        TemporalCategory.INSTANCE_CYCLE,
        TemporalCategory.KEEP_ALIVE_BOUND,
    })
    _NON_STRUCTURAL = frozenset({
        TemporalCategory.EXECUTION_DURATION,
        TemporalCategory.EXECUTION_ITERATION,
    })

    @staticmethod
    def _actions(graph: ControlFlowGraph) -> Dict[str, ActionNode]:
        """
        Collect clinical actions from a classic CFG.

        :param graph: Source graph before gateway and temporal structuring.
        :type graph: ControlFlowGraph
        :return: Clinical actions keyed by their FHIR linkId.
        :rtype: Dict[str, ActionNode]
        """
        return {node.id: node for node in graph.nodes.values() if isinstance(node, ActionNode)}

    @staticmethod
    def _relations(graph: ControlFlowGraph) -> Set[Tuple[str, str]]:
        """
        Collect clinical relationships independently of order and synthetic nodes.

        :param graph: Source classic CFG.
        :type graph: ControlFlowGraph
        :return: Unique action-to-action source and target pairs.
        :rtype: Set[Tuple[str, str]]
        """
        return {
            (edge.source.id, edge.target.id)
            for edge in graph.edges.values()
            if isinstance(edge.source, ActionNode) and isinstance(edge.target, ActionNode)
        }

    @classmethod
    def _structural_categories(
        cls, categories: Iterable[TemporalCategory]
    ) -> FrozenSet[TemporalCategory]:
        """
        Normalize categories according to the BPMN constructs they require.

        :param categories: Declared action categories, or an empty collection.
        :type categories: Iterable[TemporalCategory]
        :return: Structural categories with one representative for cyclic scopes.
        :rtype: FrozenSet[TemporalCategory]
        """
        declared = set(categories)
        structural = declared - cls._NON_STRUCTURAL - cls._CYCLIC
        if declared & cls._CYCLIC:
            structural.add(TemporalCategory.STANDARD_CYCLE)
        return frozenset(structural)

    @classmethod
    def _shared_groups(cls, graph: ControlFlowGraph) -> Set[FrozenSet[str]]:
        """
        Identify scheduled actions sharing a temporal block in the current factory.

        Gateway construction runs on a copy. Schedule equality uses the factory's
        label-independent signature, including its normalization of list ordering.
        Only group membership is compared across graphs, not literal schedule values.

        :param graph: Source classic CFG.
        :type graph: ControlFlowGraph
        :return: Groups containing at least two actions with a shared scheduler.
        :rtype: Set[FrozenSet[str]]
        """
        scheduled = {
            action.id for action in cls._actions(graph).values()
            if action.fhir_temporal_constraint is not None
            and cls._CYCLIC.intersection(action.fhir_temporal_constraint.get_categories())
        }
        if len(scheduled) < 2:
            return set()

        structured = ControlFlowGraphFactory.cfg_with_gateways(graph)
        groups: Set[FrozenSet[str]] = set()
        processed: Set[str] = set()
        for action in cls._actions(structured).values():
            if action.id not in scheduled or action.id in processed:
                continue
            group = {action.id}
            parent = action.incoming[0].source if len(action.incoming) == 1 else None
            if (isinstance(parent, GatewayNode)
                    and parent.gateway_class == CFGGatewayClass.PARALLEL
                    and parent.gateway_direction == CFGGatewayDirection.DIVERGENT):
                signature = ControlFlowGraphFactory._cycle_signature(action)
                group = {
                    edge.target.id for edge in parent.outgoing
                    if edge.execution_condition is None
                    and edge.target.id in scheduled
                    and len(edge.target.incoming) == 1
                    and ControlFlowGraphFactory._cycle_signature(edge.target) == signature
                }
            processed.update(group)
            if len(group) > 1:
                groups.add(frozenset(group))
        return groups

    @classmethod
    def requires_alignment(
        cls, request_graph: ControlFlowGraph, plan_graph: ControlFlowGraph
    ) -> bool:
        """
        Compare action identities, clinical relations and temporal structures.

        :param request_graph: Classic CFG extracted from the RequestOrchestration.
        :type request_graph: ControlFlowGraph
        :param plan_graph: Classic CFG extracted from the source PlanDefinition.
        :type plan_graph: ControlFlowGraph
        :return: Whether the process definition requires structural alignment.
        :rtype: bool
        """
        request_actions = cls._actions(request_graph)
        plan_actions = cls._actions(plan_graph)
        if ({key: action.activity_definition for key, action in request_actions.items()}
                != {key: action.activity_definition for key, action in plan_actions.items()}):
            return True
        if cls._relations(request_graph) != cls._relations(plan_graph):
            return True
        for action_id, plan_action in plan_actions.items():
            request_action = request_actions[action_id]
            plan_categories = (
                plan_action.fhir_temporal_constraint.get_categories()
                if plan_action.fhir_temporal_constraint is not None else set()
            )
            request_categories = (
                request_action.fhir_temporal_constraint.get_categories()
                if request_action.fhir_temporal_constraint is not None else set()
            )
            if cls._structural_categories(plan_categories) != cls._structural_categories(request_categories):
                return True
        return cls._shared_groups(request_graph) != cls._shared_groups(plan_graph)
