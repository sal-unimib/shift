#!/usr/bin/env python3
"""Export closed Camunda experiment instances, elements and incidents without changing engine state."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from camunda_orchestration_sdk import CamundaAsyncClient
from camunda_orchestration_sdk.models.cursor_based_forward_pagination import CursorBasedForwardPagination
from camunda_orchestration_sdk.models.element_instance_search_query import ElementInstanceSearchQuery
from camunda_orchestration_sdk.models.element_instance_search_query_filter import ElementInstanceSearchQueryFilter
from camunda_orchestration_sdk.models.incident_search_query import IncidentSearchQuery
from camunda_orchestration_sdk.models.limit_based_pagination import LimitBasedPagination
from camunda_jobworkers.runner import client_configuration


async def pages(search: Callable, identity: str) -> List[Dict[str, Any]]:
    """Read every cursor page, exhausting the cursor when totals are lower bounds.

    :param search: Asynchronous function accepting one SDK pagination object.
    :param identity: Unique result key name.
    :return: Complete list of items, or an exception on inconsistent pagination.
    """
    page: Any = LimitBasedPagination(limit=1000)
    items: Dict[str, Dict[str, Any]] = {}
    cursors = set()
    expected = None
    for _ in range(1000):
        result = (await asyncio.wait_for(search(page), timeout=60)).to_dict()
        metadata = result["page"]
        total = metadata["totalItems"]
        lower_bound = metadata.get("hasMoreTotalItems", False)
        if expected is not None and total != expected:
            raise ValueError("Export changed during pagination; retry after execution is closed")
        expected = total
        for item in result["items"]:
            key = str(item[identity])
            if key in items:
                raise ValueError("Duplicate cursor item in engine export")
            items[key] = item
        if not lower_bound and len(items) == expected:
            return list(items.values())
        if not result["items"] and lower_bound and len(items) >= expected:
            return list(items.values())
        cursor = metadata.get("endCursor")
        if not result["items"] or not cursor or cursor in cursors:
            raise ValueError("Incomplete or repeated cursor page")
        cursors.add(cursor)
        page = CursorBasedForwardPagination(after=cursor, limit=1000)
    raise ValueError("Engine export page limit exceeded")


def normalize(elements: List[Dict[str, Any]], actions: set[str]) -> List[Dict[str, Any]]:
    """Convert element states into correlated activation and outcome events.

    :param elements: Full raw element snapshot for one process instance.
    :param actions: FHIR action linkIds.
    :return: Events with per-element activation ordinals, including cancellations.
    """
    counters: Dict[str, int] = defaultdict(int)
    result = []
    ordered = sorted(elements, key=lambda e: (e["startDate"], int(e["elementInstanceKey"])))
    for item in ordered:
        task = item["elementId"] in actions and item["type"] in {"SERVICE_TASK", "TASK"}
        scope = item["type"] in {"SUB_PROCESS", "EVENT_SUB_PROCESS"}
        if not task and not scope:
            continue
        identifier = item["elementId"]
        counters[identifier] += 1
        common = {"process_instance_key": str(item["processInstanceKey"]),
                  "occurrence": counters[identifier], "task_instance_key": str(item["elementInstanceKey"]),
                  "evidence_source": "Camunda element instance"}
        common["action" if task else "element"] = identifier
        if task:
            result.append({**common, "type": "action.activated", "timestamp": item["startDate"]})
        if item["endDate"] is not None and item["state"] in {"COMPLETED", "TERMINATED"}:
            suffix = "completed" if item["state"] == "COMPLETED" else "cancelled"
            result.append({**common, "type": ("action." if task else "scope.") + suffix,
                           "timestamp": item["endDate"]})
    return result


def action_ids(actions: List[Dict[str, Any]]) -> set[str]:
    """Collect all FHIR action identifiers, including nested actions.

    :param actions: Raw action list.
    :return: Unique linkIds.
    """
    return {a["linkId"] for a in actions} | {
        identifier for a in actions for identifier in action_ids(a.get("action", []))
    }


async def export(args: argparse.Namespace) -> int:
    """Export all selected instances and publish evidence coverage only after success.

    :param args: Input run index and output configuration.
    :return: Zero after a complete export.
    """
    document = json.loads(args.runs.read_text())
    runs = document["runs"]
    output = args.output
    raw = output / "engine_raw"
    raw.mkdir(parents=True, exist_ok=True)
    events, summaries = [], []
    async with CamundaAsyncClient(configuration=client_configuration(),
                                  logger=logging.getLogger("rq2-export")) as client:
        for run in runs:
            key, case = str(run["process_instance_key"]), run["process"]
            instance = (await client.get_process_instance(process_instance_key=key)).to_dict()
            if instance["processDefinitionId"] != case or instance["state"] == "ACTIVE":
                raise ValueError(f"{case}: export requires a matching, closed instance")
            request = json.loads((args.requests / f"{case}.json").read_text())

            async def elements_query(page: Any) -> Any:
                return await client.search_element_instances(data=ElementInstanceSearchQuery(
                    filter_=ElementInstanceSearchQueryFilter(process_instance_key=key), page=page))

            async def incidents_query(page: Any) -> Any:
                return await client.search_process_instance_incidents(
                    process_instance_key=key, data=IncidentSearchQuery(page=page))

            elements = await pages(elements_query, "elementInstanceKey")
            incidents = await pages(incidents_query, "incidentKey")
            (raw / f"{case}_{key}.json").write_text(json.dumps({
                "instance": instance, "elements": elements, "incidents": incidents}, indent=2) + "\n")
            events.extend(normalize(elements, action_ids(request["action"])))
            for incident in incidents:
                events.append({"type": "incident.created", "process_instance_key": key,
                               "timestamp": incident["creationTime"], "element": incident["elementId"],
                               "error_type": incident["errorType"], "error_message": incident["errorMessage"],
                               "incident_key": str(incident["incidentKey"]),
                               "final_state": incident["state"]})
            if instance["endDate"]:
                events.append({"type": "process.completed" if instance["state"] == "COMPLETED" else "process.cancelled",
                               "process_instance_key": key, "timestamp": instance["endDate"],
                               "evidence_source": "Camunda process instance"})
            # Allow secondary-storage indexing to settle before claiming coverage.
            window_end = datetime.fromisoformat(run["observed_until"].replace("Z", "+00:00"))
            if window_end > datetime.now(timezone.utc) - timedelta(seconds=60):
                raise ValueError("Wait at least one minute after the observation window before final export")
            run["started_at"] = instance["startDate"]
            run["engine_observed_from"] = instance["startDate"]
            run["engine_observed_until"] = run["observed_until"]
            summaries.append({"process": case, "process_instance_key": key, "elements": len(elements),
                              "incidents": len(incidents), "state": instance["state"], "complete": True})
            print(f"{case}: {len(elements)} elements, {len(incidents)} incidents", flush=True)
    events.sort(key=lambda e: (e["timestamp"], e["process_instance_key"], e["type"]))
    (output / "engine_events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    (output / "engine_export.json").write_text(json.dumps({"complete": True, "instances": summaries}, indent=2) + "\n")
    (output / "runs.engine.json").write_text(json.dumps(document, indent=2) + "\n")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Export engine evidence without deployment, completion or cancellation commands.

    :param argv: Optional command-line arguments.
    :return: Zero on success, two on failed or incomplete export.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=PROJECT / "evaluation/RQ2/runs.json")
    parser.add_argument("--requests", type=Path, default=PROJECT / "evaluation/dataset/requestorchestration_fast_timing")
    parser.add_argument("--output", type=Path, default=PROJECT / "evaluation/RQ2/results")
    args = parser.parse_args(argv)
    try:
        return asyncio.run(export(args))
    except Exception as error:
        print(f"Engine export incomplete: {type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
