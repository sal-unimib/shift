import random
import json
from typing import Any, Dict

from camunda_orchestration_sdk import ConnectedJobContext

from camunda_jobworkers.simulation import simulate_execution

from camunda_jobworkers.common import read_action_variables, record_invocation


ACTIVITY_DEFINITION_ID = '1002'
JOB_TYPE = 'ad_complete_questionnaire'
ATTRIBUTE_IDS = ('1002_questionnaire',)


async def handle(job: ConnectedJobContext) -> Dict[str, Any]:
    """
    Simulate an invocation of Complete Clinical Questionnaire.

    :param job: Camunda job for ActivityDefinition 1002.
    :type job: ConnectedJobContext
    :return: Random simulated outputs; the SDK completes the job automatically.
    :rtype: Dict[str, Any]
    """
    inputs = read_action_variables(job, ATTRIBUTE_IDS)
    execution = await simulate_execution(job, ACTIVITY_DEFINITION_ID)
    answers = {
        "answers": [
            {"question": f"Q{index}", "answer": random.choice(("yes", "no", "unknown"))}
            for index in range(1, 4)
        ]
    }
    result = {
        "questionnaire_result": json.dumps(answers),
        "questionnaire_score": random.choice((0.4, 0.6)),
    }
    return record_invocation(job, ACTIVITY_DEFINITION_ID, result, inputs=inputs, execution=execution)


if __name__ == "__main__":
    from camunda_jobworkers.runner import main

    main()
