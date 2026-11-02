#!/usr/bin/env python3
"""Align reference variable JSON files to reviewed BPMN forms without rebuilding BPMNs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from instance_level import (
    PROJECT, PlanDefinition, RequestOrchestration,
    enriched_inventory, load_catalog, reference_variables,
)


def main(argv: Optional[List[str]] = None) -> int:
    """
    Align variables against reviewed forms and current FHIR sources.

    :param argv: Optional command-line arguments.
    :type argv: Optional[List[str]]
    :return: Zero on success, one for check-only differences, two on invalid input.
    :rtype: int
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=PROJECT / "evaluation/dataset")
    parser.add_argument("--groundtruth", type=Path, default=PROJECT / "evaluation/groundtruth/instance_camunda")
    parser.add_argument("--check", action="store_true", help="Check consistency without changing any file.")
    args = parser.parse_args(argv)
    try:
        catalog = load_catalog(json.loads((args.groundtruth / "catalog.json").read_text()))
        plans = {}
        for path in (args.dataset / "plandefinition").glob("*.json"):
            plan = PlanDefinition.model_validate_json(path.read_text())
            plans[(plan.id, plan.version)] = plan
        requests = sorted((args.dataset / "requestorchestration").glob("*.json"))
        if not requests:
            raise ValueError("RequestOrchestration dataset is empty")
        pending = []
        for path in requests:
            request = RequestOrchestration.model_validate_json(path.read_text())
            plan_id, version = request.instantiatesCanonical[0].rsplit("/", 1)[-1].split("|")
            inventory, _, _ = enriched_inventory(args.groundtruth / (path.stem + ".bpmn"))
            values = reference_variables(plans[(plan_id, version)], request, inventory, catalog)
            target = args.groundtruth / (path.stem + ".variables.json")
            before = json.loads(target.read_text()) if target.is_file() else None
            if before != values:
                pending.append((target, values))
                print(path.stem + ": variable values need updating")
        # Validate every case before applying any updates.
        if not args.check:
            for target, values in pending:
                target.write_text(json.dumps(values, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Checked {len(requests)} cases; {'different' if args.check else 'updated'} variable files: {len(pending)}. BPMNs unchanged.")
        return 1 if args.check and pending else 0
    except Exception as error:
        print(f"Reference variable alignment failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
