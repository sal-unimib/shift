import copy
import re
from typing import Any, Dict, Iterator, List, Mapping, Optional, Union, cast

from fhir.resources.expression import Expression
from fhir.resources.plandefinition import PlanDefinition, PlanDefinitionAction
from fhir.resources.requestorchestration import RequestOrchestration, RequestOrchestrationAction
from src.domain.action_definition import ActionDefinition
from src.domain.cfg import ControlFlowGraph, InstanceControlFlowGraph
from src.domain.enums import CFGEventType, TemporalCategory
from src.domain.nodes import ActionNode, BlockNode, TimerEventNode
from src.domain.process_definition import (
    ProcessDefinition, ProcessDefinitionActionVariable, ProcessDefinitionVariable,
    ProcessDefinitionTemporalVariable,
)
from src.domain.temporal_constraint import TemporalConstraint
from src.mappers.bpmn_mapper import BPMNStandardMapper
from src.utils.definition_identifiers import (
    action_definition_id, plan_definition_id, process_definition_id,
    process_action_variable_id, process_temporal_variable_id, process_variable_id,
)

CFGScope = Union[ControlFlowGraph, BlockNode]
WorkflowResource = Union[PlanDefinition, RequestOrchestration]
WorkflowAction = Union[PlanDefinitionAction, RequestOrchestrationAction]


