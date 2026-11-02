import copy
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence

from camunda_orchestration_sdk import ConnectedJobContext


WORKER_LOGGER = logging.getLogger("shift.camunda_jobworkers")
INVOCATION_LOGGER = logging.getLogger("shift.camunda_jobworkers.invocations")


def read_action_variables(
    job: ConnectedJobContext, attribute_ids: Sequence[str]
) -> Dict[str, Any]:
    """
    Select only the current action's resource and declared worker attributes.

    :param job: Job whose BPMN element ID corresponds to the action linkId.
    :type job: ConnectedJobContext
    :param attribute_ids: Attribute IDs belonging to the worker ActivityDefinition.
    :type attribute_ids: Sequence[str]
    :return: Independent action inputs; unresolved attribute values remain None.
    :rtype: Dict[str, Any]
    :raises ValueError: If the current action group is absent or not an object.
    """
    WORKER_LOGGER.info(
        "Job activated | worker=%s process=%s instance=%s task=%s job=%s",
        job.type_, job.process_definition_id, job.process_instance_key,
        job.element_id, job.job_key,
    )
    variables = job.variables.to_dict()
    action = variables.get(str(job.element_id))
    if not isinstance(action, dict):
        raise ValueError(f"Missing or invalid variable group for action {job.element_id}")
    return {
        key: copy.deepcopy(action.get(key))
        for key in ("resource", *attribute_ids)
    }


def snomed_code(concept: Any) -> Optional[str]:
    """
    Extract the unique SNOMED CT code from a worker's concept input.

    :param concept: CodeableConcept as JSON text, decoded object or None.
    :type concept: Any
    :return: Single SNOMED CT code, or None when no code is supplied.
    :rtype: Optional[str]
    :raises ValueError: If the concept is malformed or contains multiple SNOMED codes.
    """
    if concept is None or concept == "":
        return None
    if isinstance(concept, str):
        concept = json.loads(concept)
    if not isinstance(concept, dict):
        raise ValueError("Expected a CodeableConcept object")
    codings = concept.get("coding") or []
    if not isinstance(codings, list) or any(not isinstance(item, dict) for item in codings):
        raise ValueError("CodeableConcept.coding must be a list of objects")
    codes = [
        str(coding["code"]) for coding in codings
        if coding.get("code") is not None
        and coding.get("system") in (None, "http://snomed.info/sct")
    ]
    if not codes:
        return None
    code = codes[0]
    if any(other != code for other in codes[1:]):
        raise ValueError("Expected a unique SNOMED CT code")
    return code


def record_invocation(
    job: ConnectedJobContext, activity_definition_id: str,
    result: Optional[Dict[str, Any]] = None,
    inputs: Optional[Dict[str, Any]] = None,
    execution: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Record initial variables and simulated outputs, then return only the outputs.

    Records describe handler invocations, not confirmed job completions.
    Retries produce separate records and can generate new random outputs.

    :param job: Activated Camunda job with its initial process variables.
    :type job: ConnectedJobContext
    :param activity_definition_id: Dataset ActivityDefinition logical ID.
    :type activity_definition_id: str
    :param result: Process-variable updates, or None for an empty update.
    :type result: Optional[Dict[str, Any]]
    :param inputs: Selected variables belonging to the current worker action.
    :type inputs: Optional[Dict[str, Any]]
    :param execution: Initial snapshot and delay metadata captured before waiting.
    :type execution: Optional[Dict[str, Any]]
    :return: Independent output dictionary for automatic SDK job completion.
    :rtype: Dict[str, Any]
    """
    outputs = copy.deepcopy(result) if result is not None else {}
    record = {
        "invoked_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "activity_definition_id": activity_definition_id,
        "job_type": job.type_,
        "job_key": str(job.job_key),
        "process_definition_id": str(job.process_definition_id),
        "process_definition_version": job.process_definition_version,
        "process_instance_key": str(job.process_instance_key),
        "task_id": str(job.element_id),
        "task_instance_key": str(job.element_instance_key),
        "initial_state": copy.deepcopy(job.variables.to_dict()),
        "inputs": copy.deepcopy(inputs) if inputs is not None else {},
        "result": copy.deepcopy(outputs),
    }
    if execution is not None:
        record.update(copy.deepcopy(execution))
    record["result_at"] = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    INVOCATION_LOGGER.info(json.dumps(record, ensure_ascii=False, allow_nan=False))
    WORKER_LOGGER.info(
        "Job result | worker=%s process=%s instance=%s task=%s job=%s result=%s",
        job.type_, job.process_definition_id, job.process_instance_key,
        job.element_id, job.job_key, json.dumps(outputs, ensure_ascii=False, allow_nan=False),
    )
    return outputs
