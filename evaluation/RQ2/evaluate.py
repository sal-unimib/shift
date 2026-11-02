#!/usr/bin/env python3
"""Compare virtual RQ2 expectations with worker traces and optional engine evidence."""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from simulate import PROJECT, correlate_records, instant, read_records, run_records, seconds


def scores(tp: int, fp: int, fn: int) -> Dict[str, Any]:
    """Compute micro counts; undefined denominators remain null.

    :param tp: Correct observed facts.
    :param fp: Additional/incorrect observed facts.
    :param fn: Missing expected facts.
    :return: Counts, precision, recall and F1.
    """
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}


def canonical(value: Any) -> Any:
    """Normalize JSON-encoded action parameters for semantic comparison.

    :param value: Raw process-variable value.
    :return: Decoded JSON where applicable, otherwise the original value.
    """
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            pass
    return value


def temporal_inputs(values: Dict[str, Any], action: str) -> Dict[str, Any]:
    """Resolve action-specific temporal values independently of shared binding names.

    :param values: Flat process variables.
    :param action: Action linkId.
    :return: Category-to-value mapping, including duration/count variables.
    """
    result = {}
    for name, value in values.items():
        match = re.fullmatch(
            r"TC_(.+)_(cycle|exact|offset|execution_duration|execution_iteration|execution_bound|keep_alive_bound)", name
        )
        if match and action in match[1].split("+"):
            if isinstance(value, str) and value.startswith("P"):
                value = seconds(value)
            elif isinstance(value, str) and value.startswith("R"):
                parts = value.split("/")
                if len(parts) == 2:
                    value = [parts[0], seconds(parts[1])]
            elif isinstance(value, str) and re.match(r"\d{4}-", value):
                value = instant(value).timestamp()
            if match[2] in result and result[match[2]] != value:
                raise ValueError(f"Conflicting temporal bindings for {action}")
            result[match[2]] = value
    return result


