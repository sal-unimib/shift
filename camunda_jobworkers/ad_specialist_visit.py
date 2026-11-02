import random
from typing import Any, Dict

from camunda_orchestration_sdk import ConnectedJobContext

from camunda_jobworkers.simulation import simulate_execution

from camunda_jobworkers.common import read_action_variables, record_invocation


ACTIVITY_DEFINITION_ID = '1059'
JOB_TYPE = 'ad_specialist_visit'
ATTRIBUTE_IDS = ('1059_visit_concept',)


async def handle(job: ConnectedJobContext) -> Dict[str, Any]:
    """
    Simulate an invocation of Attend Scheduled Specialist Visit.

    :param job: Camunda job for ActivityDefinition 1059.
    :type job: ConnectedJobContext
    :return: Random simulated outputs; the SDK completes the job automatically.
    :rtype: Dict[str, Any]
    """
    inputs = read_action_variables(job, ATTRIBUTE_IDS)
    execution = await simulate_execution(job, ACTIVITY_DEFINITION_ID)
    result = {"specialist_result": random.choice(("good", "normal", "bad"))}
    return record_invocation(job, ACTIVITY_DEFINITION_ID, result, inputs=inputs, execution=execution)


if __name__ == "__main__":
    from camunda_jobworkers.runner import main

    main()
