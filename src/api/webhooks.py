from src.service.instance_service import InstanceService
from src.service.definition_service import DefinitionService
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from fhir.resources.bundle import Bundle
from fhir.resources.plandefinition import PlanDefinition
from fhir.resources.requestorchestration import RequestOrchestration
from fhir.resources.patient import Patient
from fhir.resources.task import Task
from fhir.resources.subscriptionstatus import SubscriptionStatus
import logging
from src.database.connection import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["fhir-subscriptions"])

@router.post("/plandefinition")
async def plandefinition_webhook(request: Request, db: AsyncSession = Depends(get_session)):
    """
    Handle a FHIR PlanDefinition notification using an asynchronous database session.

    Currently accepts a resource directly; subscription Bundle handling is not implemented. The response does not independently certify successful transformation or persistence.

    :param request: HTTP request containing the FHIR resource as a JSON body.
    :type request: fastapi.Request
    :param db: Asynchronous database session supplied by the FastAPI dependency.
    :type db: sqlalchemy.ext.asyncio.AsyncSession
    :return: Empty JSON response with HTTP status 200 after the service returns.
    :rtype: fastapi.responses.JSONResponse
    """

    response_data = {}
    logger.info("Received a new FHIR PlanDefinition via subscription webhook")
    json_payload = await request.json()

    # TODO handle fhir.bundle

    plandefinition = PlanDefinition.model_validate(json_payload)

    definition_service = DefinitionService(db)
    await definition_service.register_plandefinition(plandefinition)

    return JSONResponse(content=response_data, status_code=200)

@router.post("/requestorchestration")
async def requestorchestration_webhook(request: Request, db: AsyncSession = Depends(get_session)):
    """
    Handle a FHIR RequestOrchestration notification using an asynchronous database session.

    Currently accepts a resource directly; subscription Bundle handling is not implemented. The response does not independently certify successful transformation or persistence.

    :param request: HTTP request containing the FHIR resource as a JSON body.
    :type request: fastapi.Request
    :param db: Asynchronous database session supplied by the FastAPI dependency.
    :type db: sqlalchemy.ext.asyncio.AsyncSession
    :return: Empty JSON response with HTTP status 200 after the service returns.
    :rtype: fastapi.responses.JSONResponse
    """
    response_data = {}
    logger.info("Received a new FHIR PlanDefinition via subscription webhook")
    json_payload = await request.json()

    # TODO handle fhir.bundle and all requests

    requestorchestration = RequestOrchestration.model_validate(json_payload)

    instance_service = InstanceService(db)
    await instance_service.instance_request(requestorchestration)

    return JSONResponse(content=response_data, status_code=200)