class ProcessDefinitionMapper:
    """Map validated inputs to domain declarations without repository access."""

    @staticmethod
    def actions(plandefinition: WorkflowResource) -> Dict[str, WorkflowAction]:
        """Collect clinical actions from a validated FHIR workflow hierarchy.

        :param plandefinition: Validated source definition.
        :type plandefinition: Union[PlanDefinition, RequestOrchestration]
        :return: Clinical actions keyed by linkId, preserving source order.
        :rtype: Dict[str, Union[PlanDefinitionAction, RequestOrchestrationAction]]
        """
        result: Dict[str, WorkflowAction] = {}
        pending = list(plandefinition.action or [])
        while pending:
            action = pending.pop(0)
            pending[0:0] = list(action.action or [])
            if action.definitionCanonical:
                result[cast(str, action.linkId)] = action
        return result

    @classmethod
    def map(cls, plandefinition: PlanDefinition, cfg: ControlFlowGraph,
            action_definitions: Mapping[str, ActionDefinition]) -> ProcessDefinition:
        """Build the domain contract using validated inputs and a loaded action catalog.

        :param plandefinition: Source definition validated by ControlFlowGraphFactory.
        :type plandefinition: PlanDefinition
        :param cfg: Matching temporal CFG produced by the definition pipeline.
        :type cfg: ControlFlowGraph
        :param action_definitions: Loaded ActivityDefinition contracts keyed by logical ID.
        :type action_definitions: Mapping[str, ActionDefinition]
        :return: Definition metadata, action variables, condition bindings and temporal declarations.
        :rtype: ProcessDefinition
        """
        plan_id = plan_definition_id(cast(str, plandefinition.id))
        version = cast(str, plandefinition.version)
        actions = cls.actions(plandefinition)
        graph = BPMNStandardMapper.prepare_cfg(cfg)
        action_variables: List[ProcessDefinitionActionVariable] = []
        for action_id, action in actions.items():
            catalog = action_definitions[action_definition_id(cast(str, action.definitionCanonical))]
            defaults: Dict[str, Optional[str]] = {}
            for dynamic in action.dynamicValue or []:
                value = cast(str, cast(Expression, dynamic.expression).expression)
                defaults[cast(str, dynamic.path)] = None if cls._condition_names(value) else value
            for attribute in catalog.attributes:
                action_variables.append(ProcessDefinitionActionVariable(
                    id=process_action_variable_id(plan_id, version, action_id, attribute.id),
                    action_definition_attribute=attribute, action_link_id=action_id,
                    default_value=defaults.get(attribute.path)))
        return ProcessDefinition(id=process_definition_id(plan_id, version),
            plan_definition_id=plan_id, name=plandefinition.name, title=plandefinition.title,
            description=plandefinition.description, version=version, artifact_version=cfg.version,
            action_variables=action_variables,
            variables=cls._condition_variables(graph, actions, plan_id, version),
            temporal_constraints=cls._temporal_variables(graph, plan_id, version))

    @classmethod
    def map_specialization(
        cls,
        request: RequestOrchestration,
        cfg: InstanceControlFlowGraph,
        parent: ProcessDefinition,
        action_definitions: Mapping[str, ActionDefinition],
        version: str,
    ) -> ProcessDefinition:
        """
        Build a direct child with fresh bindings and applicable inherited defaults.

        Current temporal declarations and condition bindings are derived from the
        rebuilt graph. Removed actions, attributes, conditions and temporal types
        are not copied. Parent declarations are never modified.

        :param request: Validated patient-specific workflow.
        :type request: RequestOrchestration
        :param cfg: Matching temporal instance CFG.
        :type cfg: InstanceControlFlowGraph
        :param parent: Root process definition referenced by the request.
        :type parent: ProcessDefinition
        :param action_definitions: Loaded contracts for the current clinical actions.
        :type action_definitions: Mapping[str, ActionDefinition]
        :param version: Specialized version supplied by the instance service.
        :type version: str
        :return: Child metadata and declarations with version-specific identifiers.
        :rtype: ProcessDefinition
        """
        actions = cls.actions(request)
        graph = BPMNStandardMapper.prepare_cfg(cfg)
        plan_id = parent.plan_definition_id
        inherited_actions = {variable.key: variable for variable in parent.action_variables}
        action_variables: List[ProcessDefinitionActionVariable] = []
        for action_id, action in actions.items():
            catalog = action_definitions[action_definition_id(cast(str, action.definitionCanonical))]
            supplied = {
                cast(str, dynamic.path): cast(str, cast(Expression, dynamic.expression).expression)
                for dynamic in action.dynamicValue or []
            }
            for attribute in catalog.attributes:
                inherited = inherited_actions.get((action_id, attribute.id))
                default = copy.deepcopy(inherited.default_value) if inherited is not None else None
                if attribute.path in supplied:
                    value = supplied[attribute.path]
                    default = None if cls._condition_names(value) else value
                action_variables.append(ProcessDefinitionActionVariable(
                    id=process_action_variable_id(plan_id, version, action_id, attribute.id),
                    action_definition_attribute=copy.deepcopy(attribute),
                    action_link_id=action_id,
                    default_value=default,
                    is_active=inherited.is_active if inherited is not None else True,
                ))

        variables = cls._condition_variables(graph, actions, plan_id, version)
        for variable in variables:
            candidates = [
                old for old in parent.variables
                if old.prefix == "condvar" and old.name == variable.name
            ]
            inherited = next(
                (old for old in candidates if old.action_link_id == variable.action_link_id),
                candidates[0] if candidates else None,
            )
            if inherited is not None:
                variable.default_value = copy.deepcopy(inherited.default_value)
                variable.is_active = inherited.is_active

        temporal = cls._temporal_variables(graph, plan_id, version)
        inherited_temporal = {variable.key: variable for variable in parent.temporal_constraints}
        for variable in temporal:
            inherited = inherited_temporal.get(variable.key)
            if inherited is not None:
                variable.is_active = inherited.is_active

        return ProcessDefinition(
            id=process_definition_id(plan_id, version),
            plan_definition_id=plan_id,
            name=cfg.name,
            title=cfg.title,
            description=cfg.description,
            version=version,
            artifact_version=version,
            parent_definition_id=parent.id,
            revision=2,
            specialization_key=cfg.subject_id,
            action_variables=action_variables,
            variables=variables,
            temporal_constraints=temporal,
        )

    @staticmethod
    def _scopes(cfg: CFGScope) -> Iterator[CFGScope]:
        """Visit the root and every nested CFG scope in insertion order.

        :param cfg: Root CFG or block.
        :type cfg: Union[ControlFlowGraph, BlockNode]
        :return: Recursive scope iterator.
        :rtype: Iterator[Union[ControlFlowGraph, BlockNode]]
        """
        yield cfg
        for node in cfg.nodes.values():
            if isinstance(node, BlockNode):
                yield from ProcessDefinitionMapper._scopes(node)

    @staticmethod
    def _condition_names(expression: str) -> List[str]:
        """Extract distinct percent-prefixed names, excluding literals and comments.

        :param expression: Source condition or dynamicValue expression.
        :type expression: str
        :return: Referenced names without percent signs, in first-occurrence order.
        :rtype: List[str]
        """
        tokens = re.compile(
            r"%(?P<name>[A-Za-z_][A-Za-z0-9_]*|`(?:\\.|[^`\\])+`|'(?:\\.|[^'\\])+')"
            r"|//[^\n]*|/\*.*?\*/|'(?:\\.|''|[^'\\])*'|\"(?:\\.|[^\"\\])*\""
            r"|“[^”]*”|‘[^’]*’|`(?:\\.|[^`\\])*`", re.DOTALL)
        names = []
        for match in tokens.finditer(expression or ''):
            name = match.group('name')
            if name is None:
                continue
            if name[0] in {"`", "'"}:
                name = re.sub(r"\\(.)", r"\1", name[1:-1])
            if name not in names:
                names.append(name)
        return names

    @staticmethod
    def _frontier(scope: CFGScope, start_id: str) -> List[str]:
        """Find the first clinical actions downstream of an element within its scope.

        :param scope: Owning graph scope.
        :type scope: Union[ControlFlowGraph, BlockNode]
        :param start_id: Entry element identifier.
        :type start_id: str
        :return: First reachable action IDs, without crossing an action or subprocess.
        :rtype: List[str]
        """
        pending, seen, result = [start_id], set(), []
        while pending:
            nid = pending.pop(0)
            if nid in seen:
                continue
            seen.add(nid)
            node = scope.nodes[nid]
            if isinstance(node, ActionNode):
                result.append(nid)
            elif not isinstance(node, BlockNode):
                pending.extend(e.target.id for e in node.outgoing)
        return result

    @classmethod
    def _condition_variables(cls, graph: ControlFlowGraph, actions: Mapping[str, WorkflowAction], plan_id: str, version: str) -> List[ProcessDefinitionVariable]:
        """Declare each variable/flow binding, sharing logical names across conditions.

        :param graph: Prepared graph whose edge IDs match the emitted BPMN.
        :type graph: ControlFlowGraph
        :param actions: Source FHIR actions keyed by linkId.
        :type actions: Mapping[str, WorkflowAction]
        :param plan_id: Source PlanDefinition logical ID.
        :type plan_id: str
        :param version: Caller-supplied process version.
        :type version: str
        :return: NULL-valued declarations with prefix condvar and one record per binding.
        :rtype: List[ProcessDefinitionVariable]
        """
        variables = []
        for scope in cls._scopes(graph):
            for edge in scope.edges.values():
                condition = edge.execution_condition
                if condition is None or BPMNStandardMapper._is_default(condition):
                    continue
                candidates = []
                for action_id in cls._frontier(scope, edge.target.id):
                    source = actions.get(action_id)
                    if source and any(c.expression and c.expression.expression == condition.expression
                                      for c in source.condition or []):
                        candidates.append(action_id)
                action_id = candidates[0] if len(candidates) == 1 else None
                for name in cls._condition_names(condition.expression):
                    variables.append(ProcessDefinitionVariable(
                        id=process_variable_id('condvar', plan_id, version, edge.id, name),
                        name=name, bpmn_element_id=edge.id, action_link_id=action_id,
                        default_value=None, prefix='condvar'))
        return variables

    @classmethod
    def _temporal_variables(cls, graph: ControlFlowGraph, plan_id: str, version: str) -> List[ProcessDefinitionTemporalVariable]:
        """Collect all temporal categories and bind shared schedules to every member action.

        :param graph: Prepared temporal graph, including nested cycle scopes.
        :type graph: ControlFlowGraph
        :param plan_id: Source PlanDefinition logical ID.
        :type plan_id: str
        :param version: Caller-supplied process version.
        :type version: str
        :return: One temporal declaration per action/category with an optional BPMN element.
        :rtype: List[ProcessDefinitionTemporalVariable]
        """
        declarations = {}
        scopes = list(cls._scopes(graph))
        actions = {n.id: n for scope in scopes for n in scope.nodes.values() if isinstance(n, ActionNode)}

        def signature(payload: Dict[str, Any]) -> Dict[str, Any]:
            """Compare temporal defaults independently of action IDs, labels and set ordering.

            :param payload: Serialized temporal constraint.
            :type payload: Dict[str, Any]
            :return: Independent representation used to match shared schedules.
            :rtype: Dict[str, Any]
            """
            value = copy.deepcopy(payload)
            for key in ('action_id', 'label'):
                value.pop(key, None)
            for key in ('day_of_week', 'time_of_day', 'when'):
                if key in value:
                    value[key] = sorted(value[key] or [])
            return value

        def put(constraint: TemporalConstraint, action_id: str, element_id: Optional[str] = None) -> None:
            """Merge a validated declaration with its optional BPMN element binding.

            :param constraint: Validated action or timer constraint.
            :type constraint: TemporalConstraint
            :param action_id: Owning FHIR action linkId.
            :type action_id: str
            :param element_id: Associated BPMN element, when present.
            :type element_id: Optional[str]
            :return: None.
            :rtype: None
            """
            value = copy.deepcopy(constraint.to_json())
            value['action_id'] = action_id
            key = (action_id, constraint.temporal_category)
            if key in declarations:
                previous = declarations[key]
                if element_id:
                    previous.element_id = element_id
                return
            declarations[key] = ProcessDefinitionTemporalVariable(
                id=process_temporal_variable_id(plan_id, version, action_id, constraint.temporal_category),
                action_link_id=action_id, temporal_category=constraint.temporal_category,
                element_id=element_id, label=constraint.label or '', default_value=value)

        for action in actions.values():
            raw = action.fhir_temporal_constraint
            if raw:
                for category in raw.get_categories():
                    element = action.id if category in {TemporalCategory.EXECUTION_DURATION, TemporalCategory.EXECUTION_ITERATION} else None
                    put(raw.to_event_temporal_constraint(action.id, category), action.id, element)
            action_constraints = list(action.temporal_constraints)
            if action.temporal_constraint is not None and not any(
                    c.to_json() == action.temporal_constraint.to_json() for c in action_constraints):
                action_constraints.append(action.temporal_constraint)
            for constraint in action_constraints:
                element = action.id if constraint.temporal_category in {
                    TemporalCategory.EXECUTION_DURATION, TemporalCategory.EXECUTION_ITERATION} else None
                put(constraint, action.id, element)

        schedule_members = {}
        for scope in scopes:
            for timer in scope.nodes.values():
                if not isinstance(timer, TimerEventNode) or timer.event_type != CFGEventType.START:
                    continue
                tc = timer.temporal_constraint
                members = []
                for action_id in cls._frontier(scope, timer.id):
                    raw = actions[action_id].fhir_temporal_constraint
                    if raw:
                        candidate = raw.to_event_temporal_constraint(action_id, tc.temporal_category)
                        if candidate is not None and signature(candidate.to_json()) == signature(tc.to_json()):
                            members.append(action_id)
                if not members:
                    members = [tc.action_id]
                schedule_members[tc.action_id] = members
                for action_id in members:
                    put(tc, action_id, timer.id)
                    # Interval metadata combined with a calendar is carried by the same scheduler.
                    raw = actions[action_id].fhir_temporal_constraint
                    if raw and tc.temporal_category == TemporalCategory.INSTANCE_CYCLE and TemporalCategory.STANDARD_CYCLE in raw.get_categories():
                        put(raw.to_event_temporal_constraint(action_id, TemporalCategory.STANDARD_CYCLE), action_id, timer.id)
        for scope in scopes:
            for timer in scope.nodes.values():
                if not isinstance(timer, TimerEventNode) or timer.event_type == CFGEventType.START:
                    continue
                tc = timer.temporal_constraint
                members = schedule_members.get(tc.action_id, [tc.action_id]) if tc.temporal_category == TemporalCategory.KEEP_ALIVE_BOUND else [tc.action_id]
                for action_id in members:
                    put(tc, action_id, timer.id)
        return list(declarations.values())

