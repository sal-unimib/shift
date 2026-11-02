import random
from typing import Any, Dict

from camunda_orchestration_sdk import ConnectedJobContext

from camunda_jobworkers.simulation import simulate_execution

from camunda_jobworkers.common import read_action_variables, record_invocation


ACTIVITY_DEFINITION_ID = '1056'
JOB_TYPE = 'ad_perform_imaging'
ATTRIBUTE_IDS = ('1056_imaging_modality_concept', '1056_body_site_concept')


async def handle(job: ConnectedJobContext) -> Dict[str, Any]:
    """
    Simulate an invocation of Perform Diagnostic Imaging Study.

    :param job: Camunda job for ActivityDefinition 1056.
    :type job: ConnectedJobContext
    :return: Random simulated outputs; the SDK completes the job automatically.
    :rtype: Dict[str, Any]
    """
    inputs = read_action_variables(job, ATTRIBUTE_IDS)
    execution = await simulate_execution(job, ACTIVITY_DEFINITION_ID)
    result = {"imaging_result": random.choice(("positive", "negative", "to_investigate"))}
    return record_invocation(job, ACTIVITY_DEFINITION_ID, result, inputs=inputs, execution=execution)


if __name__ == "__main__":
    from camunda_jobworkers.runner import main

    main()
