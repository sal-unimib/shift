from typing import Any, Dict

from camunda_orchestration_sdk import ConnectedJobContext

from camunda_jobworkers.simulation import simulate_execution

from camunda_jobworkers.common import read_action_variables, record_invocation


ACTIVITY_DEFINITION_ID = '1000'
JOB_TYPE = 'ad_take_medication'
ATTRIBUTE_IDS = ('1000_medication', '1000_dosage_dose_and_rate')


async def handle(job: ConnectedJobContext) -> Dict[str, Any]:
    """
    Record an invocation of Administer medication.

    :param job: Camunda job for ActivityDefinition 1000.
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
