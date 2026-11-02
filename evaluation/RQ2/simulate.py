#!/usr/bin/env python3
"""Replay worker outcomes on reviewed BPMN ground truth using virtual time."""
from __future__ import annotations

import argparse
import ast
import copy
import heapq
import io
import json
import math
import re
import sys
import tokenize
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "evaluation/RQ1"))
from instance_level import (
    PlanDefinition, RequestOrchestration, enriched_inventory,
    load_catalog, reference_variables,
)

BPMN = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
FACTORS = {"Y": 31536000, "M": 2592000, "W": 604800, "D": 86400}


def instant(value: str) -> datetime:
    """Parse a timezone-aware experiment timestamp.

    :param value: ISO 8601 timestamp with an explicit timezone.
    :return: Aware datetime; naive timestamps are rejected.
    """
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Experiment timestamps require a timezone")
    return result


def seconds(value: str) -> float:
    """Convert non-negative ISO durations using SHIFT's 30/365-day convention.

    :param value: ISO 8601 duration.
    :return: Duration in seconds.
    """
    match = re.fullmatch(
        r"P(?:(\d+(?:\.\d+)?)Y)?(?:(\d+(?:\.\d+)?)M)?"
        r"(?:(\d+(?:\.\d+)?)W)?(?:(\d+(?:\.\d+)?)D)?"
        r"(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?"
        r"(?:(\d+(?:\.\d+)?)S)?)?", value,
    )
    if not match or not any(match.groups()) or value.endswith("T"):
        raise ValueError(f"Unsupported duration: {value}")
    result = sum(float(x or 0) * factor for x, factor in zip(
        match.groups(), (31536000, 2592000, 604800, 86400, 3600, 60, 1)
    ))
    if not math.isfinite(result):
        raise ValueError("Duration must be finite")
    return result


def condition(expression: str, variables: Dict[str, Any]) -> Optional[bool]:
    """Evaluate simple comparison/Boolean conditions without eval or FEEL execution.

    :param expression: Dataset condition using %, =, and/or and comparisons.
    :param variables: Current simulated process variables.
    :return: Boolean result, or None when required state is unavailable.
    """
    text = expression.strip().removeprefix("=").strip()
    tokens = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.string == "%":
            continue
        value = "==" if token.string == "=" else token.string
        if token.type == tokenize.NAME and value in {"true", "false", "null"}:
            value = {"true": "True", "false": "False", "null": "None"}[value]
        tokens.append((token.type, value))
    tree = ast.parse(tokenize.untokenize(tokens), mode="eval")
    missing = object()

    def visit(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return variables.get(node.id, missing)
        if isinstance(node, ast.BoolOp):
            values = [visit(item) for item in node.values]
            values = [None if value is missing else value for value in values]
            if isinstance(node.op, ast.And):
                return False if False in values else None if None in values else all(values)
            return True if True in values else None if None in values else any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = visit(node.operand)
            return None if value is None or value is missing else not value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = visit(node.operand)
            return None if value is None or value is missing else -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.Compare):
            left = visit(node.left)
            results = []
            for operator, right_node in zip(node.ops, node.comparators):
                right = visit(right_node)
                if left is missing or right is missing:
                    results.append(None)
                elif isinstance(operator, ast.Eq):
                    results.append(left == right)
                elif isinstance(operator, ast.NotEq):
                    results.append(left != right)
                elif left is None or right is None:
                    results.append(None)
                elif isinstance(operator, ast.Lt):
                    results.append(left < right)
                elif isinstance(operator, ast.LtE):
                    results.append(left <= right)
                elif isinstance(operator, ast.Gt):
                    results.append(left > right)
                elif isinstance(operator, ast.GtE):
                    results.append(left >= right)
                else:
                    raise ValueError("Unsupported comparison operator")
                left = right
            return False if False in results else None if None in results else all(results)
        raise ValueError(f"Unsupported condition construct: {type(node).__name__}")

    result = visit(tree)
    if result is missing:
        return None
    if result is not None and not isinstance(result, bool):
        raise ValueError("A condition must evaluate to a Boolean")
    return result


