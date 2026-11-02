from typing import Any, Dict

from camunda_orchestration_sdk import ConnectedJobContext

from camunda_jobworkers.simulation import simulate_execution

from camunda_jobworkers.common import read_action_variables, record_invocation


ACTIVITY_DEFINITION_ID = '1051'
JOB_TYPE = 'ad_alert_practitioner'
ATTRIBUTE_IDS = ('1051_priority', '1051_payload', '1051_requester', '1051_recipient', '1051_information_provider')


async def handle(job: ConnectedJobContext) -> Dict[str, Any]:
    """
    Record an invocation of Alert Healthcare Practitioner.

    :param job: Camunda job for ActivityDefinition 1051.
    :type job: ConnectedJobContext
    :return: Empty variable update; the SDK completes the job automatically.
    :rtype: Dict[str, Any]
    """
    inputs = read_action_variables(job, ATTRIBUTE_IDS)
    execution = await simulate_execution(job, ACTIVITY_DEFINITION_ID)
    return record_invocation(job, ACTIVITY_DEFINITION_ID, inputs=inputs, execution=execution)


if __name__ == "__main__":
    from camunda_jobworkers.runner import main

    main()
