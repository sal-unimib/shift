#!/usr/bin/env python3
"""Evaluate RequestOrchestration transformations without deploying or starting processes."""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from definition_level import (
    BPMNInventory, CATEGORIES as STRUCTURE, CHECKS, compare, key, scores,
    timer_value, write_csv, PROJECT,
)
from fhir.resources.plandefinition import PlanDefinition
from fhir.resources.requestorchestration import RequestOrchestration
from src.domain import bpmn
from src.domain.action_definition import ActionDefinition, ActionDefinitionAttribute
from src.domain.bpe_extensions import camunda
from src.domain.cfg import ControlFlowGraphFactory as Factory, InstanceControlFlowGraph
from src.domain.enums import CFGType
from src.mappers.bpmn_mapper import BPMNStandardMapper
from src.mappers.camunda_enricher import CamundaBPMNEnricher
from src.mappers.instance_enrichment_mapper import InstanceEnrichmentMapper
from src.mappers.process_definition_mapper import ProcessDefinitionMapper
from src.utils.definition_alignment import DefinitionAlignment
from src.utils.serializers import BPMNSerializer

CATEGORIES = STRUCTURE + (
    "conditions", "job_workers", "form_fields", "process_metadata",
    "runtime_variables", "alignment_decision", "definition_alignment",
)
MEASURES = ["tp", "fp", "fn", "precision", "recall", "f1"]
CYCLIC = {"standard_cycle", "instance_cycle", "keep_alive_bound"}