def evaluate_run(expected: Dict[str, Any], records: List[Dict[str, Any]],
                 engine: List[Dict[str, Any]], tolerance: float) -> Dict[str, Any]:
    """Compare one observation window without inventing missing engine evidence.

    :param expected: Virtual simulation report.
    :param records: Raw worker invocation records.
    :param engine: Optional normalized engine-event export.
    :param tolerance: Allowed scheduling lateness in real seconds.
    :return: Per-category metrics, explicit checks and evidence limitations.
    """
    run = expected["run"]
    start, end = instant(run["started_at"]), instant(run["observed_until"])
    if "error" in expected:
        return {"run": run, "error": expected["error"]}
    selected = run_records(records, run)
    instance_events = [e for e in engine
                       if str(e["process_instance_key"]) == str(run["process_instance_key"])
                       and start <= instant(e["timestamp"]) <= end]
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in selected:
        grouped[record["task_id"]].append(record)
    if len({r["job_key"] for r in selected}) != len(selected):
        return {"run": run, "error": "Repeated job deliveries require explicit accepted-outcome selection"}
    observed = {f"{action}#{record.get('occurrence', index)}": record for action, rows in grouped.items()
                for index, record in enumerate(rows, 1)}
    # Worker records are emitted after result production. Engine activations
    # also cover tasks still running/cancelled before producing such a record.
    engine_activations = {}
    for event in instance_events:
        if event["type"] == "action.activated":
            if "occurrence" not in event:
                raise ValueError("Engine activations require per-action activation occurrence")
            key = f"{event['action']}#{event['occurrence']}"
            if key in engine_activations:
                raise ValueError(f"Duplicate engine activation: {key}")
            engine_activations[key] = event
    if engine_activations:
        for key, event in engine_activations.items():
            observed.setdefault(key, {})
            observed[key] = {**observed[key], "invoked_at": event["timestamp"], "engine_activation": True}
    worker_keys = {key for key, record in observed.items() if record.get("job_key") is not None}
    worker_max: Dict[str, int] = defaultdict(int)
    for key in worker_keys:
        action, ordinal = key.rsplit("#", 1)
        worker_max[action] = max(worker_max[action], int(ordinal))
    # A task cancelled before worker dispatch creates an internal hole in the
    # activation tape. Without parent-scope correlation, later ordinals cannot
    # prove timing or precedence failures (notably nested cycles in P13).
    ambiguous_actions = {
        event["action"] for event in instance_events
        if event["type"] == "action.cancelled"
        and f"{event['action']}#{event['occurrence']}" not in worker_keys
        and event["occurrence"] < worker_max[event["action"]]
    }
    activations = {f"{e['action']}#{e['occurrence']}": e for e in expected["events"]
                   if e["type"] == "action.activated"}
    outcomes = {f"{e['action']}#{e['occurrence']}": e for e in expected["events"]
                if e["type"] in {"action.completed", "action.cancelled"}}
    common = activations.keys() & observed.keys()
    missing = sorted(activations.keys() - observed.keys())
    extra = sorted(observed.keys() - activations.keys())
    # A blocked expected continuation cannot prove that later observed actions
    # are extra. Missing already-predicted activations remain genuine FNs.
    unknown_extra = extra if expected["unresolved"] else []
    extra = [] if unknown_extra else extra
    metrics = {"actions": scores(len(common), len(extra), len(missing))}
    checks: List[Dict[str, Any]] = []
    for key in missing:
        checks.append({"category": "actions", "item": key, "status": "missing"})
    for key in extra:
        checks.append({"category": "actions", "item": key, "status": "additional"})
    for key in unknown_extra:
        checks.append({"category": "actions", "item": key, "status": "unavailable",
                       "reason": "Expected continuation is blocked by missing outcomes/state"})
    parameter_counts = [0, 0, 0]
    binding_counts = [0, 0, 0]
    configuration_counts = [0, 0, 0]
    unavailable_configuration = 0
    unavailable_parameters = 0
    for key in sorted(common):
        event, record = activations[key], observed[key]
        if "initial_state" in record:
            wanted_configuration = temporal_inputs(expected.get("initial_variables", {}), event["action"])
            actual_configuration = temporal_inputs(record["initial_state"], event["action"])
            wanted_configuration["subject"] = expected.get("initial_variables", {}).get("subject")
            actual_configuration["subject"] = record["initial_state"].get("subject")
            for name in sorted(wanted_configuration.keys() | actual_configuration.keys()):
                wanted, actual = wanted_configuration.get(name), actual_configuration.get(name)
                correct = wanted == actual
                configuration_counts[0] += int(correct)
                configuration_counts[1] += int(not correct)
                configuration_counts[2] += int(not correct)
                checks.append({"category": "configuration_variables", "item": f"{key}.{name}",
                               "status": "passed" if correct else "failed", "expected": wanted, "observed": actual})
        else:
            unavailable_configuration += 1
        actual_inputs = record.get("inputs")
        if "job_type" in record and "job_type" in event:
            correct_binding = (record["job_type"] == event["job_type"]
                               and str(record.get("activity_definition_id")) == event["activity_definition_id"])
            binding_counts[0] += int(correct_binding)
            binding_counts[1] += int(not correct_binding)
            binding_counts[2] += int(not correct_binding)
            checks.append({"category": "worker_bindings", "item": key,
                           "status": "passed" if correct_binding else "failed",
                           "expected": event["job_type"], "observed": record["job_type"]})
        if actual_inputs is None:
            unavailable_parameters += 1
            checks.append({"category": "parameters", "item": key, "status": "unavailable",
                           "reason": "No worker input snapshot for this activated task"})
        for name in sorted(event["inputs"].keys() | actual_inputs.keys()) if actual_inputs is not None else []:
            wanted, actual = event["inputs"].get(name), actual_inputs.get(name)
            correct = canonical(wanted) == canonical(actual)
            if correct:
                parameter_counts[0] += 1
            else:
                parameter_counts[1] += 1
                parameter_counts[2] += 1
            checks.append({"category": "parameters", "item": f"{key}.{name}",
                           "status": "passed" if correct else "failed", "expected": wanted, "observed": actual})
        elapsed = (instant(record["invoked_at"]) - start).total_seconds()
        deviation = elapsed - event["time"]
        checks.append({"category": "activation_timing", "item": key,
                       "status": "unavailable" if event["action"] in ambiguous_actions else
                       "passed" if -tolerance <= deviation <= tolerance else "failed",
                       "expected_seconds": event["time"], "observed_seconds": elapsed,
                       "deviation_seconds": deviation,
                       "reason": "Internal pre-worker cancellation requires scope-level occurrence matching"
                       if event["action"] in ambiguous_actions else None,
                       "evidence": "engine_activation" if record.get("engine_activation") else "worker_invocation_proxy"})
    metrics["parameters"] = scores(*parameter_counts)
    metrics["parameters"]["unavailable"] = unavailable_parameters
    metrics["worker_bindings"] = scores(*binding_counts)
    metrics["configuration_variables"] = {**scores(*configuration_counts), "unavailable": unavailable_configuration}
    engine_actions: Dict[str, Dict[str, Any]] = {}
    engine_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for event in instance_events:
        if event["type"] in {"action.completed", "action.cancelled"}:
            engine_groups[event["action"]].append(event)
    for action, rows in engine_groups.items():
        # Prefer explicit occurrence/correlation supplied by the export adapter.
        for event in sorted(rows, key=lambda e: instant(e["timestamp"])):
            if "occurrence" not in event:
                raise ValueError("Engine action outcomes require occurrence mapped by activation order")
            key = f"{action}#{event['occurrence']}"
            if key in engine_actions:
                raise ValueError(f"Duplicate/conflicting engine outcome: {key}")
            engine_actions[key] = event
    full_engine_window = (run.get("engine_observed_from") is not None
                          and run.get("engine_observed_until") is not None
                          and instant(run["engine_observed_from"]) <= start
                          and instant(run["engine_observed_until"]) >= end)
    incidents = [e for e in instance_events if e["type"] == "incident.created"]
    incident_known = bool(incidents) or full_engine_window
    metrics["incidents"] = {
        "passed": int(full_engine_window and not incidents),
        "failed": int(bool(incidents)), "unavailable": int(not incident_known),
        "pass_rate": float(not incidents) if incident_known else None,
        "incident_count": len(incidents) if incident_known else None,
    }
    for event in incidents:
        checks.append({"category": "incidents", "item": event["incident_key"],
                       "status": "failed", "element": event["element"],
                       "error_type": event["error_type"], "error_message": event["error_message"],
                       "final_state": event.get("final_state")})
    for key, activation in activations.items():
        for cause in activation.get("causes", []):
            if activation["action"] in ambiguous_actions or cause.rsplit("#", 1)[0] in ambiguous_actions:
                checks.append({"category": "precedence", "item": f"{cause}->{key}", "status": "unavailable",
                               "reason": "Internal cancellation makes flat occurrence matching ambiguous"})
                continue
            if key not in observed or cause not in observed:
                checks.append({"category": "precedence", "item": f"{cause}->{key}", "status": "unavailable"})
                continue
            evidence = engine_actions.get(cause)
            before = evidence["timestamp"] if evidence else observed[cause].get("result_at")
            if before is None:
                checks.append({"category": "precedence", "item": f"{cause}->{key}", "status": "unavailable"})
                continue
            passed = instant(before) <= instant(observed[key]["invoked_at"])
            checks.append({"category": "precedence", "item": f"{cause}->{key}",
                           "status": "passed" if passed else "failed",
                           "evidence": "engine_outcome" if evidence else "worker_result_proxy"})
    if full_engine_window:
        correct = sum(key in engine_actions and engine_actions[key]["type"] == value["type"]
                      for key, value in outcomes.items())
        false_positive = sum(key not in outcomes or outcomes[key]["type"] != value["type"]
                             for key, value in engine_actions.items())
        if expected["unresolved"]:
            false_positive = sum(key in outcomes and outcomes[key]["type"] != value["type"]
                                 for key, value in engine_actions.items())
        metrics["execution_outcomes"] = scores(correct, false_positive, len(outcomes) - correct)
    else:
        checks.append({"category": "execution_outcomes", "item": "engine_window", "status": "unavailable",
                       "reason": "Complete engine export coverage is not declared"})
    # Scope completion is separate from whole-process termination: an event
    # subprocess iteration may be expected to end while Keep Alive stays active.
    scope_expected = {(e["element"], e["occurrence"]): e for e in expected["events"]
                      if e["type"] == "scope.completed"}
    scope_observed = {(e["element"], e["occurrence"]): e for e in instance_events
                      if e["type"] == "scope.completed"}
    if full_engine_window:
        scope_tp, scope_fp, scope_fn = 0, 0, 0
        for key, event in scope_expected.items():
            actual = scope_observed.get(key)
            if actual:
                scope_tp += 1
                deviation = (instant(actual["timestamp"]) - start).total_seconds() - event["time"]
                checks.append({"category": "scope_timing", "item": str(key),
                               "status": "unavailable" if ambiguous_actions else
                               "passed" if abs(deviation) <= tolerance else "failed",
                               "deviation_seconds": deviation})
            elif event["time"] + tolerance <= expected["horizon_seconds"]:
                scope_fn += 1
                checks.append({"category": "scope_completion", "item": str(key), "status": "missing"})
        if not expected["unresolved"]:
            scope_fp = len(scope_observed.keys() - scope_expected.keys())
        metrics["scope_completion"] = scores(scope_tp, scope_fp, scope_fn)
    else:
        checks.append({"category": "scope_completion", "item": "engine_window", "status": "unavailable"})
    completion = next((e for e in expected["events"] if e["type"] == "process.completed"), None)
    actual_completion = next((e for e in instance_events if e["type"] == "process.completed"), None)
    status = run.get("observed_status")
    if completion is not None:
        deadline = completion["time"] + tolerance
        if actual_completion:
            elapsed = (instant(actual_completion["timestamp"]) - start).total_seconds()
            checks.append({"category": "termination", "item": "process", "status": "passed" if
                           abs(elapsed - completion["time"]) <= tolerance else "failed",
                           "expected_seconds": completion["time"], "observed_seconds": elapsed})
        elif expected["horizon_seconds"] >= deadline and (full_engine_window or status in {"ACTIVE", "INCIDENT", "CANCELLED"}):
            checks.append({"category": "termination", "item": "process", "status": "failed",
                           "reason": "Expected completion was not observed before the deadline"})
        else:
            checks.append({"category": "termination", "item": "process", "status": "unavailable",
                           "reason": "Missing completion timestamp/full engine coverage or insufficient grace window"})
    elif expected["unresolved"]:
        checks.append({"category": "termination", "item": "process", "status": "unavailable",
                       "reason": "Expected continuation needs missing worker outcomes/state"})
    elif actual_completion:
        checks.append({"category": "termination", "item": "process", "status": "failed",
                       "reason": "Observed completion while expected execution is still active"})
    else:
        checks.append({"category": "termination", "item": "process",
                       "status": "failed" if status in {"INCIDENT", "CANCELLED"} else
                       "passed" if full_engine_window or status == "ACTIVE" else "unavailable",
                       "reason": "Expected active at the observation horizon"})
    for category in {c["category"] for c in checks} - {
        "actions", "parameters", "worker_bindings", "configuration_variables", "execution_outcomes", "scope_completion", "incidents"
    }:
        rows = [c for c in checks if c["category"] == category]
        passed, failed = sum(c["status"] == "passed" for c in rows), sum(c["status"] == "failed" for c in rows)
        metrics[category] = {"passed": passed, "failed": failed,
                             "unavailable": sum(c["status"] == "unavailable" for c in rows),
                             "pass_rate": passed / (passed + failed) if passed + failed else None}
    return {"run": run, "metrics": metrics, "checks": checks,
            "unresolved": expected["unresolved"], "unclassified_observed_actions": unknown_extra,
            "ambiguous_occurrence_actions": sorted(ambiguous_actions),
            "activation_evidence": "engine_and_worker_records" if engine_activations else "worker_invocation_proxy_only",
            "matching": "per-action activation ordinal; worker timestamps include dispatch/network latency"}


