from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from fhir.resources.bundle import Bundle
from fhir.resources.plandefinition import PlanDefinition
from fhir.resources.requestorchestration import RequestOrchestration
from fhir.resources.patient import Patient
from fhir.resources.task import Task
from fhir.resources.subscriptionstatus import SubscriptionStatus
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["fhir-subscriptions"])

@router.post("/plandefinition")
async def plandefinition_webhook(request: Request):
    """
    Endpoint to handle new PlanDefinition FHIR resources via subscription webhook.
    It executes the routines to translate FHIR PlanDefinition resource into BPMN standard format and registers all the necessary information.

    :param request: FastAPI Request object containing the incoming FHIR Bundle
    :type request: Request
    :return: JSONResponse confirming receipt and processing status
    :rtype: JSONResponse
    """
    try:
        logger.info("Received a new FHIR PlanDefinition via subscription webhook")
        json_payload = await request.json()
        subscription_bundle = Bundle(**json_payload)
        response_data = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": json_payload.get("entry")
        }
        
        for entry in subscription_bundle.entry or []:
            if type(entry.resource) == PlanDefinition:
                plan_definition = entry.resource
            elif type(entry.resource) == SubscriptionStatus:
                subscription_status : SubscriptionStatus = entry.resource
                subscription = subscription_status.subscription.reference
                subscription_topic = '/'.join(urlparse(subscription_status.topic).path.split("/")[2:])
                subscription_event_number = subscription_status.eventsSinceSubscriptionStart
                subscription_event_focus = subscription_status.notificationEvent[0].focus.reference
                logger.info("SubscriptionStatus n.%s on topic %s for %s: %s",
                    subscription_event_number,
                    subscription_topic,
                    subscription,
                    subscription_event_focus
                )
            else:
                logger.debug("FHIR type not handled: %s", type(entry.resource))
        
        # TODO genera BPMN

    except Exception as e:
        logger.error(f"Error processing PlanDefinition webhook: {e}")
    finally:
        return JSONResponse(content=response_data, status_code=200)
    

@router.post("/requestorchestration")
async def requestorchestration_webhook(request: Request):
    """
    Endpoint to handle new RequestOrchestration FHIR resources via subscription webhook.
    It executes the routines to instantiate the BPMN process.

    :param request: FastAPI Request object containing the incoming FHIR Bundle
    :type request: Request
    :return: JSONResponse confirming receipt and processing status
    :rtype: JSONResponse
    """
    try:
        logger.info("Received a new FHIR PlanDefinition via subscription webhook")
        json_payload = await request.json()
        subscription_bundle = Bundle(**json_payload)
        response_data = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": json_payload.get("entry")
        }
        
        fhir_requests_dict = {}
        for entry in subscription_bundle.entry or []:
            if type(entry.resource) == RequestOrchestration:
                request_orchestration = entry.resource
            elif type(entry.resource) == Patient:
                patient = entry.resource
            elif type(entry.resource) == PlanDefinition:
                plan_definition = entry.resource
            elif type(entry.resource) == Task:
                fhir_requests_dict[entry.resource.id] = entry.resource
            elif "Request" in type(entry.resource).__name__:
                fhir_requests_dict[entry.resource.id] = entry.resource
            elif type(entry.resource) == SubscriptionStatus:
                subscription_status : SubscriptionStatus = entry.resource
                subscription = subscription_status.subscription.reference
                subscription_topic = '/'.join(urlparse(subscription_status.topic).path.split("/")[2:])
                subscription_event_number = subscription_status.eventsSinceSubscriptionStart
                subscription_event_focus = subscription_status.notificationEvent[0].focus.reference
                logger.info("SubscriptionStatus n.%s on topic %s for %s: %s",
                    subscription_event_number,
                    subscription_topic,
                    subscription,
                    subscription_event_focus
                )
            else:
                logger.debug("FHIR type not handled: %s", type(entry.resource))

        fhir_requests = {}
        for action in request_orchestration.action or []:
            fhir_requests[action.linkId] = fhir_requests_dict[action.resource.split("/")[-1]]
        
        # TODO istanzia processo

    except Exception as e:
        logger.error(f"Error processing PlanDefinition webhook: {e}")
    finally:
        return JSONResponse(content=response_data, status_code=200)
    
