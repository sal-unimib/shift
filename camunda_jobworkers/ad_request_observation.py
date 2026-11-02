import json
import random
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx
from fhir.resources.observation import Observation
from pydantic import AliasChoices, AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Any, Dict

from camunda_orchestration_sdk import ConnectedJobContext

from camunda_jobworkers.simulation import simulate_execution
from camunda_jobworkers.ares_client import CODE_CAPABILITIES, Result, process_variables, request_observation

from camunda_jobworkers.common import WORKER_LOGGER, read_action_variables, record_invocation, snomed_code


ACTIVITY_DEFINITION_ID = '1058'
JOB_TYPE = 'ad_request_observation'
ATTRIBUTE_IDS = ('1058_observation_concept',)


class FhirSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / '.env', extra='ignore')
    base_url: AnyHttpUrl = Field(default='http://localhost:8080/fhir',
        validation_alias=AliasChoices('WORKERS_FHIR_BASE_URL', 'FHIR_BASE_URL'))
    api_key: SecretStr = Field(default='',
        validation_alias=AliasChoices('WORKERS_FHIR_API_KEY', 'FHIR_API_KEY'))
    timeout_seconds: float = Field(default=30, gt=0, validation_alias='WORKERS_FHIR_TIMEOUT_SECONDS')


@lru_cache(maxsize=1)
def get_fhir_settings() -> FhirSettings:
    return FhirSettings()


def build_observation(job, code: str, result: Result, request_id: str) -> Observation:
    """Build a base FHIR R5 Observation; do not claim a specific clinical profile."""
    values = process_variables(code, result)
    variables = job.variables.to_dict()
    subject = variables.get('subject')
    if isinstance(subject, dict):
        subject = subject.get('reference')
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError('A patient subject is required to publish an Observation')
    subject = subject.strip()
    if '/' not in subject and not subject.startswith('urn:'):
        subject = 'Patient/' + subject
    identifier = str(uuid5(NAMESPACE_URL,
        f'care:{job.process_instance_key}:{job.job_key}:{code}'))
    data = {
        'resourceType': 'Observation', 'id': identifier, 'status': 'final',
        'identifier': [
            {'system': 'urn:care:request-id', 'value': request_id},
            {'system': 'urn:care:camunda-job', 'value': str(job.job_key)},
            {'system': 'urn:care:process-instance', 'value': str(job.process_instance_key)}],
        'code': {'coding': [{'system': 'http://snomed.info/sct', 'code': code}]},
        'subject': {'reference': subject},
        'effectiveDateTime': result.value.timestamp.isoformat(),
        'note': [{'text': 'ARES QoS: ' + json.dumps(result.qos, allow_nan=False)}],
    }
    resource = variables.get(str(job.element_id), {}).get('resource')
    if isinstance(resource, dict):
        resource = resource.get('reference')
    if isinstance(resource, str) and resource.startswith('ServiceRequest/'):
        data['basedOn'] = [{'reference': resource}]

    def quantity(value, unit):
        return {'value': value, 'unit': unit, 'system': 'http://unitsofmeasure.org', 'code': unit}

    if code == '68130003':
        data['valueCodeableConcept'] = {'text': values['physical_activity_result']}
    elif code in ('364075005', '27113001'):
        key, unit = ('heart_rate', '/min') if code == '364075005' else ('body_weight', 'kg')
        data['valueQuantity'] = quantity(values[key], unit)
    elif code == '75367002':
        data['component'] = [
            {'code': {'coding': [{'system': 'http://loinc.org', 'code': loinc}]},
             'valueQuantity': quantity(values[name], 'mm[Hg]')}
            for name, loinc in (('systolic', '8480-6'), ('diastolic', '8462-4'))]
    elif code == '258158006':
        sleep = values['sleep_parameters']
        from datetime import datetime
        end = datetime.fromisoformat(sleep['end_timestamp'].replace('Z', '+00:00'))
        data.pop('effectiveDateTime')
        data['effectivePeriod'] = {
            'start': (end - timedelta(seconds=sleep['duration'])).isoformat(),
            'end': end.isoformat()}
        data['valueQuantity'] = quantity(sleep['duration'], 's')
        data['component'] = [
            {'code': {'text': 'Sleep quality'}, 'valueQuantity': quantity(sleep['quality'], '1')},
            *[{'code': {'text': f'{stage} stage duration'}, 'valueQuantity': quantity(seconds, 's')}
              for stage, seconds in sleep['stages'].items()]]
    return Observation.model_validate(data)


async def publish_observation(job, code: str, result: Result, request_id: str) -> None:
    """Publish using a stable job-based resource ID so job retries do not create duplicates."""
    observation = build_observation(job, code, result, request_id)
    config = get_fhir_settings()
    headers = {'Content-Type': 'application/fhir+json', 'Accept': 'application/fhir+json',
               'X-Request-ID': request_id}
    if config.api_key.get_secret_value():
        headers['X-API-Key'] = config.api_key.get_secret_value()
    async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
        response = await client.put(
            f'{str(config.base_url).rstrip("/")}/Observation/{observation.id}',
            headers=headers, json=observation.model_dump(mode='json', exclude_none=True))
        response.raise_for_status()
    WORKER_LOGGER.info('FHIR Observation published | request_id=%s instance=%s task=%s job=%s observation=%s status=%s',
        request_id, job.process_instance_key, job.element_id, job.job_key,
        observation.id, response.status_code)


async def handle(job: ConnectedJobContext) -> Dict[str, Any]:
    """
    Acquire the five San Gerardo observations through ARES; simulate other codes.

    :param job: Camunda job for ActivityDefinition 1058.
    :type job: ConnectedJobContext
    :return: Process-variable updates; the SDK completes the job automatically.
    :rtype: Dict[str, Any]
    """
    inputs = read_action_variables(job, ATTRIBUTE_IDS)
    execution = await simulate_execution(job, ACTIVITY_DEFINITION_ID)
    code = snomed_code(inputs["1058_observation_concept"])
    if code in CODE_CAPABILITIES:
        async def persist(result: Result, request_id: str) -> None:
            await publish_observation(job, code, result, request_id)
        result = await request_observation(job, code, on_result=persist)
        return record_invocation(job, ACTIVITY_DEFINITION_ID, result, inputs=inputs, execution=execution)
    result: Dict[str, Any] = {
        "vital_sign_result": random.choice(("normal", "abnormal"))
    }
    if code == "365812005":
        result["glucose_level"] = round(random.uniform(70.0, 260.0), 2)
    elif code == "386725007":
        result["body_temperature"] = round(random.uniform(36.0, 40.0), 2)
    elif code == "106048009":
        result["respiration_rate"] = round(random.uniform(10.0, 35.0), 2)
    elif code == "431314004":
        result["spo2"] = round(random.uniform(0.85, 1.0), 3)
    return record_invocation(job, ACTIVITY_DEFINITION_ID, result, inputs=inputs, execution=execution)


if __name__ == "__main__":
    from camunda_jobworkers.runner import main

    main()
