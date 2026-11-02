import random
from typing import Any, Dict

from camunda_orchestration_sdk import ConnectedJobContext

from camunda_jobworkers.simulation import simulate_execution

from camunda_jobworkers.common import read_action_variables, record_invocation, snomed_code


ACTIVITY_DEFINITION_ID = '1053'
JOB_TYPE = 'ad_collect_specimen'
ATTRIBUTE_IDS = ('1053_specimen_concept', '1053_body_site_concept')


async def handle(job: ConnectedJobContext) -> Dict[str, Any]:
    """
    Simulate an invocation of Collect Biological Specimen.

    :param job: Camunda job for ActivityDefinition 1053.
    :type job: ConnectedJobContext
    :return: Random simulated outputs; the SDK completes the job automatically.
    :rtype: Dict[str, Any]
    """
    inputs = read_action_variables(job, ATTRIBUTE_IDS)
    execution = await simulate_execution(job, ACTIVITY_DEFINITION_ID)
    code = snomed_code(inputs["1053_specimen_concept"])
    outcomes = ("infection", "ulcer", "normal") if code == "119365002" else ("normal", "abnormal")
    result = {"specimen_result": random.choice(outcomes)}
    return record_invocation(job, ACTIVITY_DEFINITION_ID, result, inputs=inputs, execution=execution)


if __name__ == "__main__":
    from camunda_jobworkers.runner import main

    main()
