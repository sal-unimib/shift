import copy
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any, Dict, List, Mapping, Tuple

from fhir.resources.requestorchestration import RequestOrchestration

from src.domain.action_definition import ActionDefinition
from src.domain.cfg import ControlFlowGraph
from src.domain.enums import CFGEventType, TemporalCategory
from src.domain.nodes import ActionNode, TimerEventNode
from src.domain.process_instance import (
    ProcessInstanceVariable, ProcessInstanceActionVariable, ProcessInstanceTemporalConstraint,
)
from src.utils.definition_identifiers import fhir_resource_id
from src.domain.process_definition import ProcessDefinition
from src.mappers.bpmn_mapper import BPMNStandardMapper
from src.mappers.process_definition_mapper import ProcessDefinitionMapper


class InstanceEnrichmentMapper:
    """Prepare declaration-only inputs for engine-specific enrichment."""

    @staticmethod
    def build(
        definition: ProcessDefinition,
        request_graph: ControlFlowGraph,
        template_graph: ControlFlowGraph,
        action_definitions: Mapping[str, ActionDefinition],
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
        """
        Build runtime variable declarations, flow expressions and worker names.

        :param definition: Selected root or specialized process definition.
        :type definition: ProcessDefinition
        :param request_graph: Current classic RequestOrchestration graph.
        :type request_graph: ControlFlowGraph
        :param template_graph: Temporal CFG associated with the selected BPMN.
        :type template_graph: ControlFlowGraph
        :param action_definitions: Complete catalog contracts keyed by logical ID.
        :type action_definitions: Mapping[str, ActionDefinition]
        :return: Declaration metadata and action ID to ActivityDefinition name mapping.
        :rtype: Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]
        """
        variables: Dict[str, Dict[str, Any]] = {
            "__process_definition__": {"id": definition.id, "conditions": {}},
            "subject": {"kind": "subject", "type": "string"},
        }
        workers: Dict[str, str] = {}
        for action in request_graph.nodes.values():
            if not isinstance(action, ActionNode):
                continue
            catalog = action_definitions[action.activity_definition]
            if action.id in variables:
                raise ValueError(f"Action ID conflicts with a runtime declaration: {action.id}")
            workers[action.id] = catalog.name
            variables[action.id] = {
                "kind": "action",
                "properties": {
                    attribute.id: {
                        "type": attribute.fhir_type or "string",
                        "fhir_path": attribute.path,
                    }
                    for attribute in catalog.attributes
                },
            }

        prepared = BPMNStandardMapper.prepare_cfg(template_graph)
        declarations = ProcessDefinitionMapper._temporal_variables(
            prepared, definition.plan_definition_id, definition.version
        )
        slots: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for declaration in declarations:
            category = declaration.temporal_category
            suffix = "cycle" if category in {
                TemporalCategory.STANDARD_CYCLE, TemporalCategory.INSTANCE_CYCLE
            } else category.value
            is_timer = category not in {
                TemporalCategory.EXECUTION_DURATION, TemporalCategory.EXECUTION_ITERATION
            }
            identity = declaration.element_id if is_timer and declaration.element_id else declaration.action_link_id
            slot = slots.setdefault((identity, suffix), {
                "kind": "temporal", "type": "string", "action_ids": set(),
                "element_ids": [], "timer_type": None,
            })
            slot["action_ids"].add(declaration.action_link_id)
            if is_timer and declaration.element_id:
                slot["element_ids"] = [declaration.element_id]
                slot["timer_type"] = {
                    "cycle": "time_cycle", "exact": "time_date",
                    "offset": "time_duration", "execution_bound": "time_duration",
                    "keep_alive_bound": "time_duration",
                }[suffix]
                if suffix == "keep_alive_bound":
                    request_action = request_graph.nodes.get(declaration.action_link_id)
                    raw = request_action.fhir_temporal_constraint if isinstance(request_action, ActionNode) else None
                    if raw is not None and raw.bounds_period_end is not None:
                        slot["timer_type"] = "time_date"
                    elif raw is not None and raw.bounds_duration is not None:
                        slot["timer_type"] = "time_duration"
                    elif declaration.default_value and declaration.default_value.get("bounds_period_end") is not None:
                        slot["timer_type"] = "time_date"
            if suffix == "execution_iteration":
                slot["type"] = "integer"
            slot.setdefault("declaration_ids", []).append(declaration.id)

        # Non-structural constraints may be newly supplied without rebuilding.
        for action in request_graph.nodes.values():
            if not isinstance(action, ActionNode) or action.fhir_temporal_constraint is None:
                continue
            for category in action.fhir_temporal_constraint.get_categories():
                if category not in {TemporalCategory.EXECUTION_DURATION, TemporalCategory.EXECUTION_ITERATION}:
                    continue
                slots.setdefault((action.id, category.value), {
                    "kind": "temporal",
                    "type": "integer" if category == TemporalCategory.EXECUTION_ITERATION else "string",
                    "action_ids": {action.id}, "element_ids": [], "timer_type": None,
                    "declaration_ids": [],
                })

        for (_, suffix), slot in slots.items():
            slot["action_ids"] = sorted(slot["action_ids"])
            name = f"TC_{'+'.join(slot['action_ids'])}_{suffix}"
            if name in variables:
                raise ValueError(f"Conflicting runtime variable name: {name}")
            variables[name] = slot

        for scope in ProcessDefinitionMapper._scopes(prepared):
            for edge in scope.edges.values():
                if edge.execution_condition is None or BPMNStandardMapper._is_default(edge.execution_condition):
                    continue
                expressions = set()
                for action_id in ProcessDefinitionMapper._frontier(scope, edge.target.id):
                    action = request_graph.nodes.get(action_id)
                    if isinstance(action, ActionNode):
                        expressions.update(
                            incoming.execution_condition.expression
                            for incoming in action.incoming
                            if incoming.execution_condition is not None
                            and not BPMNStandardMapper._is_default(incoming.execution_condition)
                        )
                if len(expressions) > 1:
                    raise ValueError(f"Flow {edge.id} cannot represent different action conditions")
                expression = next(iter(expressions), edge.execution_condition.expression)
                variables["__process_definition__"]["conditions"][edge.id] = expression
                for name in ProcessDefinitionMapper._condition_names(expression):
                    if name in variables and variables[name].get("kind") != "condition":
                        raise ValueError(f"Conflicting runtime variable name: {name}")
                    variables.setdefault(name, {"kind": "condition", "type": "string"})
        return copy.deepcopy(variables), workers

    @staticmethod
    def build_values(
        definition: ProcessDefinition,
        request: RequestOrchestration,
        request_graph: ControlFlowGraph,
        declarations: Mapping[str, Dict[str, Any]],
        instance_id: str,
    ) -> Tuple[
        Dict[str, Any], List[ProcessInstanceVariable],
        List[ProcessInstanceActionVariable], List[ProcessInstanceTemporalConstraint],
    ]:
        """
        Resolve runtime values and their persisted declaration bindings.

        Action values retain their textual FHIR representation, including JSON
        strings. Expressions referring to unresolved variables remain None; this
        mapper does not evaluate FHIRPath or fetch remote request resources.

        :param definition: Selected process definition with persisted declarations.
        :type definition: ProcessDefinition
        :param request: Validated patient-specific workflow.
        :type request: RequestOrchestration
        :param request_graph: Classic graph carrying the requested temporal values.
        :type request_graph: ControlFlowGraph
        :param declarations: Runtime declarations produced by build.
        :type declarations: Mapping[str, Dict[str, Any]]
        :param instance_id: SHIFT instance ID used for dependent value IDs.
        :type instance_id: str
        :return: Engine payload and generic, action and temporal domain values.
        :rtype: Tuple[Dict[str, Any], List[ProcessInstanceVariable], List[ProcessInstanceActionVariable], List[ProcessInstanceTemporalConstraint]]
        :raises ValueError: If shared temporal values or generic defaults conflict.
        """
        payload: Dict[str, Any] = {
            "subject": fhir_resource_id(request.subject.reference, "Patient")
        }
        generic_values: List[ProcessInstanceVariable] = []
        action_values: List[ProcessInstanceActionVariable] = []
        temporal_values: List[ProcessInstanceTemporalConstraint] = []
        actions = ProcessDefinitionMapper.actions(request)
        action_defaults = {
            variable.key: variable for variable in definition.action_variables
            if variable.is_active
        }
        temporal_by_id = {
            variable.id: variable for variable in definition.temporal_constraints
            if variable.is_active
        }
        for name, declaration in declarations.items():
            kind = declaration.get("kind")
            if kind == "action":
                action = actions[name]
                supplied = {
                    dynamic.path: dynamic.expression.expression
                    for dynamic in action.dynamicValue or []
                    if dynamic.expression is not None
                }
                values: Dict[str, Any] = {"resource": action.resource.reference}
                for attribute_id, metadata in declaration["properties"].items():
                    binding = action_defaults.get((name, attribute_id))
                    path = metadata["fhir_path"]
                    matches = [
                        supplied_value for supplied_path, supplied_value in supplied.items()
                        if re.sub(r"\[(?:0)?\]", "", supplied_path) == re.sub(r"\[(?:0)?\]", "", path)
                    ]
                    if matches and any(value != matches[0] for value in matches[1:]):
                        raise ValueError(f"Conflicting values for action {name}, path {path}")
                    value = supplied.get(
                        path, matches[0] if matches else (
                            binding.default_value if binding is not None else None
                        ),
                    )
                    if value is not None and ProcessDefinitionMapper._condition_names(value):
                        value = None
                    values[attribute_id] = value
                    if binding is not None:
                        action_values.append(ProcessInstanceActionVariable(
                            id=f"piav_{instance_id}_{binding.id}",
                            action_variable_id=binding.id, value=value,
                        ))
                payload[name] = values
            elif kind == "condition":
                bindings = [
                    variable for variable in definition.variables
                    if variable.is_active and variable.name == name
                ]
                defaults = [
                    variable.default_value for variable in bindings
                    if variable.default_value is not None
                ]
                if defaults and any(value != defaults[0] for value in defaults[1:]):
                    raise ValueError(f"Conflicting defaults for condition variable {name}")
                value = copy.deepcopy(defaults[0]) if defaults else None
                payload[name] = value
                for binding in bindings:
                    generic_values.append(ProcessInstanceVariable(
                        id=f"piv_{instance_id}_{binding.id}",
                        process_variable_id=binding.id,
                        value=value if value is None or isinstance(value, str) else json.dumps(value),
                    ))
            elif kind == "temporal":
                # Category names contain underscores; action IDs are supplied
                # separately and do not need to be parsed from the runtime name.
                prefix = f"TC_{'+'.join(declaration['action_ids'])}_"
                suffix = name[len(prefix):]
                resolved: List[Any] = []
                labels: Dict[str, str] = {}
                for action_id in declaration["action_ids"]:
                    action_node = request_graph.nodes.get(action_id)
                    raw = action_node.fhir_temporal_constraint if isinstance(action_node, ActionNode) else None
                    category = TemporalCategory.STANDARD_CYCLE if suffix == "cycle" else TemporalCategory(suffix)
                    if raw is not None and suffix == "cycle":
                        category = next(
                            (category for category in raw.get_categories()
                             if category in {TemporalCategory.STANDARD_CYCLE, TemporalCategory.INSTANCE_CYCLE}),
                            TemporalCategory.STANDARD_CYCLE,
                        )
                    constraint = raw.to_event_temporal_constraint(action_id, category) if raw is not None else None
                    value = None
                    if constraint is not None:
                        labels[action_id] = constraint.label or ""
                        if category == TemporalCategory.EXECUTION_DURATION:
                            value = BPMNStandardMapper._duration(constraint.duration, constraint.duration_unit)
                        elif category == TemporalCategory.EXECUTION_ITERATION:
                            if constraint.count_max is not None and constraint.count_max != constraint.count:
                                raise ValueError(f"Iteration ranges cannot be resolved for action {action_id}")
                            value = constraint.count
                        else:
                            binding = BPMNStandardMapper._timer_binding(TimerEventNode(
                                f"runtime_{action_id}_{suffix}", CFGEventType.START, constraint
                            ))
                            value = binding[1] if binding is not None else None
                    resolved.append(value)
                if resolved and any(value != resolved[0] for value in resolved[1:]):
                    raise ValueError(f"Shared timer {name} has different requested values")
                value = resolved[0] if resolved else None
                if suffix == "keep_alive_bound" and (value is None or value == ""):
                    # Camunda timers require a finite ISO value. Approximate
                    # an unspecified lifetime only in the instance payload.
                    if declaration.get("timer_type") == "time_date":
                        value = (datetime.now(timezone.utc) + timedelta(days=36525)).isoformat(timespec="seconds")
                    else:
                        value = "P100Y"
                payload[name] = value
                for identifier in declaration.get("declaration_ids", []):
                    binding = temporal_by_id.get(identifier)
                    if binding is not None:
                        temporal_values.append(ProcessInstanceTemporalConstraint(
                            id=f"pitv_{instance_id}_{binding.id}",
                            temporal_constraint_id=binding.id,
                            label=labels.get(binding.action_link_id, binding.label),
                            value=str(value) if value is not None else None,
                        ))
        return payload, generic_values, action_values, temporal_values
