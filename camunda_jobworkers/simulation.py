import asyncio
import copy
import math
import random
import re
from calendar import monthrange
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from camunda_orchestration_sdk import ConnectedJobContext
from camunda_orchestration_sdk.models.job_changeset import JobChangeset
from camunda_orchestration_sdk.models.job_update_request import JobUpdateRequest

from camunda_jobworkers.common import WORKER_LOGGER


# Clinical defaults are expressed in seconds and compressed only when selected.
TIME_COMPRESSION_FACTOR = 600.0
# Original dataset durations use minutes: ±2 minutes become ±0.2 seconds.
DURATION_TOLERANCE_SECONDS = 120.0 / TIME_COMPRESSION_FACTOR
DEFAULT_DELAY_RANGES: Dict[str, Tuple[float, float]] = {
    "1051": (0.0, 0.0),
    "1052": (600.0, 1800.0),
    "1053": (780.0, 1020.0),
    "1002": (120.0, 300.0),
    "1054": (0.0, 0.0),
    "1055": (0.0, 0.0),
    "1001": (1680.0, 1920.0),
    "1056": (780.0, 1020.0),
    "1057": (1680.0, 1920.0),
    "1058": (0.0, 10.0),
    "1059": (1680.0, 1920.0),
    "1000": (0.0, 0.0),
}
DURATION_PATTERN = re.compile(
    r"P(?:(?P<years>\d+(?:\.\d+)?)Y)?"
    r"(?:(?P<months>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<weeks>\d+(?:\.\d+)?)W)?"
    r"(?:(?P<days>\d+(?:\.\d+)?)D)?"
    r"(?:T(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?"
)
HEARTBEAT_SECONDS = 15.0
JOB_TIMEOUT_MS = 60000


def _calendar_seconds(anchor: datetime, months: int) -> float:
    """
    Convert calendar months relative to the invocation date.

    :param anchor: UTC invocation time.
    :type anchor: datetime
    :param months: Number of whole calendar months.
    :type months: int
    :return: Elapsed seconds after clamping to the target month's final day.
    :rtype: float
    """
    month_index = anchor.year * 12 + anchor.month - 1 + months
    year, month = divmod(month_index, 12)
    month += 1
    target = anchor.replace(
        year=year, month=month,
        day=min(anchor.day, monthrange(year, month)[1]),
    )
    return (target - anchor).total_seconds()


def duration_seconds(value: str, anchor: datetime) -> Tuple[float, float]:
    """
    Parse an ISO duration and identify the unit used for random tolerance.

    :param value: Non-negative ISO duration supplied by the instance mapper.
    :type value: str
    :param anchor: Invocation time for calendar month/year conversion.
    :type anchor: datetime
    :return: Nominal seconds and seconds per smallest explicitly supplied unit.
    :rtype: Tuple[float, float]
    :raises ValueError: If the duration is invalid or uses fractional months/years.
    """
    match = DURATION_PATTERN.fullmatch(value) if isinstance(value, str) else None
    if match is None or not any(item is not None for item in match.groupdict().values()) or value.endswith("T"):
        raise ValueError(f"Invalid execution duration: {value!r}")
    parts = {name: float(number) for name, number in match.groupdict().items() if number is not None}
    if any(not math.isfinite(number) for number in parts.values()):
        raise ValueError("Execution duration must be finite")
    years, months = parts.get("years", 0.0), parts.get("months", 0.0)
    if not years.is_integer() or not months.is_integer():
        raise ValueError("Fractional calendar months/years are not supported")
    factors = {
        "years": _calendar_seconds(anchor, 12),
        "months": _calendar_seconds(anchor, 1),
        "weeks": 604800.0, "days": 86400.0, "hours": 3600.0,
        "minutes": 60.0, "seconds": 1.0,
    }
    total = _calendar_seconds(anchor, int(years * 12 + months))
    total += sum(parts.get(unit, 0.0) * factors[unit] for unit in ("weeks", "days", "hours", "minutes", "seconds"))
    unit = next(unit for unit in reversed(factors) if unit in parts)
    return total, factors[unit]


def choose_delay(
    variables: Dict[str, Any], action_id: str,
    activity_definition_id: str, anchor: datetime,
) -> Tuple[float, str]:
    """
    Select a compressed table delay or an already compressed execution duration.

    Explicit durations come from requestorchestration_fast_timing and are not
    divided again. Their tolerance is ±0.2 seconds (two clinical minutes).

    :param variables: Process variables at activation.
    :type variables: Dict[str, Any]
    :param action_id: Current action linkId.
    :type action_id: str
    :param activity_definition_id: Worker ActivityDefinition ID.
    :type activity_definition_id: str
    :param anchor: UTC invocation time.
    :type anchor: datetime
    :return: Non-negative delay in seconds and its source variable/table marker.
    :rtype: Tuple[float, str]
    """
    name = f"TC_{action_id}_execution_duration"
    value = variables.get(name)
    if value is not None and value != "":
        nominal, _ = duration_seconds(value, anchor)
        if nominal == 0:
            return 0.0, name
        return random.uniform(
            max(0.0, nominal - DURATION_TOLERANCE_SECONDS),
            nominal + DURATION_TOLERANCE_SECONDS,
        ), name
    low, high = DEFAULT_DELAY_RANGES[activity_definition_id]
    return (random.uniform(low, high) / TIME_COMPRESSION_FACTOR if high else 0.0), "estimated"


async def simulate_execution(
    job: ConnectedJobContext, activity_definition_id: str
) -> Dict[str, Any]:
    """
    Wait asynchronously before producing results, renewing the active job timeout.

    :param job: Activated job with a connected asynchronous Camunda client.
    :type job: ConnectedJobContext
    :param activity_definition_id: Worker ActivityDefinition ID.
    :type activity_definition_id: str
    :return: Invocation snapshot and planned delay metadata for the JSONL record.
    :rtype: Dict[str, Any]
    """
    started = datetime.now(timezone.utc)
    initial_state = copy.deepcopy(job.variables.to_dict())
    seconds, source = choose_delay(initial_state, str(job.element_id), activity_definition_id, started)
    WORKER_LOGGER.info(
        "Job delay | worker=%s process=%s instance=%s task=%s job=%s seconds=%.3f source=%s",
        job.type_, job.process_definition_id, job.process_instance_key,
        job.element_id, job.job_key, seconds, source,
    )
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while seconds > 0:
        # Each update resets the activation timeout from the current time.
        # Failure propagates so the SDK fails the job instead of completing late.
        await job.client.update_job(
            job_key=job.job_key,
            data=JobUpdateRequest(changeset=JobChangeset(timeout=JOB_TIMEOUT_MS)),
        )
        remaining = deadline - loop.time()
        if remaining <= 0:
            break
        await asyncio.sleep(min(remaining, HEARTBEAT_SECONDS))
        if loop.time() >= deadline:
            break
    return {
        "invoked_at": started.isoformat(timespec="microseconds"),
        "initial_state": initial_state,
        "delay_seconds": seconds,
        "delay_source": source,
    }