def write_csv(path: Path, rows: List[Dict[str, Any]], fields: List[str]) -> None:
    """Overwrite a report with a stable header, including empty results.

    :param path: Output CSV.
    :param rows: Report rows.
    :param fields: Ordered column names.
    """
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Optional[List[str]] = None) -> int:
    """Evaluate stored virtual traces without executing workflows or regenerating truth.

    :param argv: Optional command-line arguments.
    :return: Zero after reporting, two for invalid input or failed simulations.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=Path, default=PROJECT / "evaluation/RQ2/results/expected.json")
    parser.add_argument("--invocations", type=Path, default=PROJECT / "camunda_jobworkers/data/invocations.jsonl")
    parser.add_argument("--engine-events", type=Path)
    parser.add_argument("--tolerance-seconds", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=PROJECT / "evaluation/RQ2/results")
    args = parser.parse_args(argv)
    if args.tolerance_seconds < 0:
        parser.error("Tolerance must be non-negative")
    engine = read_records(args.engine_events) if args.engine_events else []
    records = correlate_records(read_records(args.invocations), engine)
    reports = []
    for expected in json.loads(args.expected.read_text())["runs"]:
        try:
            reports.append(evaluate_run(expected, records, engine, args.tolerance_seconds))
        except Exception as error:
            reports.append({"run": expected["run"], "error": f"{type(error).__name__}: {error}"})
    args.output.mkdir(parents=True, exist_ok=True)
    metric_rows, check_rows = [], []
    for report in reports:
        identity = {"run": report["run"]["id"], "process": report["run"]["process"],
                    "process_instance_key": report["run"]["process_instance_key"]}
        for category, values in report.get("metrics", {}).items():
            metric_rows.append({**identity, "category": category, **values})
        for check in report.get("checks", []):
            check_rows.append({**identity, **check, "details": json.dumps(check, ensure_ascii=False)})
    fields = ["tp", "fp", "fn", "precision", "recall", "f1", "passed", "failed", "unavailable", "pass_rate", "incident_count"]
    write_csv(args.output / "process_metrics.csv", metric_rows,
              ["run", "process", "process_instance_key", "category"] + fields)
    category_rows = []
    for category in sorted({row["category"] for row in metric_rows}):
        rows = [r for r in metric_rows if r["category"] == category]
        if "tp" in rows[0]:
            values = scores(*(sum(r[k] for r in rows) for k in ("tp", "fp", "fn")))
            values["unavailable"] = sum(r.get("unavailable", 0) for r in rows)
        else:
            passed, failed, unavailable = (sum(r[k] for r in rows) for k in ("passed", "failed", "unavailable"))
            values = {"passed": passed, "failed": failed, "unavailable": unavailable,
                      "pass_rate": passed / (passed + failed) if passed + failed else None}
            if category == "incidents":
                values["incident_count"] = sum(r.get("incident_count") or 0 for r in rows)
        category_rows.append({"category": category, "evaluated_runs": len(rows), **values})
    write_csv(args.output / "category_metrics.csv", category_rows, ["category", "evaluated_runs"] + fields)
    write_csv(args.output / "checks.csv", check_rows,
              ["run", "process", "process_instance_key", "category", "item", "status", "details"])
    write_csv(args.output / "errors.csv", [
        {"run": r["run"]["id"], "process": r["run"]["process"], "error": r["error"]}
        for r in reports if "error" in r
    ], ["run", "process", "error"])
    (args.output / "results.json").write_text(json.dumps({"tolerance_seconds": args.tolerance_seconds,
                                                         "runs": reports}, indent=2, ensure_ascii=False) + "\n")
    for report in reports:
        print(report["run"]["id"], report.get("error") or json.dumps(report["metrics"]))
    return 2 if any("error" in r for r in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
