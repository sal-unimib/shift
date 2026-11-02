#!/usr/bin/env python3
"""Compare definition-level BPMNs with ground truth using element/edge checks."""
from __future__ import annotations

import argparse
import csv
import json
import sys
import shutil
from collections import Counter, defaultdict
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fhir.resources.plandefinition import PlanDefinition
from src.domain import bpmn
from src.utils.serializers import BPMNSerializer

PROJECT = Path(bpmn.__file__).resolve().parents[3]
CATEGORIES = ("actions", "edges", "temporal_constraints", "subprocesses", "gateways")
CHECKS = ("timer_events", "timer_values", "subprocess_actions", "subprocess_edges",
          "diverging_gateways", "converging_gateways")
NAMESPACES = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "di": "http://www.omg.org/spec/DD/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


def key(value: Any) -> str:
    """Encode a comparable element/edge description.

    :param value: JSON-compatible description.
    :return: Stable multiset key.
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def children(value: Any) -> Iterator[Any]:
    """Read immediate typed children of a SHIFT BPMN dataclass.

    :param value: Domain dataclass.
    :return: Child dataclass objects.
    """
    for field in fields(value):
        item = getattr(value, field.name)
        for child in item if isinstance(item, list) else [item]:
            if is_dataclass(child):
                yield child


def is_action(node: bpmn.TFlowNode) -> bool:
    """Recognize task and call-activity domain classes.

    :param node: BPMN flow node.
    :return: Whether this is an action.
    """
    return isinstance(node, (bpmn.TTask, bpmn.CallActivity))


def scope_actions(scope: Any) -> List[str]:
    """Collect descendant action IDs without ignoring nested subprocesses.

    :param scope: Process or subprocess.
    :return: Sorted descendant action IDs, preserving duplicates.
    """
    result = []
    for node in children(scope):
        if isinstance(node, bpmn.TFlowNode) and is_action(node):
            result.append(node.id)
        elif isinstance(node, bpmn.TSubProcess):
            result.extend(scope_actions(node))
    return sorted(result)


def timer_value(kind: str, value: str) -> Any:
    """Compare equivalent fixed ISO durations without approximating months.

    :param kind: BPMN timer value field.
    :param value: Timer expression text.
    :return: Normalized value; unsupported expressions remain literal.
    """
    value = value.strip()
    if kind == "timeCycle":
        if value.startswith("R") and "/" in value:
            count, duration = value.split("/", 1)
            return [count, timer_value("timeDuration", duration)]
        return " ".join(value.split())
    if kind == "timeDate":
        try:
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if date.utcoffset() is not None:
                return date.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    if kind == "timeDuration":
        pattern = r"P(?:(\d+(?:\.\d+)?)Y)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)W)?(?:(\d+(?:\.\d+)?)D)?(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?"
        match = re.fullmatch(pattern, value)
        if match and any(match.groups()):
            y, mo, w, d, h, mi, s = [Decimal(v or "0") for v in match.groups()]
            return {"months": str((12*y+mo).normalize()),
                    "seconds": str((604800*w+86400*d+3600*h+60*mi+s).normalize())}
    return value


def timer_definition(timer: bpmn.TimerEventDefinition) -> List[Any]:
    """Read typed timer values, including intentionally empty definitions.

    :param timer: Domain timer definition.
    :return: Empty list or the normalized field/value.
    """
    values = []
    for attr, name in (("time_cycle", "timeCycle"), ("time_duration", "timeDuration"),
                       ("time_date", "timeDate")):
        expression = getattr(timer, attr)
        if expression is not None:
            if any(not isinstance(v, str) for v in expression.content):
                raise ValueError("Timer expression contains unsupported non-text content")
            text = "".join(expression.content).strip()
            if not text:
                raise ValueError("Present timer expression has an empty value")
            values.append([name, timer_value(name, text)])
    if len(values) > 1:
        raise ValueError("Timer definition contains multiple value fields")
    return values


class BPMNInventory:
    """Extract only actions, actual sequence flows, timers, scopes and gateways."""

    def __init__(self, path: Path) -> None:
        """Load using SHIFT's parser and index each local scope.

        :param path: BPMN XML file.
        :return: None.
        """
        probe = path.read_bytes().replace(b"\x00", b"").upper()
        if b"<!DOCTYPE" in probe or b"<!ENTITY" in probe:
            raise ValueError("DTD/entities are not allowed")
        self.definition = BPMNSerializer().parse(str(path), NAMESPACES)
        if len(self.definition.process) != 1:
            raise ValueError("Exactly one process is required")
        self.scopes: List[Tuple[Any, Any, Dict[str, Any], List[Any]]] = []
        self.paths: Dict[str, Any] = {}
        self.ids = {self.definition.process[0].id}
        self._visit(self.definition.process[0], ["process"])
        self.facts = {name: Counter() for name in CATEGORIES + CHECKS}
        self._extract()

    def _visit(self, scope: Any, path: Any) -> None:
        """Index local nodes/flows and derive ID-independent subprocess paths.

        :param scope: Typed process/subprocess.
        :param path: Parent membership path.
        :return: None.
        """
        nodes, flows = {}, []
        for item in children(scope):
            if isinstance(item, (bpmn.TFlowNode, bpmn.SequenceFlow)):
                if not item.id or item.id in self.ids:
                    raise ValueError("Missing or duplicate BPMN element ID: " + str(item.id))
                self.ids.add(item.id)
                if isinstance(item, bpmn.SequenceFlow):
                    flows.append(item)
                else:
                    nodes[item.id] = item
        self.scopes.append((scope, path, nodes, flows))
        for flow in flows:
            if flow.source_ref not in nodes or flow.target_ref not in nodes:
                raise ValueError("Unresolved/cross-scope edge: " + str(flow.id))
        for node in nodes.values():
            if isinstance(node, bpmn.TSubProcess):
                child_path = path + [["event" if node.triggered_by_event else "subprocess",
                                      scope_actions(node)]]
                self.paths[node.id] = child_path
                self._visit(node, child_path)

    def _extract(self) -> None:
        """Build per-category and diagnostic multisets from actual BPMN elements.

        :return: None.
        """
        for scope, path, nodes, flows in self.scopes:
            before, after = defaultdict(list), defaultdict(list)
            for flow in flows:
                before[flow.target_ref].append(flow.source_ref)
                after[flow.source_ref].append(flow.target_ref)

            def nearest(nid: str, backwards: bool = False) -> List[str]:
                """Describe nearby clinical actions for technical-node correspondence.

                :param nid: Local node ID.
                :param backwards: Traverse incoming arcs.
                :return: Sorted action IDs.
                """
                adjacency = before if backwards else after
                pending, seen, actions = list(adjacency[nid]), {nid}, set()
                while pending:
                    current = pending.pop()
                    if current in seen:
                        continue
                    seen.add(current)
                    node = nodes[current]
                    if is_action(node):
                        actions.add(current)
                    elif isinstance(node, bpmn.TSubProcess):
                        actions.update(scope_actions(node))
                    else:
                        pending.extend(adjacency[current])
                return sorted(actions)

            def node_key(nid: str) -> Any:
                """Match technical nodes by kind, scope and adjacent actions.

                :param nid: Local node ID.
                :return: ID-independent endpoint key; clinical action IDs stay exact.
                """
                node = nodes[nid]
                if is_action(node):
                    return ["action", nid]
                if isinstance(node, bpmn.TSubProcess):
                    return ["subprocess", self.paths[nid]]
                kind = node.Meta.name
                context = [kind, path, nearest(nid, True), nearest(nid)]
                if isinstance(node, bpmn.TGateway):
                    role = ("mixed" if len(before[nid]) > 1 and len(after[nid]) > 1 else
                            "diverging" if len(after[nid]) > 1 else
                            "converging" if len(before[nid]) > 1 else "pass")
                    return context + [role, len(before[nid]), len(after[nid])]
                attached = getattr(node, "attached_to_ref", None)
                if attached is not None:
                    attached = str(attached).rsplit("}", 1)[-1]
                    if attached not in nodes or not isinstance(nodes[attached], bpmn.TActivity):
                        raise ValueError("Invalid boundary attachment: " + nid)
                    context += [node_key(attached), bool(node.cancel_activity)]
                if isinstance(node, bpmn.StartEvent):
                    context += [bool(node.is_interrupting)]
                return context + [bool(getattr(node, "timer_event_definition", []))]

            edges = [[node_key(f.source_ref), node_key(f.target_ref)] for f in flows]
            for edge in edges:
                self.facts["edges"][key([path, edge])] += 1
            if isinstance(scope, bpmn.TSubProcess):
                direct_actions = sorted(nid for nid, node in nodes.items() if is_action(node))
                self.facts["subprocesses"][key([path, direct_actions, sorted(edges, key=key)])] += 1
                for aid in scope_actions(scope):
                    self.facts["subprocess_actions"][key([path, aid])] += 1
                for edge in edges:
                    self.facts["subprocess_edges"][key([path, edge])] += 1
            for nid, node in nodes.items():
                description = node_key(nid)
                if is_action(node):
                    self.facts["actions"][key(nid)] += 1
                if isinstance(node, bpmn.TGateway):
                    self.facts["gateways"][key(description)] += 1
                    if len(after[nid]) > 1:
                        self.facts["diverging_gateways"][key(description)] += 1
                    if len(before[nid]) > 1:
                        self.facts["converging_gateways"][key(description)] += 1
                timers = getattr(node, "timer_event_definition", [])
                if len(timers) > 1:
                    raise ValueError("Multiple timer definitions on event: " + nid)
                for timer in timers:
                    value = timer_definition(timer)
                    self.facts["timer_events"][key(description)] += 1
                    self.facts["timer_values"][key([description, value])] += 1
                    self.facts["temporal_constraints"][key([description, value])] += 1


def scores(tp: int, fp: int, fn: int) -> Dict[str, Any]:
    """Calculate micro metrics from counts, retaining undefined denominators.

    :param tp: Matched facts.
    :param fp: Additional facts.
    :param fn: Missing facts.
    :return: Counts and precision/recall/F1.
    """
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": tp/(tp+fp) if tp+fp else None,
            "recall": tp/(tp+fn) if tp+fn else None,
            "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}


def compare(actual: Counter, expected: Counter) -> Dict[str, Any]:
    """Compare presence/content while retaining repeated elements.

    :param actual: Output elements.
    :param expected: Ground-truth elements.
    :return: PRF and explicit missing/additional descriptions.
    """
    return {**scores(sum((actual & expected).values()), sum((actual-expected).values()),
                     sum((expected-actual).values())),
            "missing": [json.loads(v) for v in (expected-actual).elements()],
            "additional": [json.loads(v) for v in (actual-expected).elements()]}


def actions(plan: PlanDefinition) -> List[str]:
    """Collect clinical source linkIds, including nested FHIR actions.

    :param plan: Validated source resource.
    :return: Sorted clinical IDs.
    """
    pending, result = list(plan.action or []), []
    while pending:
        action = pending.pop(0)
        pending[0:0] = list(action.action or [])
        if action.definitionCanonical:
            if not action.linkId or action.linkId in result:
                raise ValueError("Missing/duplicate clinical linkId")
            result.append(action.linkId)
    return sorted(result)


def generate(plan: PlanDefinition, path: Path) -> None:
    """Run the current definition transformation without catalog/database access.

    :param plan: Validated PlanDefinition.
    :param path: Isolated output BPMN.
    :return: None.
    """
    from src.domain.cfg import ControlFlowGraphFactory as Factory
    from src.mappers.bpmn_mapper import BPMNStandardMapper
    graph = Factory.cfg_with_temporal_structures(
        Factory.cfg_with_gateways(Factory.from_plandefinition(plan)))
    path.parent.mkdir(parents=True, exist_ok=True)
    model = BPMNStandardMapper.map(graph)
    path.write_text(BPMNSerializer().serialize(model, NAMESPACES), encoding="utf-8")


def artifact(root: Path, case: str, plan: PlanDefinition) -> Optional[Path]:
    """Find an existing output, refusing ambiguous case files.

    :param root: Artifact directory.
    :param case: Dataset filename stem.
    :param plan: Source ID/version.
    :return: Unique matching file, or None.
    """
    name = str(plan.id) + "_" + str(plan.version) + ".bpmn"
    candidates = [root/name, root/(case+".bpmn"), root/case/"definition.bpmn", root/case/name]
    matches = list(dict.fromkeys(p for p in candidates if p.is_file()))
    if len(matches) > 1:
        raise ValueError("Ambiguous BPMNs: " + ", ".join(map(str, matches)))
    return matches[0] if matches else None


def evaluate(plan_path: Path, config: argparse.Namespace) -> Dict[str, Any]:
    """Run the requested checks for one process.

    :param plan_path: Source FHIR JSON.
    :param config: CLI paths and generation flag.
    :return: Process/category metrics and element-level differences.
    """
    case = plan_path.stem
    try:
        plan = PlanDefinition.model_validate_json(plan_path.read_text(encoding="utf-8"))
        if not plan.id or not plan.version:
            raise ValueError("PlanDefinition.id/version are required")
        clinical_ids = actions(plan)
        reference = BPMNInventory(config.groundtruth/(case+".bpmn"))
        if reference.facts["actions"] != Counter(key(a) for a in clinical_ids):
            raise ValueError("Ground-truth action IDs differ from source linkIds; review correspondence")
        generation_error = None
        if config.generate:
            path = config.output/"artifacts"/case/"definition.bpmn"
            try:
                generate(plan, path)
            except Exception as exc:
                generation_error = str(exc)
        else:
            path = artifact(config.artifacts, case, plan)
        # Missing output counts as missing facts. Existing but unreadable output is an error.
        actual = BPMNInventory(path) if path is not None and path.is_file() else None
        metrics = {category: compare(actual.facts[category] if actual else Counter(),
                                     reference.facts[category]) for category in CATEGORIES}
        checks = {name: compare(actual.facts[name] if actual else Counter(), reference.facts[name])
                  for name in CHECKS}
        total = scores(*(sum(m[c] for m in metrics.values()) for c in ("tp", "fp", "fn")))
        return {"process": case, "status": "generation_error" if generation_error else "evaluated",
                "actual_bpmn": str(path) if path is not None else None,
                "reference_bpmn": str(config.groundtruth/(case+".bpmn")),
                "generation_error": generation_error, "metrics": metrics, "checks": checks, "total": total}
    except Exception as exc:
        return {"process": case, "status": "error", "error": type(exc).__name__+": "+str(exc)}


def write_csv(path: Path, rows: List[Dict[str, Any]], columns: List[str]) -> None:
    """Write a result table.

    :param path: Output CSV.
    :param rows: Result rows.
    :param columns: Ordered column names.
    :return: None.
    """
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Optional[List[str]] = None) -> int:
    """Evaluate local BPMNs and aggregate counts by process and category.

    :param argv: Optional CLI arguments.
    :return: 0 after reporting, 1 for strict differences, 2 for setup errors.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=PROJECT/"evaluation/dataset")
    parser.add_argument("--groundtruth", type=Path, default=PROJECT/"evaluation/groundtruth/definition")
    parser.add_argument("--artifacts", type=Path, default=PROJECT/"data/storage/fs")
    parser.add_argument("--output", type=Path, default=PROJECT/"evaluation/RQ1/results"/
                        "definition")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--fail-on-differences", action="store_true")
    args = parser.parse_args(argv)
    for name in ("dataset", "groundtruth", "artifacts", "output"):
        setattr(args, name, getattr(args, name).resolve())
    try:
        plans = sorted((args.dataset/"plandefinition").glob("*.json"))
        if not plans or not args.groundtruth.is_dir():
            raise ValueError("PlanDefinition dataset or BPMN ground truth is missing")
        for source in (args.dataset, args.groundtruth, args.artifacts):
            if args.output.is_relative_to(source) or source.is_relative_to(args.output):
                raise ValueError("Output must be separate from inputs")
        args.output.mkdir(parents=True, exist_ok=True)
        generated = args.output / "artifacts"
        if generated.is_symlink():
            raise ValueError("Generated artifacts directory must not be a symbolic link")
        if generated.exists():
            shutil.rmtree(generated)
        results = []
        for plan in plans:
            result = evaluate(plan, args)
            results.append(result)
            if "total" in result:
                value = result["total"]
                print(result["process"]+": TP="+str(value["tp"])+", FP="+str(value["fp"])+
                      ", FN="+str(value["fn"])+
                      ", precision="+str(round(value["precision"], 4) if value["precision"] is not None else None)+
                      ", recall="+str(round(value["recall"], 4) if value["recall"] is not None else None)+
                      ", F1="+str(round(value["f1"], 4) if value["f1"] is not None else None)+
                      ("; generation error: "+result["generation_error"] if result.get("generation_error") else ""))
            else:
                print(result["process"]+": ERROR "+result["error"])
        valid = [r for r in results if "metrics" in r]
        category_totals = []
        for category in CATEGORIES + CHECKS:
            field = "metrics" if category in CATEGORIES else "checks"
            count = scores(*(sum(r[field][category][c] for r in valid) for c in ("tp", "fp", "fn")))
            category_totals.append({"category": category, "level": "category" if field == "metrics" else "check",
                                    **count, "evaluated_processes": len(valid),
                                    "error_processes": len(results)-len(valid)})
        metric_rows = [{"process": r["process"], "category": c, "status": r["status"], **r["metrics"][c]}
                       if "metrics" in r else {"process": r["process"], "category": c, "status": "error", "error": r["error"]}
                       for r in results for c in CATEGORIES]
        metric_rows += [{"process": r["process"], "category": c, "status": r["status"], **r["checks"][c]}
                        for r in valid for c in CHECKS]
        process_rows = [{"process": r["process"], "status": r["status"], **r.get("total", {}),
                         "error": r.get("error") or r.get("generation_error")} for r in results]
        measures = ["tp", "fp", "fn", "precision", "recall", "f1"]
        write_csv(args.output/"metrics.csv", metric_rows, ["process", "category", "status"]+measures+["error"])
        write_csv(args.output/"process_metrics.csv", process_rows, ["process", "status"]+measures+["error"])
        write_csv(args.output/"category_metrics.csv", category_totals, ["category", "level"]+measures+
                  ["evaluated_processes", "error_processes"])
        report = {"categories": CATEGORIES, "by_process": process_rows, "by_category": category_totals,
                  "cases": results,
                  "notes": ["Edges are actual local sequenceFlow source/target pairs, not projected action precedence.",
                            "Technical node IDs are matched using node type, scope and nearby action IDs; clinical IDs remain exact.",
                            "Process metrics sum the five category counts. Diagnostic subchecks are also aggregated but never counted twice in process totals.",
                            "Differences are structural agreement results, not proof of behavioural equivalence."]}
        (args.output/"results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
        print("Results: "+str(args.output))
        failure = any("total" not in r or r.get("generation_error") or
                      any(r["metrics"][c]["fp"] or r["metrics"][c]["fn"] for c in CATEGORIES) for r in results)
        return 1 if args.fail_on_differences and failure else 0
    except Exception as exc:
        print("Evaluation setup error: "+str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
