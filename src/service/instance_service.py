from fhir.resources.requestorchestration import RequestOrchestration
import logging
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional, cast

from src.domain.action_definition import ActionDefinition
from src.domain.bpmn import Definitions
from src.domain.cfg import ControlFlowGraph, ControlFlowGraphFactory, InstanceControlFlowGraph
from src.domain.enums import BPMNEngines, CFGType
from src.domain.exceptions import ArtifactReadException, ArtifactWriteException, BPMNGenerationException, CFGGenerationException, DBReadException, DBWriteException, PlanDefinitionValidationException, RequestOrchestrationValidationException
from src.domain.process_definition import ProcessDefinition
from src.domain.process_deployment import ProcessDeployment
from src.domain.process_instance import ProcessInstance
from src.domain.exceptions import CamundaDeploymentException, CamundaInstanceException, ContractIdException
from src.mappers.bpmn_mapper import BPMNStandardMapper
from src.mappers.process_definition_mapper import ProcessDefinitionMapper
from src.mappers.instance_enrichment_mapper import InstanceEnrichmentMapper
from src.repository.artifact_repository import ArtifactRepository
from src.repository.process_definition_repository import ProcessDefinitionRepository
from src.repository.process_deployment_repository import ProcessDeploymentRepository
from src.repository.process_instance_repository import ProcessInstanceRepository
from src.repository.action_definition_repository import ActionDefinitionRepository
from src.utils.definition_identifiers import action_definition_id, process_definition_id
from src.utils.bpe_selector import BPESelector
from src.utils.definition_alignment import DefinitionAlignment


logger = logging.getLogger(__name__)

