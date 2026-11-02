"""ARES Task/Result HTTP adapter for observation jobs."""
import asyncio
import json
import math
from uuid import uuid4
from functools import lru_cache
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, FiniteFloat, AnyHttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from camunda_orchestration_sdk.models.job_changeset import JobChangeset
from camunda_orchestration_sdk.models.job_update_request import JobUpdateRequest
from camunda_jobworkers.common import WORKER_LOGGER
from camunda_jobworkers.simulation import HEARTBEAT_SECONDS, JOB_TIMEOUT_MS

CODE_CAPABILITIES = {
    '68130003': 'getPhysicalActivity',
    '364075005': 'getHeartRate',
    '258158006': 'getSleepParameters',
    '75367002': 'getBloodPressure',
    '27113001': 'getBodyWeight',
}

class AresSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='WORKERS_ARES_',
        env_file=Path(__file__).resolve().parent.parent / '.env', extra='ignore')
    url: AnyHttpUrl = 'http://127.0.0.1:8001/tasks'
    timeout_seconds: float = Field(default=30, gt=0)
    required_kpi: dict[str, dict[str, FiniteFloat]] = Field(default_factory=lambda: {
        'latency': {'max': 2.}, 'reliability': {'min': .90}, 'data_freshness': {'max': 25.}})

@lru_cache(maxsize=1)
def get_ares_settings():
    return AresSettings()

class Reading(BaseModel):
    value: Any
    timestamp: AwareDatetime

class Result(BaseModel):
    value: Reading
    qos: dict[str, FiniteFloat]

class BloodPressure(BaseModel):
    model_config = ConfigDict(extra='forbid')
    systolic: float = Field(gt=0, allow_inf_nan=False, strict=True)
    diastolic: float = Field(gt=0, allow_inf_nan=False, strict=True)

class SleepStages(BaseModel):
    model_config = ConfigDict(extra='forbid')
    deep: float = Field(ge=0, allow_inf_nan=False, strict=True)
    light: float = Field(ge=0, allow_inf_nan=False, strict=True)
    rem: float = Field(ge=0, allow_inf_nan=False, strict=True)
    wake: float = Field(ge=0, allow_inf_nan=False, strict=True)

class SleepParameters(BaseModel):
    model_config = ConfigDict(extra='forbid')
    duration: float = Field(ge=0, allow_inf_nan=False, strict=True)
    end_timestamp: AwareDatetime
    quality: float = Field(ge=0, le=1, allow_inf_nan=False, strict=True)
    stages: SleepStages

    @model_validator(mode='after')
    def stage_duration_matches_total(self):
        if not math.isclose(sum(self.stages.model_dump().values()), self.duration, rel_tol=1e-6, abs_tol=1e-6):
            raise ValueError('Sleep stage durations must add up to duration')
        return self


def process_variables(code: str, result: Result) -> Dict[str, Any]:
    value = result.value.value
    if code == '68130003':
        if value not in ('HIGH', 'MEDIUM', 'LOW'):
            raise ValueError('PhysicalActivity must be HIGH, MEDIUM or LOW')
        return {'physical_activity_result': value}
    if code in ('364075005', '27113001'):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('HeartRate and BodyWeight must be finite numbers')
        return {'heart_rate' if code == '364075005' else 'body_weight': float(value)}
    if code == '258158006':
        return {'sleep_parameters': SleepParameters.model_validate(value).model_dump(mode='json')}
    if code == '75367002':
        return BloodPressure.model_validate(value).model_dump()
    raise ValueError(f'Unsupported ARES observation code: {code}')


async def request_observation(job, code: str, *,
    on_result: Callable[[Result, str], Awaitable[None]] | None = None) -> Dict[str, Any]:
    config = get_ares_settings()
    task = {'capability': CODE_CAPABILITIES[code], 'requiredKpi': config.required_kpi}
    request_id = str(uuid4())
    WORKER_LOGGER.info('ARES Task | request_id=%s instance=%s task=%s job=%s payload=%s',
        request_id, job.process_instance_key, job.element_id, job.job_key,
        json.dumps(task, ensure_ascii=False, allow_nan=False))
    # Extend the lease before I/O, then renew it while queued or provisioning.
    await job.client.update_job(job_key=job.job_key,
        data=JobUpdateRequest(changeset=JobChangeset(timeout=JOB_TIMEOUT_MS)))
    async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
        async def acquire() -> Dict[str, Any]:
            response = await client.post(str(config.url), json=task, headers={'X-Request-ID': request_id})
            response.raise_for_status()
            raw = response.json()
            WORKER_LOGGER.info('ARES Result | request_id=%s instance=%s task=%s job=%s capability=%s result=%s',
                request_id, job.process_instance_key, job.element_id, job.job_key, task['capability'],
                json.dumps(raw, ensure_ascii=False, allow_nan=False))
            result = Result.model_validate(raw)
            outputs = process_variables(code, result)
            if on_result is not None:
                await on_result(result, request_id)
            return outputs

        # Keep renewing the lease throughout acquisition AND FHIR publication.
        pending = asyncio.create_task(acquire())
        try:
            while not pending.done():
                done, _ = await asyncio.wait({pending}, timeout=HEARTBEAT_SECONDS)
                if not done:
                    await job.client.update_job(job_key=job.job_key,
                        data=JobUpdateRequest(changeset=JobChangeset(timeout=JOB_TIMEOUT_MS)))
            return await pending
        except Exception:
            WORKER_LOGGER.exception('Observation acquisition/publication failed | request_id=%s instance=%s task=%s job=%s capability=%s',
                request_id, job.process_instance_key, job.element_id, job.job_key, task['capability'])
            raise
        finally:
            if not pending.done():
                pending.cancel()
                try:
                    await pending
                except asyncio.CancelledError:
                    pass