def read_records(path: Path) -> List[Dict[str, Any]]:
    """Read worker JSONL records; malformed records fail with their line number.

    :param path: Worker invocation log.
    :return: Parsed records in file order.
    """
    records = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if line.strip():
            try:
                records.append(json.loads(line))
            except ValueError as error:
                raise ValueError(f"{path}:{number}: {error}") from error
    return records


def run_records(records: List[Dict[str, Any]], run: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Select one instance without conflating runs, retries or process versions.

    :param records: Worker invocation records.
    :param run: Experiment identity and observation window.
    :return: Chronologically ordered records for that instance and window.
    """
    start, end = instant(run["started_at"]), instant(run["observed_until"])
    selected = [r for r in records if str(r["process_instance_key"]) == str(run["process_instance_key"])
                and start <= instant(r["invoked_at"]) <= end]
    return sorted(selected, key=lambda r: (instant(r["invoked_at"]), str(r["job_key"])))


def correlate_records(records: List[Dict[str, Any]], engine: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach engine activation ordinals using element-instance keys, never completion order.

    :param records: Worker outcome records.
    :param engine: Normalized engine export; optional for worker-only analysis.
    :return: Copied records annotated with per-action activation occurrence.
    """
    activations = {}
    for event in engine:
        if event["type"] != "action.activated":
            continue
        key = (str(event["process_instance_key"]), str(event["task_instance_key"]))
        if key in activations or not isinstance(event.get("occurrence"), int) or event["occurrence"] < 1:
            raise ValueError("Engine activations require unique task-instance keys and positive occurrence")
        activations[key] = event
    result = copy.deepcopy(records)
    for record in result:
        event = activations.get((str(record["process_instance_key"]), str(record["task_instance_key"])))
        if event:
            if event["action"] != record["task_id"]:
                raise ValueError("Worker/engine action correlation mismatch")
            record["occurrence"] = event["occurrence"]
    return result


class Frame:
    """One dynamic scope activation, with independent join counters and children."""

    def __init__(self, element: ET.Element, parent: Optional[Frame], done: Optional[Callable], number: int) -> None:
        self.element, self.parent, self.done, self.number = element, parent, done, number
        self.alive, self.tokens = True, 0
        self.children: List[Frame] = []
        self.joins: Dict[str, Dict[str, List[List[str]]]] = defaultdict(lambda: defaultdict(list))
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.exit_causes: List[str] = []
        self.occurrence = 0
        self.nodes = {e.attrib["id"]: e for e in element if e.tag.startswith(BPMN) and "id" in e.attrib}
        self.outgoing: Dict[str, List[ET.Element]] = defaultdict(list)
        self.incoming: Dict[str, List[str]] = defaultdict(list)
        for e in element.findall(BPMN + "sequenceFlow"):
            self.outgoing[e.attrib["sourceRef"]].append(e)
            self.incoming[e.attrib["targetRef"]].append(e.attrib["id"])


class Simulator:
    """Independent event queue over reviewed BPMN, not SHIFT-generated structure.

    Worker outcomes/delays are an external tape. Missing outcomes block only the
    affected token; independent branches and scheduler subscriptions continue.
    """

    def __init__(self, process: ET.Element, variables: Dict[str, Any], records: List[Dict[str, Any]],
                 start: datetime, horizon: float, max_events: int = 200000) -> None:
        self.process, self.variables = process, copy.deepcopy(variables)
        self.start, self.horizon, self.max_events = start, horizon, max_events
        self.queue: List[Tuple[float, int, Callable]] = []
        self.serial, self.now, self.frame_number = 0, 0.0, 0
        self.events: List[Dict[str, Any]] = []
        self.unresolved: List[Dict[str, Any]] = []
        self.counts: Dict[str, int] = defaultdict(int)
        self.scope_counts: Dict[str, int] = defaultdict(int)
        self.tape: Dict[str, Dict[int, Dict[str, Any]]] = defaultdict(dict)
        ordinal: Dict[str, int] = defaultdict(int)
        for record in records:
            action = record["task_id"]
            ordinal[action] += 1
            occurrence = record.get("occurrence", ordinal[action])
            if occurrence in self.tape[action]:
                raise ValueError("Duplicate action occurrence in worker outcome tape")
            self.tape[action][occurrence] = record
        jobs = [r["job_key"] for r in records]
        if len(jobs) != len(set(jobs)):
            raise ValueError("Repeated job deliveries require an accepted-outcome tape; do not choose a retry implicitly")

    def event(self, kind: str, **data: Any) -> None:
        self.events.append({"type": kind, "time": self.now, **data})

    def schedule(self, when: float, callback: Callable) -> None:
        if when < self.now:
            raise ValueError("Cannot schedule an event in the past")
        self.serial += 1
        # Recurrence addition and lifetime addition must agree at the same
        # deadline; binary float residue must not create a last extra cycle.
        heapq.heappush(self.queue, (round(when, 9), self.serial, callback))

    def unknown(self, reason: str, **data: Any) -> None:
        self.unresolved.append({"time": self.now, "reason": reason, **data})

    def timer(self, node: ET.Element) -> Tuple[str, str]:
        definition = node.find(BPMN + "timerEventDefinition")
        if definition is None or len(definition) != 1:
            raise ValueError(f"Timer {node.attrib['id']} requires exactly one binding")
        item = definition[0]
        value = (item.text or "").strip()
        if value.startswith("="):
            name = value[1:].strip().strip("`")
            value = self.variables.get(name)
            if not isinstance(value, str):
                raise ValueError(f"Missing timer variable {name}")
        return item.tag.removeprefix(BPMN), value

    def due(self, node: ET.Element, base: float) -> float:
        kind, value = self.timer(node)
        if kind == "timeDuration":
            return base + seconds(value)
        if kind == "timeDate":
            return max(base, (instant(value) - self.start).total_seconds())
        raise ValueError("Cycles are supported only on event-subprocess starts")

    def enqueue(self, frame: Frame, node: str, causes: List[str], incoming: str = "") -> None:
        frame.tokens += 1
        self.schedule(self.now, lambda: self.visit(frame, node, causes, incoming) if frame.alive else None)

    def advance(self, frame: Frame, node: str, causes: List[str], flows: Optional[List[ET.Element]] = None) -> None:
        frame.tokens -= 1
        for flow in frame.outgoing[node] if flows is None else flows:
            self.enqueue(frame, flow.attrib["targetRef"], causes, flow.attrib["id"])
        if frame.tokens == 0:
            self.close(frame)

    def cancel_tree(self, frame: Frame) -> None:
        frame.alive = False
        for task in frame.tasks.values():
            if task["active"]:
                task["active"] = False
                if task["known"]:
                    self.event("action.cancelled", action=task["action"], occurrence=task["occurrence"])
        for child in frame.children:
            if child.alive:
                self.cancel_tree(child)

    def close(self, frame: Frame) -> None:
        if not frame.alive:
            return
        if frame.parent:
            self.event("scope.completed", element=frame.element.attrib["id"], occurrence=frame.occurrence)
        self.cancel_tree(frame)
        if frame.done:
            frame.done(frame.exit_causes)
        else:
            self.event("process.completed")

    def spawn(self, element: ET.Element, parent: Optional[Frame], done: Optional[Callable],
              causes: List[str], start_node: Optional[str] = None) -> Frame:
        self.frame_number += 1
        frame = Frame(element, parent, done, self.frame_number)
        self.scope_counts[element.attrib["id"]] += 1
        frame.occurrence = self.scope_counts[element.attrib["id"]]
        if parent:
            parent.children.append(frame)
        supported = {"extensionElements", "serviceTask", "task", "subProcess", "startEvent",
                     "endEvent", "boundaryEvent", "intermediateCatchEvent", "parallelGateway",
                     "exclusiveGateway", "sequenceFlow", "documentation", "incoming", "outgoing"}
        for child in element:
            if child.tag.startswith(BPMN) and child.tag.removeprefix(BPMN) not in supported:
                raise ValueError(f"Unsupported BPMN element: {child.tag}")
        for child in element.findall(BPMN + "subProcess"):
            if child.get("triggeredByEvent") == "true":
                starts = child.findall(BPMN + "startEvent")
                if len(starts) != 1 or starts[0].get("isInterrupting") != "false":
                    raise ValueError("Only non-interrupting timer event subprocesses are supported")
                self.subscribe(frame, child, starts[0], causes)
        starts = [start_node] if start_node else [s.attrib["id"] for s in element.findall(BPMN + "startEvent")]
        if len(starts) != 1:
            raise ValueError("Exactly one ordinary start is required per activated scope")
        self.enqueue(frame, starts[0], causes)
        return frame

    def subscribe(self, owner: Frame, subprocess: ET.Element, start: ET.Element, causes: List[str]) -> None:
        kind, value = self.timer(start)
        if kind != "timeCycle":
            raise ValueError("An event-subprocess scheduler requires a timeCycle")
        parts = value.split("/")
        if len(parts) not in (2, 3) or not re.fullmatch(r"R\d*", parts[0]):
            raise ValueError(f"Use the accelerated interval dataset, not cron: {value}")
        interval = seconds(parts[-1])
        if interval <= 0:
            raise ValueError("Cycle intervals must be positive")
        count = int(parts[0][1:]) if parts[0][1:] else None
        first = self.now + interval if len(parts) == 2 else max(self.now, (instant(parts[1]) - self.start).total_seconds())

        def trigger(index: int) -> None:
            if not owner.alive or count is not None and index >= count:
                return
            self.event("timer.fired", element=start.attrib["id"], frame=owner.number)
            owner.tokens += 1

            def finished(exit_causes: List[str]) -> None:
                if owner.alive:
                    owner.exit_causes = sorted(set(owner.exit_causes + exit_causes))
                    owner.tokens -= 1
                    if owner.tokens == 0:
                        self.close(owner)

            self.spawn(subprocess, owner, finished, causes, start.attrib["id"])
            self.schedule(self.now + interval, lambda: trigger(index + 1))

        self.schedule(first, lambda: trigger(0))

    def task(self, frame: Frame, node: ET.Element, causes: List[str]) -> None:
        action = node.attrib["id"]
        self.counts[action] += 1
        occurrence = self.counts[action]
        key = f"{action}#{occurrence}"
        state = {"active": True, "known": False, "action": action, "occurrence": occurrence}
        frame.tasks[key] = state
        self.event("action.activated", action=action, occurrence=occurrence,
                   causes=causes, inputs=copy.deepcopy(self.variables.get(action, {})), frame=frame.number)
        for boundary in frame.element.findall(BPMN + "boundaryEvent"):
            if boundary.get("attachedToRef") != action:
                continue
            if boundary.get("cancelActivity", "true") != "true":
                raise ValueError("Only interrupting timer boundaries are supported")

            def timeout(boundary: ET.Element = boundary) -> None:
                if frame.alive and state["active"] and state["known"]:
                    state["active"] = False
                    self.event("timer.fired", element=boundary.attrib["id"], frame=frame.number)
                    self.event("action.cancelled", action=action, occurrence=occurrence)
                    self.advance(frame, boundary.attrib["id"], [key])

            self.schedule(self.due(boundary, self.now), timeout)
        tape = self.tape[action]
        if occurrence not in tape:
            self.unknown("missing_worker_outcome", action=action, occurrence=occurrence)
            return
        record = tape[occurrence]
        delay = record.get("delay_seconds")
        if not isinstance(delay, (int, float)) or not math.isfinite(delay) or delay < 0:
            raise ValueError(f"Missing/non-negative delay_seconds required for {key}")
        state["known"] = True

        def complete() -> None:
            if frame.alive and state["active"]:
                state["active"] = False
                result = copy.deepcopy(record["result"])
                self.variables.update(result)
                self.event("action.completed", action=action, occurrence=occurrence, result=result)
                self.advance(frame, action, [key])

        self.schedule(self.now + delay, complete)

    def visit(self, frame: Frame, identifier: str, causes: List[str], incoming: str) -> None:
        node = frame.nodes[identifier]
        kind = node.tag.removeprefix(BPMN)
        if kind in {"task", "serviceTask"}:
            self.task(frame, node, causes)
        elif kind == "subProcess":
            self.spawn(node, frame, lambda exits: self.advance(frame, identifier, exits or causes), causes)
        elif kind == "parallelGateway" and len(frame.incoming[identifier]) > 1:
            waiting = frame.joins[identifier]
            waiting[incoming].append(causes)
            if all(waiting[flow] for flow in frame.incoming[identifier]):
                merged = sorted({cause for flow in frame.incoming[identifier] for cause in waiting[flow].pop(0)})
                frame.tokens -= len(frame.incoming[identifier]) - 1
                self.advance(frame, identifier, merged)
        elif kind == "exclusiveGateway" and len(frame.outgoing[identifier]) > 1:
            default = node.get("default")
            chosen, unknown = None, False
            for flow in frame.outgoing[identifier]:
                if flow.attrib["id"] == default:
                    continue
                expression = flow.find(BPMN + "conditionExpression")
                result = True if expression is None else condition(expression.text or "", self.variables)
                if result is None:
                    unknown = True
                    break
                if result:
                    chosen = flow
                    break
            if unknown:
                self.unknown("missing_condition_state", element=identifier, frame=frame.number)
                return
            if chosen is None:
                chosen = next((f for f in frame.outgoing[identifier] if f.attrib["id"] == default), None)
            if chosen is None:
                self.unknown("no_matching_branch_or_default", element=identifier)
                return
            self.event("branch.selected", element=identifier, flow=chosen.attrib["id"], frame=frame.number)
            self.advance(frame, identifier, causes, [chosen])
        elif kind == "endEvent":
            frame.exit_causes = sorted(set(frame.exit_causes + causes))
            if node.find(BPMN + "terminateEventDefinition") is not None:
                self.close(frame)
            else:
                self.advance(frame, identifier, causes)
        elif kind in {"startEvent", "intermediateCatchEvent"} and node.find(BPMN + "timerEventDefinition") is not None:
            if frame.element.get("triggeredByEvent") == "true" and kind == "startEvent":
                self.advance(frame, identifier, causes)
            else:
                def fired() -> None:
                    if frame.alive:
                        self.event("timer.fired", element=identifier, frame=frame.number)
                        self.advance(frame, identifier, causes)
                self.schedule(self.due(node, self.now), fired)
        elif kind in {"startEvent", "parallelGateway", "exclusiveGateway"}:
            self.advance(frame, identifier, causes)
        else:
            raise ValueError(f"Unsupported node: {kind}")

    def run(self) -> Dict[str, Any]:
        """Execute the event queue up to the declared observation horizon.

        :return: Expected trace, final state, coverage gaps and completion evidence.
        """
        frame = self.spawn(self.process, None, None, [])
        processed = 0
        while self.queue and self.queue[0][0] <= self.horizon:
            self.now, _, callback = heapq.heappop(self.queue)
            callback()
            processed += 1
            if processed > self.max_events:
                raise ValueError("Virtual event limit exceeded; shorten the observation window")
        return {"events": self.events, "unresolved": self.unresolved,
                "completed": not frame.alive, "final_variables": self.variables,
                "processed_events": processed}


def simulate_run(run: Dict[str, Any], records: List[Dict[str, Any]], requests: Path,
                 plans: Path, groundtruth: Path) -> Dict[str, Any]:
    """Build one expected execution from reviewed structure and current FHIR values.

    :param run: Explicit instance identity, start, horizon and optional initial inputs.
    :param records: Raw worker invocation log.
    :param requests: Selected RequestOrchestration dataset (fast timings by default).
    :param plans: PlanDefinition dataset.
    :param groundtruth: Reviewed instance-level BPMN references and catalog.
    :return: Simulation report without changing source resources or references.
    """
    start, end = instant(run["started_at"]), instant(run["observed_until"])
    horizon = (end - start).total_seconds()
    if horizon < 0:
        raise ValueError("observed_until must not precede started_at")
    case = run["process"]
    if not re.fullmatch(r"P\d+", case):
        raise ValueError("Process names must use P followed by digits")
    request = RequestOrchestration.model_validate_json((requests / f"{case}.json").read_text())
    plan = PlanDefinition.model_validate_json((plans / f"{case}.json").read_text())
    reference = groundtruth / f"{case}.bpmn"
    inventory, _, _ = enriched_inventory(reference)
    catalog = load_catalog(json.loads((groundtruth / "catalog.json").read_text()))
    values = reference_variables(plan, request, inventory, catalog)
    extras = run.get("initial_variables", {})
    if any(key.startswith("TC_") or isinstance(values.get(key), dict) or key == "subject" for key in extras):
        raise ValueError("initial_variables may supply condition inputs only, not replace FHIR action/timer values")
    values.update(extras)
    root = ET.parse(reference).getroot().find(BPMN + "process")
    if root is None:
        raise ValueError("Reference has no BPMN process")
    selected = run_records(records, run)
    if any(r.get("process_definition_id") != case for r in selected):
        raise ValueError("Worker process_definition_id does not match the selected FHIR/reference case")
    simulation = Simulator(root, values, selected, start, horizon).run()
    actions = {a.linkId: a for a in request.action}
    for event in simulation["events"]:
        if event["type"] == "action.activated":
            contract_id = actions[event["action"]].definitionCanonical.rstrip("/").split("/")[-1]
            event["activity_definition_id"] = contract_id
            event["job_type"] = catalog[contract_id].name
    return {"run": run, "reference_bpmn": str(reference), "request": str(requests / f"{case}.json"),
            "horizon_seconds": horizon, "initial_variables": values,
            "outcome_replay": "per-action chronological occurrence; retries rejected",
            **simulation}


def main(argv: Optional[List[str]] = None) -> int:
    """Write virtual traces, or create an editable run index from worker records.

    :param argv: Optional command-line arguments.
    :return: Zero on success, two for invalid experiment data.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=PROJECT / "evaluation/RQ2/runs.json")
    parser.add_argument("--invocations", type=Path, default=PROJECT / "camunda_jobworkers/data/invocations.jsonl")
    parser.add_argument("--engine-events", type=Path)
    parser.add_argument("--requests", type=Path, default=PROJECT / "evaluation/dataset/requestorchestration_fast_timing")
    parser.add_argument("--plans", type=Path, default=PROJECT / "evaluation/dataset/plandefinition")
    parser.add_argument("--groundtruth", type=Path, default=PROJECT / "evaluation/groundtruth/instance_camunda")
    parser.add_argument("--output", type=Path, default=PROJECT / "evaluation/RQ2/results/expected.json")
    parser.add_argument("--write-run-template", action="store_true")
    args = parser.parse_args(argv)
    try:
        records = correlate_records(read_records(args.invocations),
                                    read_records(args.engine_events) if args.engine_events else [])
        if args.write_run_template:
            groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for record in records:
                groups[str(record["process_instance_key"])].append(record)
            runs = [{"id": key, "process": rows[0]["process_definition_id"],
                     "process_instance_key": key, "started_at": None, "observed_until": None,
                     "initial_variables": {}} for key, rows in sorted(groups.items())]
            if args.runs.exists():
                raise ValueError("Run template already exists; it will not be overwritten")
            args.runs.parent.mkdir(parents=True, exist_ok=True)
            args.runs.write_text(json.dumps({"runs": runs}, indent=2) + "\n")
            print(f"Created {args.runs}; fill authoritative start/window timestamps before simulation")
            return 0
        runs = json.loads(args.runs.read_text())["runs"]
        identifiers = [run["id"] for run in runs]
        instances = [str(run["process_instance_key"]) for run in runs]
        if len(identifiers) != len(set(identifiers)) or len(instances) != len(set(instances)):
            raise ValueError("Each run and process instance must occur only once")
        reports = []
        for run in runs:
            try:
                reports.append(simulate_run(run, records, args.requests, args.plans, args.groundtruth))
            except Exception as error:
                reports.append({"run": run, "error": f"{type(error).__name__}: {error}"})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"runs": reports}, indent=2, ensure_ascii=False) + "\n")
        for report in reports:
            print(report["run"]["id"], report.get("error") or
                  f"events={len(report['events'])}, gaps={len(report['unresolved'])}, completed={report['completed']}")
        return 2 if any("error" in r for r in reports) else 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"Simulation setup error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