class InstanceService:

    db : AsyncSession
    artifact_repository : ArtifactRepository
    process_definition_repository : ProcessDefinitionRepository
    process_deployment_repository : ProcessDeploymentRepository
    process_instance_repository : ProcessInstanceRepository
    action_definition_repository : ActionDefinitionRepository

    def __init__(self, db: AsyncSession):
        """
        Initialize the instance-level service and its repositories.

        :param db: Asynchronous database session shared by the service repositories.
        :type db: sqlalchemy.ext.asyncio.AsyncSession
        """
        self.db = db
        self.artifact_repository = ArtifactRepository()
        self.process_definition_repository = ProcessDefinitionRepository(db)
        self.process_deployment_repository = ProcessDeploymentRepository(db)
        self.process_instance_repository = ProcessInstanceRepository(db)
        self.action_definition_repository = ActionDefinitionRepository(db)

    async def instance_request(self, request_orchestration: RequestOrchestration) -> Optional[Definitions]:
        """
        Align, enrich, deploy and instantiate the patient-specific process.

        :param request_orchestration: FHIR R5 resource describing the patient-specific workflow.
        :type request_orchestration: fhir.resources.requestorchestration.RequestOrchestration
        :return: Enriched BPMN after instance creation and persistence, or None on a handled failure.
        :rtype: Optional[Definitions]
        """
        plan_id_and_version = request_orchestration.instantiatesCanonical[0].split("/")[-1]
        plan_id = plan_id_and_version.split("|")[0]
        plan_version = plan_id_and_version.split("|")[1]
        try:
            plan_cfg = self.artifact_repository.read_cfg(plan_definition_id=plan_id, version=plan_version, cfg_type=CFGType.CLASSIC)
            actual_cfg_type = None
            req_orch_cfg = ControlFlowGraphFactory.from_request_orchestration(request_orchestration, plan_cfg)
            actual_cfg_type = CFGType.CLASSIC
            logger.debug("Generated %s CFG for RequestOrchestration with ID %s (PlanDefinition %s|%s)", getattr(actual_cfg_type, "name", "initial"), request_orchestration.id, plan_id, plan_version)
        except RequestOrchestrationValidationException as e:
            logger.error("RequestOrchestration with ID %s (PlanDefinition %s|%s) is not a valid resource for SHIFT registration: %s", request_orchestration.id, plan_id, plan_version, e)
            return
        except ArtifactReadException as e:
            logger.error("An error has occurred while reading classic CFG for PlanDefinition with ID %s: %s", plan_id, e)
            return
        except CFGGenerationException as e:
            logger.error("An error has occurred while generating %s CFG for RequestOrchestration with ID %s (PlanDefinition %s|%s): %s", getattr(actual_cfg_type, "name", "initial"), request_orchestration.id, plan_id, plan_version, e)
            return

        process_definition = None
        to_align = DefinitionAlignment.requires_alignment(req_orch_cfg, plan_cfg)

        if to_align:
            try:
                logger.debug("Definition Alignment for RequestOrchestration with ID %s (PlanDefinition %s|%s)", request_orchestration.id, plan_id, plan_version)
                self.artifact_repository.save_cfg(req_orch_cfg)
                req_orch_cfg_gat = ControlFlowGraphFactory.cfg_with_gateways(req_orch_cfg)
                actual_cfg_type = CFGType.GATEWAY
                logger.debug("Generated %s CFG for RequestOrchestration with ID %s (PlanDefinition %s|%s)", getattr(actual_cfg_type, "name", "initial"), request_orchestration.id, plan_id, plan_version)
                self.artifact_repository.save_cfg(req_orch_cfg_gat)
                req_orch_cfg_tc = ControlFlowGraphFactory.cfg_with_temporal_structures(req_orch_cfg_gat)
                actual_cfg_type = CFGType.TEMPORAL
                logger.debug("Generated %s CFG for RequestOrchestration with ID %s (PlanDefinition %s|%s)", getattr(actual_cfg_type, "name", "initial"), request_orchestration.id, plan_id, plan_version)
                self.artifact_repository.save_cfg(req_orch_cfg_tc)
                bpmn_definition = BPMNStandardMapper.map(req_orch_cfg_tc)
                logger.debug("Generated BPMN for RequestOrchestration with ID %s (PlanDefinition %s|%s)", request_orchestration.id, plan_id, plan_version)
                self.artifact_repository.save_bpmn(bpmn_definition, plan_id, req_orch_cfg.get_specialized_version()) # TODO
                process_definition = await self.register_process_definition(request_orchestration, req_orch_cfg_tc)
            except CFGGenerationException as e:
                logger.error("An error has occurred while generating %s CFG for RequestOrchestration with ID %s (PlanDefinition %s|%s): %s", getattr(actual_cfg_type, "name", "initial"), request_orchestration.id, plan_id, plan_version, e)
                return
            except ArtifactWriteException as e:
                logger.error("An error has occurred while writing artifact for RequestOrchestration with ID %s (PlanDefinition %s|%s): %s", request_orchestration.id, plan_id, plan_version, e)
                return
            except BPMNGenerationException as e:
                logger.error("An error has occurred while generating BPMN process definition for RequestOrchestration with ID %s (PlanDefinition %s|%s): %s", request_orchestration.id, plan_id, plan_version, e)
                return
            except (DBReadException, DBWriteException) as e:
                logger.error("An error has occurred while registering process definition in DB for RequestOrchestration with ID %s (PlanDefinition %s|%s): %s", request_orchestration.id, plan_id, plan_version, e)
                return
            except Exception as e:
                logger.error("An unexpected error has occurred while registering %s for RequestOrchestration with ID %s (PlanDefinition %s|%s): %s", getattr(actual_cfg_type, "name", "initial"), request_orchestration.id, plan_id, plan_version, e)
                return
        else:
            process_definition = await self.process_definition_repository.get_process_definition_by_plan_definition(plan_id, plan_version)
            bpmn_definition = self.artifact_repository.read_bpmn(plan_id, plan_version)

        # if no process_def => LOG ERROR
        if process_definition is None:
            logger.error("Something went wrong for RequestOrchestration with ID %s (PlanDefinition %s|%s): No ProcessDefinition object", request_orchestration.id, plan_id, plan_version)
            return
        if bpmn_definition is None:
            logger.error("Something went wrong for RequestOrchestration with ID %s (PlanDefinition %s|%s): No BPMN process definition file", request_orchestration.id, plan_id, plan_version)
            return

        try:
            target_bpe, Enricher, bpe_source = BPESelector.select_bpe(bpmn_definition)
            action_definitions: Dict[str, ActionDefinition] = {}
            for action in ProcessDefinitionMapper.actions(request_orchestration).values():
                identifier = action_definition_id(cast(str, action.definitionCanonical))
                if identifier not in action_definitions:
                    contract = await self.action_definition_repository.get_action_definition_by_id(identifier)
                    if contract is None:
                        raise DBReadException(f"ActivityDefinition {identifier} is not loaded in the database")
                    action_definitions[identifier] = contract

            template_cfg = req_orch_cfg_tc if to_align else self.artifact_repository.read_cfg(
                plan_id, process_definition.artifact_version, CFGType.TEMPORAL
            )
            variables, action_workers = InstanceEnrichmentMapper.build(
                process_definition, req_orch_cfg, template_cfg, action_definitions
            )
            enriched_bpmn_definition = Enricher.enrich(
                bpmn_definition=bpmn_definition,
                version=process_definition.version,
                variables=variables,
                action_workers=action_workers,
            )
            bpmn_path = self.artifact_repository.save_bpmn(
                enriched_bpmn_definition, plan_id, process_definition.artifact_version, target_bpe
            )
        except ArtifactWriteException as e:
            logger.error("An error has occurred while writing artifact for RequestOrchestration with ID %s (PlanDefinition %s|%s): %s", request_orchestration.id, plan_id, plan_version, e)
            return
        except (BPMNGenerationException, DBReadException, ArtifactReadException, ValueError) as e:
            logger.error("An error has occurred while enriching BPMN for RequestOrchestration with ID %s (PlanDefinition %s|%s): %s", request_orchestration.id, plan_id, plan_version, e)
            return

        if enriched_bpmn_definition is None:
            logger.error("Something went wrong for RequestOrchestration with ID %s (PlanDefinition %s|%s): No BPMN enriched definition object", request_orchestration.id, plan_id, plan_version)
            return
        if bpmn_path is None:
            logger.error("Something went wrong for RequestOrchestration with ID %s (PlanDefinition %s|%s): No BPMN enriched definition file", request_orchestration.id, plan_id, plan_version)
            return

        # 4. Deploy on target BPE
        try:
            process_deployment = await self.process_deployment_repository.get_process_deployment_by_definition(process_definition, target_bpe)
        except DBReadException as e:
            logger.error("Cannot read deployment for ProcessDefinition %s on %s: %s", process_definition.id, target_bpe.value, e)
            return

        if process_deployment is None:
            try:
                process_deployment_key, process_deployment_version = await bpe_source.deploy_bpmn(
                    self.artifact_repository.root_dir / bpmn_path
                )
            except CamundaDeploymentException as e:
                logger.error("Cannot deploy BPMN for RequestOrchestration %s on %s: %s", request_orchestration.id, target_bpe.value, e)
                return
            try:
                process_deployment = await self.process_deployment_repository.save_process_deployment(
                    ProcessDeployment(
                        id=f"pd_{process_definition.id}_{target_bpe.value}",
                        deployment_key=process_deployment_key,
                        deployment_version=str(process_deployment_version),
                        process_definition=process_definition,
                        engine=target_bpe,
                    )
                )
            except DBWriteException as e:
                logger.error("Deployment %s succeeded but cannot be saved for ProcessDefinition %s: %s", process_deployment_key, process_definition.id, e)
                return

        if process_deployment is None:
            logger.error("No saved deployment for RequestOrchestration %s on %s", request_orchestration.id, target_bpe.value)
            return

        # 5. Create (variables, values) from RequestOrchestration
        instance_id = f"pi_{uuid4()}"
        try:
            instance_variables, generic_values, action_values, temporal_values = InstanceEnrichmentMapper.build_values(
                process_definition, request_orchestration, req_orch_cfg, variables, instance_id
            )
        except (ValueError, ContractIdException) as e:
            logger.error("Cannot resolve instance values for RequestOrchestration %s: %s", request_orchestration.id, e)
            return

        # 6. Instantiate process and persist its variable values
        try:
            process_instance_key = await bpe_source.create_process_instance_by_id(
                process_definition_id=enriched_bpmn_definition.process[0].id,
                process_definition_version=process_deployment.deployment_version,
                variables=instance_variables,
            )
        except CamundaInstanceException as e:
            logger.error("Cannot start RequestOrchestration %s using deployment %s: %s", request_orchestration.id, process_deployment.deployment_key, e)
            return

        try:
            process_instance = await self.process_instance_repository.save_process_instance(
                ProcessInstance(
                    id=instance_id,
                    instance_key=process_instance_key,
                    deployment_id=process_deployment.id,
                    patient_id=instance_variables["subject"],
                    variables=generic_values,
                    action_variables=action_values,
                    temporal_constraints=temporal_values,
                )
            )
        except DBWriteException as e:
            logger.error("Camunda instance %s started but cannot be saved for RequestOrchestration %s: %s", process_instance_key, request_orchestration.id, e)
            return
        if process_instance is None:
            logger.error("Camunda instance %s started but no SHIFT instance was saved for RequestOrchestration %s", process_instance_key, request_orchestration.id)
            return
        logger.info("Started RequestOrchestration %s as %s instance %s", request_orchestration.id, target_bpe.value, process_instance_key)
        return enriched_bpmn_definition


    async def register_process_definition(self, request_orchestration: RequestOrchestration, cfg: InstanceControlFlowGraph) -> Optional[ProcessDefinition]:
        """
        Reuse an existing child or load contracts, map and persist a new direct child.
        
        Input validation is performed by ControlFlowGraphFactory at pipeline entry.
        Transformation errors propagate to instance_request for handling.

        :param request_orchestration: Validated FHIR RequestOrchestration used by the pipeline.
        :type request_orchestration: RequestOrchestration
        :param cfg: Matching temporal CFG produced by the pipeline.
        :type cfg: InstanceControlFlowGraph
        :return: Existing or inserted definition, or None when the repository declines insertion.
        :rtype: Optional[ProcessDefinition]
        :raises DBReadException: If the parent or a referenced ActivityDefinition has not been loaded.
        """
        specialized_version = cfg.get_specialized_version()
        identifier = process_definition_id(cfg.id, specialized_version)
        existing = await self.process_definition_repository.get_process_definition_by_id(identifier)
        if existing is not None:
            return existing

        parent = await self.process_definition_repository.get_process_definition_by_plan_definition(
            cfg.id, cfg.version
        )
        if parent is None:
            raise DBReadException(f"ProcessDefinition for PlanDefinition {cfg.id}|{cfg.version} is not registered")

        action_definitions: Dict[str, ActionDefinition] = {}
        for action in ProcessDefinitionMapper.actions(request_orchestration).values():
            identifier = action_definition_id(cast(str, action.definitionCanonical))
            if identifier not in action_definitions:
                definition = await self.action_definition_repository.get_action_definition_by_id(identifier)
                if definition is None:
                    raise DBReadException(f"ActivityDefinition {identifier} is not loaded in the database")
                action_definitions[identifier] = definition

        child = ProcessDefinitionMapper.map_specialization(
            request_orchestration, cfg, parent, action_definitions, specialized_version
        )
        return await self.process_definition_repository.save_process_definition(child)
