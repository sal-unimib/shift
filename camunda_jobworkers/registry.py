from typing import Any, Awaitable, Callable, Dict

from camunda_orchestration_sdk import ConnectedJobContext

from camunda_jobworkers.ad_alert_practitioner import handle as ad_alert_practitioner
from camunda_jobworkers.ad_clinical_procedure import handle as ad_clinical_procedure
from camunda_jobworkers.ad_collect_specimen import handle as ad_collect_specimen
from camunda_jobworkers.ad_complete_questionnaire import handle as ad_complete_questionnaire
from camunda_jobworkers.ad_diet_indication import handle as ad_diet_indication
from camunda_jobworkers.ad_educate_patient import handle as ad_educate_patient
from camunda_jobworkers.ad_perform_exercise import handle as ad_perform_exercise
from camunda_jobworkers.ad_perform_imaging import handle as ad_perform_imaging
from camunda_jobworkers.ad_provide_therapy import handle as ad_provide_therapy
from camunda_jobworkers.ad_request_observation import handle as ad_request_observation
from camunda_jobworkers.ad_specialist_visit import handle as ad_specialist_visit
from camunda_jobworkers.ad_take_medication import handle as ad_take_medication


WORKERS: Dict[str, Callable[[ConnectedJobContext], Awaitable[Dict[str, Any]]]] = {
    "ad_alert_practitioner": ad_alert_practitioner,
    "ad_clinical_procedure": ad_clinical_procedure,
    "ad_collect_specimen": ad_collect_specimen,
    "ad_complete_questionnaire": ad_complete_questionnaire,
    "ad_diet_indication": ad_diet_indication,
    "ad_educate_patient": ad_educate_patient,
    "ad_perform_exercise": ad_perform_exercise,
    "ad_perform_imaging": ad_perform_imaging,
    "ad_provide_therapy": ad_provide_therapy,
    "ad_request_observation": ad_request_observation,
    "ad_specialist_visit": ad_specialist_visit,
    "ad_take_medication": ad_take_medication,
}
