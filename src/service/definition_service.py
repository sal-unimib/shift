from typing import Dict, Optional, cast
from src.utils.definition_identifiers import action_definition_id
from fhir.resources.plandefinition import PlanDefinition
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.cfg import ControlFlowGraphFactory, ControlFlowGraph
from src.domain.enums import CFGType
from src.domain.exceptions import (
    CFGGenerationException,
    PlanDefinitionValidationException,
    ArtifactWriteException,
    BPMNGenerationException,
    DBWriteException,
    DBReadException
)
from src.domain.action_definition import ActionDefinition
from src.domain.process_definition import ProcessDefinition
from src.mappers.process_definition_mapper import ProcessDefinitionMapper
from src.mappers.bpmn_mapper import BPMNStandardMapper
from src.repository.action_definition_repository import ActionDefinitionRepository
from src.repository.artifact_repository import ArtifactRepository
from src.repository.process_definition_repository import ProcessDefinitionRepository

logger = logging.getLogger(__name__)

class DefinitionService:
    artifact_repository : ArtifactRepository
    action_definition_repository : ActionDefinitionRepository
    process_definition_repository : ProcessDefinitionRepository
    
    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the definition-level transformation service and its repositories.

        :param db: Asynchronous database session shared by the service repositories.
        :type db: sqlalchemy.ext.asyncio.AsyncSession
        """
        self.artifact_repository=ArtifactRepository()
        self.action_definition_repository=ActionDefinitionRepository(db)
        self.process_definition_repository=ProcessDefinitionRepository(db)

    async def register_plandefinition(self, plandefinition: PlanDefinition) -> Optional[ProcessDefinition]:
        """
        Perform the definition-level transformation of a FHIR PlanDefinition resource.

        Generates and stores classic, gateway and temporal CFG artifacts and a standard BPMN definition, then invokes process definition registration. Handled failures are logged.

        :param plandefinition: FHIR R5 PlanDefinition resource to register into SHIFT.
        :type plandefinition: fhir.resources.plandefinition.PlanDefinition
        :return: Inserted definition, or None if transformation or registration fails.
        :rtype: Optional[ProcessDefinition]
        """

        try:
            actual_cfg_type = None
            classic_cfg = ControlFlowGraphFactory.from_plandefinition(plandefinition) # Throw CFGGenerationException/PlanDefinitionValidationException
            actual_cfg_type = CFGType.CLASSIC
            logger.debug("Generated %s CFG for PlanDefinition with ID %s", getattr(actual_cfg_type, "name", "initial"), plandefinition.id)
            self.artifact_repository.save_cfg(classic_cfg)
            cfg_gat = ControlFlowGraphFactory.cfg_with_gateways(classic_cfg) # Throw CFGGenerationException
            actual_cfg_type = CFGType.GATEWAY
            logger.debug("Generated %s CFG for PlanDefinition with ID %s", getattr(actual_cfg_type, "name", "initial"), plandefinition.id)
            self.artifact_repository.save_cfg(cfg_gat)
            cfg_tc = ControlFlowGraphFactory.cfg_with_temporal_structures(cfg_gat) # Throw CFGGenerationException
            actual_cfg_type = CFGType.TEMPORAL
            logger.debug("Generated %s CFG for PlanDefinition with ID %s", getattr(actual_cfg_type, "name", "initial"), plandefinition.id)
            self.artifact_repository.save_cfg(cfg_tc)
            bpmn_definition = BPMNStandardMapper.map(cfg_tc) # Throw BPMNGenerationException
            logger.debug("Generated BPMN for PlanDefinition with ID %s", plandefinition.id)
            self.artifact_repository.save_bpmn(bpmn_definition, plandefinition.id, plandefinition.version)
            return await self.register_process_definition(plandefinition, cfg_tc)
        except PlanDefinitionValidationException as e:
            logger.error("PlanDefinition with ID %s is not a valid resource for SHIFT registration: %s", plandefinition.id, e)
        except CFGGenerationException as e:
            logger.error("An error has occurred while generating %s CFG for PlanDefinition with ID %s: %s", getattr(actual_cfg_type, "name", "initial"), plandefinition.id, e)
        except ArtifactWriteException as e:
            logger.error("An error has occurred while writing artifact for PlanDefinition with ID %s: %s", plandefinition.id, e)
        except BPMNGenerationException as e:
            logger.error("An error has occurred while generating BPMN process definition for PlanDefinition with ID %s: %s", plandefinition.id, e)
        except (DBReadException, DBWriteException) as e:
            logger.error("An error has occurred while registering process definition in DB for PlanDefinition with ID %s: %s", plandefinition.id, e)
        except Exception as e:
            logger.error("An unexpected error has occurred while registering %s for PlanDefinition with ID %s: %s", getattr(actual_cfg_type, "name", "initial"), plandefinition.id, e)
        return None

    async def register_process_definition(self, plandefinition: PlanDefinition, cfg: ControlFlowGraph) -> Optional[ProcessDefinition]:
        """Load action contracts, map the validated definition and persist it.

        Input validation is performed by ControlFlowGraphFactory at pipeline entry.
        Transformation errors propagate to register_plandefinition for handling.

        :param plandefinition: Validated FHIR PlanDefinition used by the pipeline.
        :type plandefinition: PlanDefinition
        :param cfg: Matching temporal CFG produced by the pipeline.
        :type cfg: ControlFlowGraph
        :return: Inserted definition, or None when the repository declines insertion.
        :rtype: Optional[ProcessDefinition]
        :raises DBReadException: If a referenced ActivityDefinition has not been loaded.
        """
        action_definitions: Dict[str, ActionDefinition] = {}
        for action in ProcessDefinitionMapper.actions(plandefinition).values():
            identifier = action_definition_id(cast(str, action.definitionCanonical))
            if identifier not in action_definitions:
                action_definition = await self.action_definition_repository.get_action_definition_by_id(identifier)
                if action_definition is None:
                    raise DBReadException(f'ActivityDefinition {identifier} is not loaded in the database')
                action_definitions[identifier] = action_definition
        process_definition = ProcessDefinitionMapper.map(plandefinition, cfg, action_definitions)
        return await self.process_definition_repository.save_process_definition(process_definition)
