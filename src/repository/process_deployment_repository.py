import logging
from typing import Optional

from src.domain.exceptions import DBReadException, DBWriteException, ContractIdException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.model.process_deployment_record import ProcessDeploymentRecord
from src.domain.enums import BPMNEngines
from src.domain.process_definition import ProcessDefinition
from src.domain.process_deployment import ProcessDeployment
from src.repository.process_definition_repository import definition_load_options


logger = logging.getLogger(__name__)


class ProcessDeploymentRepository:
    def __init__(self, db: AsyncSession):
        """
        Initialize the deployment repository.

        :param db: Shared asynchronous database session.
        :type db: AsyncSession
        """
        self.db = db

    async def _record(
        self, identifier: Optional[str] = None, deployment_key: Optional[str] = None,
        process_definition_id: Optional[str] = None, engine: Optional[BPMNEngines] = None
    ) -> Optional[ProcessDeploymentRecord]:
        """
        Load a deployment and the complete definition needed by domain mapping.

        :param identifier: SHIFT deployment ID, when selecting by ID.
        :type identifier: Optional[str]
        :param deployment_key: Engine deployment key, when selecting by key.
        :type deployment_key: Optional[str]
        :param process_definition_id: SHIFT definition ID, when selecting by definition and engine.
        :type process_definition_id: Optional[str]
        :param engine: Target engine, when selecting by definition.
        :type engine: Optional[BPMNEngines]
        :return: Eagerly loaded record or None.
        :rtype: Optional[ProcessDeploymentRecord]
        """
        query = select(ProcessDeploymentRecord).options(
            selectinload(ProcessDeploymentRecord.process_definition).options(*definition_load_options())
        )
        if identifier is not None:
            query = query.where(ProcessDeploymentRecord.id == identifier)
        elif process_definition_id is not None:
            query = query.where(
                ProcessDeploymentRecord.process_def_id == process_definition_id,
                ProcessDeploymentRecord.engine == engine,
            )
        else:
            query = query.where(ProcessDeploymentRecord.deployment_key == deployment_key)
        return await self.db.scalar(query)

    async def save_process_deployment(
        self, process_deployment: ProcessDeployment
    ) -> Optional[ProcessDeployment]:
        """
        Persist and map a deployment before committing the session.

        :param process_deployment: Deployment linked to its SHIFT definition.
        :type process_deployment: ProcessDeployment
        :return: Saved domain deployment, or None if no record is available.
        :rtype: Optional[ProcessDeployment]
        :raises DBWriteException: If persistence or mapping fails.
        """
        try:
            self.db.add(process_deployment.to_record())
            await self.db.flush()
            record = await self._record(identifier=process_deployment.id)
            if record is None:
                await self.db.rollback()
                return None
            result = ProcessDeployment.from_record(record)
            await self.db.commit()
            return result
        except Exception as error:
            try:
                await self.db.rollback()
            except Exception:
                logger.exception("Cannot roll back ProcessDeployment persistence")
            if isinstance(error, (DBReadException, DBWriteException, ContractIdException)):
                raise
            raise DBWriteException(f'Cannot save ProcessDeployment {getattr(process_deployment, "id", None)}: {error}') from error

    async def get_process_deployment_by_id(self, process_deployment_id: str) -> Optional[ProcessDeployment]:
        """
        Retrieve a deployment by SHIFT ID.

        :param process_deployment_id: SHIFT deployment ID.
        :type process_deployment_id: str
        :return: Domain deployment or None.
        :rtype: Optional[ProcessDeployment]
        :raises DBReadException: If reading or mapping fails.
        """
        try:
            record = await self._record(identifier=process_deployment_id)
            return ProcessDeployment.from_record(record) if record is not None else None
        except Exception as error:
            try:
                await self.db.rollback()
            except Exception:
                logger.exception("Cannot roll back ProcessDeployment read")
            if isinstance(error, (DBReadException, DBWriteException, ContractIdException)):
                raise
            raise DBReadException(f"Cannot retrieve ProcessDeployment by process_deployment_id {process_deployment_id}: {error}") from error

    async def get_process_deployment_by_definition(
        self, process_definition: ProcessDefinition, engine: BPMNEngines
    ) -> Optional[ProcessDeployment]:
        """
        Retrieve a deployment by its SHIFT definition and target engine.

        :param process_definition: SHIFT process definition to find a deployment for.
        :type process_definition: ProcessDefinition
        :param engine: Target BPMN engine.
        :type engine: BPMNEngines
        :return: Domain deployment or None.
        :rtype: Optional[ProcessDeployment]
        :raises DBReadException: If reading or mapping fails.
        """
        try:
            record = await self._record(
                process_definition_id=process_definition.id, engine=engine
            )
            return ProcessDeployment.from_record(record) if record is not None else None
        except Exception as error:
            try:
                await self.db.rollback()
            except Exception:
                logger.exception("Cannot roll back ProcessDeployment read")
            if isinstance(error, (DBReadException, DBWriteException, ContractIdException)):
                raise
            raise DBReadException(f"Cannot retrieve ProcessDeployment by definition {process_definition.id}: {error}") from error

    async def get_process_deployment_by_deployment_key(self, process_deployment_key: str) -> Optional[ProcessDeployment]:
        """
        Retrieve a deployment by its engine key.

        :param process_deployment_key: Engine deployment key.
        :type process_deployment_key: str
        :return: Domain deployment or None.
        :rtype: Optional[ProcessDeployment]
        :raises DBReadException: If reading or mapping fails.
        """
        try:
            record = await self._record(deployment_key=process_deployment_key)
            return ProcessDeployment.from_record(record) if record is not None else None
        except Exception as error:
            try:
                await self.db.rollback()
            except Exception:
                logger.exception("Cannot roll back ProcessDeployment read")
            if isinstance(error, (DBReadException, DBWriteException, ContractIdException)):
                raise
            raise DBReadException(f"Cannot retrieve ProcessDeployment by process_deployment_key {process_deployment_key}: {error}") from error
