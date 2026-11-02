import logging
from typing import Optional

from src.domain.exceptions import DBReadException, DBWriteException, ContractIdException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.model.process_instance_record import ProcessInstanceRecord
from src.domain.process_instance import ProcessInstance


logger = logging.getLogger(__name__)


class ProcessInstanceRepository:
    def __init__(self, db: AsyncSession):
        """
        Initialize the instance repository.

        :param db: Shared asynchronous database session.
        :type db: AsyncSession
        """
        self.db = db

    async def _record(
        self, identifier: Optional[str] = None, instance_key: Optional[str] = None
    ) -> Optional[ProcessInstanceRecord]:
        """
        Load an instance and all three variable collections.

        :param identifier: SHIFT instance ID, when selecting by ID.
        :type identifier: Optional[str]
        :param instance_key: Camunda instance key, when selecting by key.
        :type instance_key: Optional[str]
        :return: Eagerly loaded record or None.
        :rtype: Optional[ProcessInstanceRecord]
        """
        query = select(ProcessInstanceRecord).options(
            selectinload(ProcessInstanceRecord.variables),
            selectinload(ProcessInstanceRecord.action_variables),
            selectinload(ProcessInstanceRecord.temporal_constraints),
        )
        query = query.where(
            ProcessInstanceRecord.id == identifier if identifier is not None
            else ProcessInstanceRecord.instance_key == instance_key
        )
        return await self.db.scalar(query)

    async def save_process_instance(self, process_instance: ProcessInstance) -> Optional[ProcessInstance]:
        """
        Persist and map an instance before committing the session.

        :param process_instance: Instance with its SHIFT deployment link and values.
        :type process_instance: ProcessInstance
        :return: Saved instance or None if no record is available.
        :rtype: Optional[ProcessInstance]
        :raises DBWriteException: If persistence or mapping fails.
        """
        try:
            self.db.add(process_instance.to_record())
            await self.db.flush()
            record = await self._record(identifier=process_instance.id)
            if record is None:
                await self.db.rollback()
                return None
            result = ProcessInstance.from_record(record)
            await self.db.commit()
            return result
        except Exception as error:
            try:
                await self.db.rollback()
            except Exception:
                logger.exception("Cannot roll back ProcessInstance persistence")
            if isinstance(error, (DBReadException, DBWriteException, ContractIdException)):
                raise
            raise DBWriteException(f'Cannot save ProcessInstance {getattr(process_instance, "id", None)}: {error}') from error

    async def get_process_instance_by_id(self, process_instance_id: str) -> Optional[ProcessInstance]:
        """
        Retrieve an instance by SHIFT ID.

        :param process_instance_id: SHIFT instance ID.
        :type process_instance_id: str
        :return: Domain instance or None.
        :rtype: Optional[ProcessInstance]
        :raises DBReadException: If reading or mapping fails.
        """
        try:
            record = await self._record(identifier=process_instance_id)
            return ProcessInstance.from_record(record) if record is not None else None
        except Exception as error:
            try:
                await self.db.rollback()
            except Exception:
                logger.exception("Cannot roll back ProcessInstance read")
            if isinstance(error, (DBReadException, DBWriteException, ContractIdException)):
                raise
            raise DBReadException(f"Cannot retrieve ProcessInstance by process_instance_id {process_instance_id}: {error}") from error

    async def get_process_instance_by_key(self, instance_key: str) -> Optional[ProcessInstance]:
        """
        Retrieve an instance by its engine key.

        :param instance_key: Camunda instance key.
        :type instance_key: str
        :return: Domain instance or None.
        :rtype: Optional[ProcessInstance]
        :raises DBReadException: If reading or mapping fails.
        """
        try:
            record = await self._record(instance_key=instance_key)
            return ProcessInstance.from_record(record) if record is not None else None
        except Exception as error:
            try:
                await self.db.rollback()
            except Exception:
                logger.exception("Cannot roll back ProcessInstance read")
            if isinstance(error, (DBReadException, DBWriteException, ContractIdException)):
                raise
            raise DBReadException(f"Cannot retrieve ProcessInstance by instance_key {instance_key}: {error}") from error