def source_actions(resource: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Collect clinical source actions, retaining exact linkId correspondence."""
    result: Dict[str, Dict[str, Any]] = {}
    pending = list(resource.get("action", []))
    while pending:
        action = pending.pop(0)
        pending[0:0] = action.get("action", [])
        if action.get("definitionCanonical"):
            identifier = action.get("linkId")
            if not identifier or identifier in result:
                raise ValueError("Missing/duplicate action linkId")
            result[identifier] = action
    return result


def source_profile(resource: Dict[str, Any]) -> Dict[str, Any]:
    """Describe alignment requirements directly from FHIR, independently of DefinitionAlignment."""
    actions = source_actions(resource)
    relations = set()
    categories: Dict[str, List[str]] = {}
    schedules = {}
    for aid, action in actions.items():
        related = action.get("relatedAction", [])
        for relation in related:
            target = relation["targetId"]
            kind = relation["relationship"]
            if kind == "after-end":
                relations.add((target, aid))
            elif kind == "before-end":
                relations.add((aid, target))
            else:
                raise ValueError(f"Review unsupported oracle relationship: {kind}")
        timing = action.get("timingTiming") or {}
        repeat = timing.get("repeat") or {}
        types = set()
        if repeat.get("frequency") or repeat.get("period"):
            types.add("standard_cycle")
        if any(repeat.get(field) for field in ("dayOfWeek", "timeOfDay", "when")) or (timing.get("code") or {}).get("coding"):
            types.add("instance_cycle")
        if any(repeat.get(field) is not None for field in ("boundsDuration", "boundsPeriod")):
            types.add("keep_alive_bound")
        if timing.get("event"):
            types.add("exact")
        if repeat.get("durationMax") is not None:
            types.add("execution_bound")
        if any(relation.get("offsetDuration") is not None for relation in related):
            types.add("offset")
        categories[aid] = sorted((types - CYCLIC) | ({"cyclic_scope"} if types & CYCLIC else set()))
        if types & CYCLIC:
            schedule = copy.deepcopy(timing)
            # code.text is a label, not schedule semantics.
            if "code" in schedule:
                schedule["code"].pop("text", None)
                if not schedule["code"]:
                    schedule.pop("code")
            for field in ("dayOfWeek", "timeOfDay", "when"):
                if field in (schedule.get("repeat") or {}):
                    schedule["repeat"][field] = sorted(schedule["repeat"][field])
            schedules[aid] = schedule
    # Parallel siblings have the same sole predecessor, or are both entry actions.
    cohorts: Dict[str, List[str]] = defaultdict(list)
    for aid, schedule in schedules.items():
        predecessors = sorted(source for source, target in relations if target == aid)
        if len(predecessors) > 1 or actions[aid].get("condition"):
            continue
        cohorts[key([predecessors, schedule])].append(aid)
    return {
        "actions": {aid: action["definitionCanonical"].split("|")[0].rstrip("/").split("/")[-1] for aid, action in actions.items()},
        "relations": sorted([list(pair) for pair in relations]),
        "structural_categories": categories,
        "shared_groups": sorted([sorted(group) for group in cohorts.values() if len(group) > 1]),
    }


def expected_alignment(plan: Dict[str, Any], request: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Return a source-based alignment oracle and explicit reasons for review."""
    before, after = source_profile(plan), source_profile(request)
    reasons = []
    for field in ("actions", "relations", "structural_categories", "shared_groups"):
        if before[field] != after[field]:
            reasons.append(field)
    return bool(reasons), reasons


def load_catalog(raw: List[Dict[str, Any]]) -> Dict[str, ActionDefinition]:
    """Construct domain action contracts from the frozen source catalog."""
    result = {}
    for item in raw:
        attributes = [
            ActionDefinitionAttribute("", dynamic["path"], dynamic["expression"]["expression"], "string")
            for dynamic in item.get("dynamicValue", [])
        ]
        result[item["id"]] = ActionDefinition(
            item["id"], item["name"], item.get("title", ""), item.get("description", ""),
            item["kind"], attributes,
        )
    return result


def transform(
    plan: PlanDefinition, request: RequestOrchestration,
    catalog: Dict[str, ActionDefinition], directory: Path,
    force_alignment: Optional[bool] = None,
) -> Dict[str, Any]:
    """Run the instance transformation offline and record the executed branch.

    :param plan: Validated source PlanDefinition.
    :param request: Validated source RequestOrchestration.
    :param catalog: Source ActivityDefinition contracts.
    :param directory: Isolated artifact destination.
    :param force_alignment: Reference preparation only; None evaluates the actual decision.
    :return: Selected version, executed alignment flag and artifact paths.
    """
    classic = Factory.from_plandefinition(plan)
    temporal = Factory.cfg_with_temporal_structures(Factory.cfg_with_gateways(classic))
    parent = ProcessDefinitionMapper.map(plan, temporal, catalog)
    request_graph = Factory.from_request_orchestration(request, classic)
    required = DefinitionAlignment.requires_alignment(request_graph, classic)
    selected = required if force_alignment is None else force_alignment
    performed = False
    if selected:
        template = Factory.cfg_with_temporal_structures(Factory.cfg_with_gateways(request_graph))
        definition = ProcessDefinitionMapper.map_specialization(
            request, template, parent, catalog, request_graph.get_specialized_version()
        )
        model = BPMNStandardMapper.map(template)
        performed = True  # Set only after reconstruction has succeeded.
    else:
        template, definition = temporal, parent
        model = BPMNStandardMapper.map(temporal)
    variables, workers = InstanceEnrichmentMapper.build(definition, request_graph, template, catalog)
    enriched = CamundaBPMNEnricher.enrich(model, definition.version, variables, workers)
    payload, _, _, _ = InstanceEnrichmentMapper.build_values(
        definition, request, request_graph, variables, "evaluation"
    )
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "instance.camunda.bpmn"
    path.write_text(BPMNSerializer().serialize(enriched, CamundaBPMNEnricher.get_namespaces()), encoding="utf-8")
    (directory / "variables.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    evidence = {
        "alignment_required": required, "alignment_performed": performed,
        "evidence": "offline_transform_executed_branch",
        "request_id": request.id, "version": definition.version,
    }
    (directory / "alignment.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return {"path": path, "variables": payload, **evidence}


def extensions(element: Any, cls: Any) -> List[Any]:
    """Read typed Camunda extensions from a BPMN element."""
    extension = getattr(element, "extension_elements", None)
    return [item for item in extension.other_element if isinstance(item, cls)] if extension else []


def normalized_expression(text: str) -> List[str]:
    """Ignore formatting whitespace while preserving spaces inside quoted literals."""
    return re.findall(r"'(?:\\.|''|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|\S+", text.strip())


def enriched_inventory(path: Path) -> Tuple[BPMNInventory, Dict[str, Counter], str]:
    """Extract structural, condition, worker, form and process facts."""
    inventory = BPMNInventory(path)
    extra = {name: Counter() for name in ("conditions", "job_workers", "form_fields", "process_metadata")}
    process = inventory.definition.process[0]
    tags = extensions(process, camunda.VersionTag)
    versions = [tag.value for tag in tags]
    for version in versions:
        extra["process_metadata"][key(["version", version])] += 1
    extra["process_metadata"][key(["executable", bool(process.is_executable)])] += 1
    extra["process_metadata"][key(["process_id", process.id])] += 1

    def form_fields(components: List[Dict[str, Any]], prefix: List[str]) -> None:
        for component in components:
            if component.get("type") == "group":
                group = prefix + [component.get("path")]
                extra["form_fields"][key([group, "group"])] += 1
                form_fields(component.get("components", []), group)
            else:
                extra["form_fields"][key([prefix + [component.get("key")], component.get("type")])] += 1
            for forbidden in ("label", "defaultValue", "value"):
                if forbidden in component:
                    extra["form_fields"][key(["unexpected", forbidden, prefix, component.get("key")])] += 1

    for form in extensions(process, camunda.UserTaskForm):
        schema = json.loads(form.value)
        extra["process_metadata"][key(["form_id", form.id, schema.get("id")])] += 1
        form_fields(schema.get("components", []), [])
    for scope, scope_path, nodes, flows in inventory.scopes:
        defaults = {node.default for node in nodes.values() if getattr(node, "default", None)}
        for flow in flows:
            if flow.condition_expression is not None:
                expression = "".join(flow.condition_expression.content)
                extra["conditions"][key([scope_path, flow.source_ref, flow.target_ref, normalized_expression(expression)])] += 1
            if flow.id in defaults:
                extra["conditions"][key([scope_path, flow.source_ref, flow.target_ref, "default"])] += 1
        for node in nodes.values():
            if isinstance(node, bpmn.TTask):
                definitions = extensions(node, camunda.TaskDefinition)
                for definition in definitions:
                    extra["job_workers"][key([node.id, isinstance(node, bpmn.ServiceTask), definition.type])] += 1
                if not definitions:
                    extra["job_workers"][key([node.id, isinstance(node, bpmn.ServiceTask), None])] += 1
            if isinstance(node, bpmn.StartEvent):
                for form in extensions(node, camunda.FormDefinition):
                    extra["process_metadata"][key(["start_form", node.id, form.formKey])] += 1
    if len(versions) != 1:
        raise ValueError("Exactly one Camunda versionTag is required as definition-selection evidence")
    return inventory, extra, versions[0]


def reference_variables(
    plan: PlanDefinition, request: RequestOrchestration,
    reference: BPMNInventory, catalog: Dict[str, ActionDefinition],
) -> Dict[str, Any]:
    """
    Resolve source FHIR values using the reviewed BPMN form as the binding schema.

    :param plan: Source PlanDefinition providing action defaults.
    :type plan: PlanDefinition
    :param request: Patient-specific workflow providing overrides.
    :type request: RequestOrchestration
    :param reference: Reviewed BPMN inventory with an embedded form.
    :type reference: BPMNInventory
    :param catalog: ActivityDefinition contracts.
    :type catalog: Dict[str, ActionDefinition]
    :return: Values keyed exactly as declared in the form.
    :rtype: Dict[str, Any]
    :raises ValueError: If form bindings conflict with the FHIR sources.
    """
    from src.domain.enums import CFGEventType, TemporalCategory
    from src.domain.nodes import TimerEventNode
    from src.domain.temporal_constraint import FHIRTemporalConstraint
    from datetime import timedelta

    process = reference.definition.process[0]
    forms = extensions(process, camunda.UserTaskForm)
    if len(forms) != 1:
        raise ValueError("Exactly one embedded form is required")
    schema = json.loads(forms[0].value)
    clinical = ProcessDefinitionMapper.actions(request)
    defaults = ProcessDefinitionMapper.actions(plan)
    values: Dict[str, Any] = {}
    timer_types: Dict[str, str] = {}
    for _, _, nodes, _ in reference.scopes:
        for node in nodes.values():
            for timer in getattr(node, "timer_event_definition", []):
                for kind in ("time_cycle", "time_duration", "time_date"):
                    expression = getattr(timer, kind)
                    if expression is not None:
                        name = "".join(expression.content).strip().removeprefix("=").strip()
                        if name.startswith(chr(96)) and name.endswith(chr(96)):
                            name = name[1:-1]
                        if name.startswith("TC_"):
                            previous = timer_types.setdefault(name, kind)
                            if previous != kind:
                                raise ValueError(f"Conflicting timer types for {name}")

    def normalize_path(path: str) -> str:
        return re.sub(r"\[(?:0)?\]", "", path)

    def action_value(action: Any, path: str) -> Tuple[bool, Any]:
        candidates = [
            dynamic.expression.expression
            for dynamic in (action.dynamicValue or []) if dynamic.expression is not None
            and normalize_path(dynamic.path) == normalize_path(path)
        ] if action is not None else []
        if candidates and any(candidate != candidates[0] for candidate in candidates[1:]):
            raise ValueError(f"Conflicting source values for {path}")
        return bool(candidates), candidates[0] if candidates else None

    for component in schema.get("components", []):
        if component.get("type") == "group":
            aid = component.get("path")
            if aid in values or aid not in clinical:
                raise ValueError(f"Invalid or duplicate form action group: {aid}")
            action = clinical[aid]
            catalog_id = action.definitionCanonical.rstrip("/").split("/")[-1]
            attributes = {attribute.id: attribute for attribute in catalog[catalog_id].attributes}
            group: Dict[str, Any] = {}
            for field in component.get("components", []):
                name = field.get("key")
                if name in group:
                    raise ValueError(f"Duplicate action form field: {aid}.{name}")
                if name == "resource":
                    group[name] = action.resource.reference
                elif name in attributes:
                    supplied, value = action_value(action, attributes[name].path)
                    if not supplied:
                        _, value = action_value(defaults.get(aid), attributes[name].path)
                    if value is not None and ProcessDefinitionMapper._condition_names(value):
                        value = None
                    group[name] = value
                else:
                    raise ValueError(f"Unknown action form field: {aid}.{name}")
            values[aid] = group
            continue

        name = component.get("key")
        if not isinstance(name, str) or name in values:
            raise ValueError(f"Invalid or duplicate top-level form field: {name}")
        if name == "subject":
            values[name] = request.subject.reference.rstrip("/").split("/")[-1]
        elif name.startswith("TC_"):
            match = re.fullmatch(
                r"TC_(.+)_(cycle|exact|offset|execution_duration|execution_iteration|execution_bound|keep_alive_bound)",
                name,
            )
            if match is None:
                raise ValueError(f"Unknown temporal form binding: {name}")
            members, suffix = match.groups()
            resolved = []
            for aid in members.split("+"):
                if aid not in clinical:
                    raise ValueError(f"Unknown temporal action: {aid}")
                action = clinical[aid]
                offsets = [
                    relation.offsetDuration for relation in action.relatedAction or []
                    if relation.offsetDuration is not None
                ]
                if len(offsets) > 1:
                    raise ValueError(f"Multiple offsets for {aid} require explicit review")
                raw = FHIRTemporalConstraint.from_fhir_constraints(
                    action.timingTiming, offsets[0] if offsets else None
                ) if action.timingTiming is not None or offsets else None
                category = TemporalCategory.STANDARD_CYCLE if suffix == "cycle" else TemporalCategory(suffix)
                if raw is not None and suffix == "cycle":
                    category = next(
                        (category for category in raw.get_categories() if category in {
                            TemporalCategory.STANDARD_CYCLE, TemporalCategory.INSTANCE_CYCLE
                        }), TemporalCategory.STANDARD_CYCLE,
                    )
                constraint = raw.to_event_temporal_constraint(aid, category) if raw is not None else None
                value = None
                if constraint is not None:
                    if category == TemporalCategory.EXECUTION_DURATION:
                        value = BPMNStandardMapper._duration(constraint.duration, constraint.duration_unit)
                    elif category == TemporalCategory.EXECUTION_ITERATION:
                        if constraint.count_max is not None and constraint.count_max != constraint.count:
                            raise ValueError(f"Unresolved count range for {aid}")
                        value = constraint.count
                    else:
                        binding = BPMNStandardMapper._timer_binding(
                            TimerEventNode(f"reference_{aid}", CFGEventType.START, constraint)
                        )
                        value = binding[1] if binding is not None else None
                if value is None and suffix == "keep_alive_bound":
                    value = (
                        (datetime.now(timezone.utc) + timedelta(days=36525)).isoformat(timespec="seconds")
                        if timer_types.get(name) == "time_date" else "P100Y"
                    )
                resolved.append(value)
            if any(value != resolved[0] for value in resolved[1:]):
                raise ValueError(f"Shared variable {name} has unequal source values")
            values[name] = resolved[0]
        else:
            # Conditions' result variables remain unresolved until activity execution.
            values[name] = None
    if set(timer_types) - set(values):
        raise ValueError("A BPMN timer variable has no corresponding form field")
    return values


def variable_facts(payload: Dict[str, Any]) -> Counter:
    """Compare runtime values per nested action attribute or top-level variable."""
    result = Counter()
    for name, value in payload.items():
        items = value.items() if isinstance(value, dict) else [(None, value)]
        for attribute, item in items:
            if name.startswith("TC_") and isinstance(item, str):
                kind = "timeDate" if name.endswith("_exact") else "timeCycle" if name.endswith("_cycle") else "timeDuration"
                item = timer_value(kind, item)
            elif isinstance(item, str):
                try:
                    parsed = json.loads(item)
                    if isinstance(parsed, (dict, list)):
                        item = ["json_text", parsed]
                except ValueError:
                    pass
            result[key([[name, attribute] if attribute is not None else [name], item])] += 1
    return result


def selected_artifact(root: Path, case: str, plan: PlanDefinition, request: RequestOrchestration) -> Optional[Path]:
    """Find one existing output, refusing ambiguous root/specialized artifacts."""
    own = root / case / "instance.camunda.bpmn"
    if own.is_file():
        return own
    plain = root / (case + ".bpmn")
    if plain.is_file():
        return plain
    patient = request.subject.reference.rstrip("/").split("/")[-1]
    prefix = f"{plan.id}_{plan.version}"
    candidates = [root / f"{prefix}_{patient}.camunda.bpmn", root / f"{prefix}.camunda.bpmn"]
    matches = [path for path in candidates if path.is_file()]
    if len(matches) > 1:
        raise ValueError("Ambiguous artifacts: provide case-specific instance.camunda.bpmn")
    return matches[0] if matches else None


def alignment_evidence(
    root: Path, case: str, plan: PlanDefinition, request: RequestOrchestration, version: str
) -> Tuple[Optional[bool], str]:
    """Verify selected specialization from a trace or matching serialized instance CFG."""
    sidecar = root / case / "alignment.json"
    if not sidecar.is_file():
        sidecar = root / f"{case}.alignment.json"
    if sidecar.is_file():
        evidence = json.loads(sidecar.read_text())
        if evidence.get("request_id") != request.id or evidence.get("version") != version or not isinstance(evidence.get("alignment_performed"), bool):
            raise ValueError("Alignment trace does not match request/selected version")
        return evidence["alignment_performed"], "matching_alignment_trace"
    if version == plan.version:
        return False, "selected_root_versionTag"
    cfg_path = root / f"{plan.id}_{version}.cfg.classic.json"
    if cfg_path.is_file():
        graph = Factory.from_json(json.loads(cfg_path.read_text()))
        if (isinstance(graph, InstanceControlFlowGraph)
                and graph.request_orchestration_id == request.id
                and graph.subject_id == request.subject.reference.rstrip("/").split("/")[-1]
                and graph.id == plan.id and graph.version == plan.version
                and graph.get_specialized_version() == version):
            current = Factory.from_request_orchestration(request, Factory.from_plandefinition(plan))
            if graph.to_json() != current.to_json():
                return None, "selected_instance_CFG_differs_from_current_request"
            return True, "selected_versionTag_and_matching_instance_CFG"
    return None, "missing_specialization_evidence"


def evaluate(request_path: Path, config: argparse.Namespace, catalog: Dict[str, ActionDefinition]) -> Dict[str, Any]:
    """Compare one RequestOrchestration output with its reviewed BPMN/value reference."""
    case = request_path.stem
    try:
        raw_request = json.loads(request_path.read_text())
        request = RequestOrchestration.model_validate(raw_request)
        plan_id, plan_version = request.instantiatesCanonical[0].rsplit("/", 1)[-1].split("|")
        plans = [path for path in (config.dataset / "plandefinition").glob("*.json")
                 if (raw := json.loads(path.read_text())).get("id") == plan_id and raw.get("version") == plan_version]
        if len(plans) != 1:
            raise ValueError("Expected exactly one matching PlanDefinition")
        raw_plan = json.loads(plans[0].read_text())
        plan = PlanDefinition.model_validate(raw_plan)
        reference, reference_extra, reference_version = enriched_inventory(config.groundtruth / f"{case}.bpmn")
        expected_required = reference_version != plan.version
        if reference.facts["actions"] != Counter(key(aid) for aid in source_actions(raw_request)):
            raise ValueError("Reference action IDs differ from RequestOrchestration linkIds")
        runtime_reference = json.loads((config.groundtruth / f"{case}.variables.json").read_text())
        metrics, checks = {}, {}
        actual_graph = Factory.from_request_orchestration(request, Factory.from_plandefinition(plan))
        required = DefinitionAlignment.requires_alignment(actual_graph, Factory.from_plandefinition(plan))
        generation_error = None
        if config.generate:
            try:
                output = transform(plan, request, catalog, config.output / "artifacts" / case)
                path, runtime_actual = output["path"], output["variables"]
                performed, evidence = output["alignment_performed"], output["evidence"]
            except Exception as error:
                path, runtime_actual, performed, evidence = None, None, None, "generation_failed"
                generation_error = str(error)
        else:
            path = selected_artifact(config.artifacts, case, plan, request)
            runtime_path = config.artifacts / case / "variables.json"
            if not runtime_path.is_file():
                runtime_path = config.artifacts / f"{case}.variables.json"
            if not runtime_path.is_file() and path is not None:
                runtime_path = path.with_suffix(".variables.json")
            runtime_actual = json.loads(runtime_path.read_text()) if runtime_path.is_file() else None
            performed, evidence = None, "missing_output"
        actual, actual_extra = None, {}
        if path is not None and path.is_file():
            actual, actual_extra, version = enriched_inventory(path)
            if not config.generate:
                performed, evidence = alignment_evidence(config.artifacts, case, plan, request, version)
        for category in STRUCTURE:
            metrics[category] = compare(actual.facts[category] if actual else Counter(), reference.facts[category])
        for category in reference_extra:
            metrics[category] = compare(actual_extra.get(category, Counter()), reference_extra[category])
        for check in CHECKS:
            checks[check] = compare(actual.facts[check] if actual else Counter(), reference.facts[check])
        if runtime_actual is not None:
            metrics["runtime_variables"] = compare(variable_facts(runtime_actual), variable_facts(runtime_reference))
        expected_positive = Counter({key("alignment"): 1}) if expected_required else Counter()
        metrics["alignment_decision"] = compare(Counter({key("alignment"): 1}) if required else Counter(), expected_positive)
        if performed is not None:
            metrics["definition_alignment"] = compare(Counter({key("alignment"): 1}) if performed else Counter(), expected_positive)
        total = scores(*(sum(metric[count] for metric in metrics.values()) for count in ("tp", "fp", "fn")))
        return {
            "process": case, "status": "generation_error" if generation_error else "evaluated",
            "reference_status": "reviewed",
            "alignment_expected_evidence": "reviewed_reference_versionTag",
            "alignment_expected": expected_required, "alignment_required": required,
            "alignment_performed": performed, "alignment_evidence": evidence,
            "alignment_correct": performed == expected_required if performed is not None else None,
            "alignment_tn": int(not expected_required and performed is False),
            "unavailable_categories": [category for category in CATEGORIES if category not in metrics],
            "actual_bpmn": str(path) if path else None, "generation_error": generation_error,
            "metrics": metrics, "checks": checks, "total": total,
        }
    except Exception as error:
        return {"process": case, "status": "error", "error": f"{type(error).__name__}: {error}"}


def main(argv: Optional[List[str]] = None) -> int:
    """Evaluate existing or isolated generated instance artifacts and aggregate micro metrics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=PROJECT / "evaluation/dataset")
    parser.add_argument("--groundtruth", type=Path, default=PROJECT / "evaluation/groundtruth/instance_camunda")
    parser.add_argument("--artifacts", type=Path, default=PROJECT / "data/storage/fs")
    parser.add_argument("--output", type=Path, default=PROJECT / "evaluation/RQ1/results" / "instance")
    parser.add_argument("--generate", action="store_true", help="Offline pipeline: no DB, deployment, process start or workers.")
    parser.add_argument("--fail-on-differences", action="store_true")
    args = parser.parse_args(argv)
    for name in ("dataset", "groundtruth", "artifacts", "output"):
        setattr(args, name, getattr(args, name).resolve())
    try:
        inputs = sorted((args.dataset / "requestorchestration").glob("*.json"))
        if not inputs or not args.groundtruth.is_dir():
            raise ValueError("Dataset or instance reference directory is missing")
        if any(args.output.is_relative_to(path) or path.is_relative_to(args.output) for path in (args.dataset, args.groundtruth, args.artifacts)):
            raise ValueError("Output must be separate from inputs")
        catalog = load_catalog(json.loads((args.groundtruth / "catalog.json").read_text()))
        args.output.mkdir(parents=True, exist_ok=True)
        generated = args.output / "artifacts"
        if generated.is_symlink():
            raise ValueError("Generated artifacts directory must not be a symbolic link")
        if generated.exists():
            shutil.rmtree(generated)
        results = [evaluate(path, args, catalog) for path in inputs]
        valid = [row for row in results if "metrics" in row]
        metric_rows, category_rows = [], []
        for category in CATEGORIES + CHECKS:
            section = "checks" if category in CHECKS else "metrics"
            applicable = [row for row in valid if category in row[section]]
            totals = scores(*(sum(row[section][category][count] for row in applicable) for count in ("tp", "fp", "fn")))
            category_rows.append({
                "category": category, "level": "check" if category in CHECKS else "category",
                **totals, "evaluated_processes": len(applicable),
                "unavailable_processes": len(valid) - len(applicable), "error_processes": len(results) - len(valid),
            })
            for row in applicable:
                metric_rows.append({"process": row["process"], "category": category, **row[section][category]})
        differences = [
            {"process": row["process"], "category": category, "difference": difference, "fact": key(fact)}
            for row in valid for section in ("metrics", "checks")
            for category, metric in row[section].items()
            for difference in ("missing", "additional") for fact in metric[difference]
        ]
        write_csv(args.output / "differences.csv", differences, ["process", "category", "difference", "fact"])
        process_rows = [
            {key_: row.get(key_) for key_ in ("process", "status", "reference_status")}
            | row.get("total", {})
            | {"unavailable_categories": ";".join(row.get("unavailable_categories", [])),
               "error": row.get("error") or row.get("generation_error")}
            for row in results
        ]
        alignment_rows = [{
            key_: row.get(key_) for key_ in ("process", "alignment_expected", "alignment_required", "alignment_performed", "alignment_evidence", "alignment_correct", "alignment_tn")
        } | row.get("metrics", {}).get("definition_alignment", {}) for row in results]
        write_csv(args.output / "metrics.csv", metric_rows, ["process", "category"] + MEASURES)
        write_csv(args.output / "process_metrics.csv", process_rows, ["process", "status", "reference_status"] + MEASURES + ["unavailable_categories", "error"])
        write_csv(args.output / "category_metrics.csv", category_rows, ["category", "level"] + MEASURES + ["evaluated_processes", "unavailable_processes", "error_processes"])
        write_csv(args.output / "alignment.csv", alignment_rows, ["process", "alignment_expected", "alignment_required", "alignment_performed", "alignment_evidence", "alignment_correct", "alignment_tn"] + MEASURES)
        report = {
            "mode": "offline_generated" if args.generate else "existing_artifacts",
            "by_process": process_rows, "by_category": category_rows, "cases": results,
            "alignment": {
                **scores(*(sum(row.get("metrics", {}).get("definition_alignment", {}).get(count, 0) for row in valid) for count in ("tp", "fp", "fn"))),
                "tn": sum(row["alignment_tn"] for row in valid),
                "unknown": sum(row["alignment_performed"] is None for row in valid),
            },
            "notes": [
                "Expected BPMNs were reviewed by the user; expected alignment follows their root/specialized versionTag.",
                "Runtime values are checked only when an actual variables.json is provided or generated offline; they are never inferred from form declarations.",
                "Alignment decision and selected specialization are distinct checks. Missing execution/lineage evidence remains unknown.",
                "Offline alignment evidence describes the evaluator's executed transformation branch, not a live InstanceService/engine execution.",
                "Process totals sum category counts; diagnostic checks are excluded to prevent double counting. Empty denominators remain null.",
            ],
        }
        (args.output / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        for row in results:
            if "total" not in row:
                print(f"{row['process']}: ERROR {row['error']}")
            else:
                print(f"{row['process']}: alignment expected={row['alignment_expected']}, required={row['alignment_required']}, performed={row['alignment_performed']}; TP={row['total']['tp']}, FP={row['total']['fp']}, FN={row['total']['fn']}; reference={row['reference_status']}")
        unavailable = {row["process"]: row["unavailable_categories"] for row in valid if row["unavailable_categories"]}
        if unavailable:
            print("Unavailable categories (not counted as correct): " + json.dumps(unavailable))
        print("Results: " + str(args.output))
        differences = any("total" not in row or row.get("generation_error") or row["total"]["fp"] or row["total"]["fn"] or row["unavailable_categories"] for row in results)
        return 1 if args.fail_on_differences and differences else 0
    except Exception as error:
        print(f"Evaluation setup error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
