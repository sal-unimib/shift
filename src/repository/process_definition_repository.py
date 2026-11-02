from src.utils.definition_identifiers import process_definition_id
import logging
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, Load
from src.database.model.process_definition_record import ProcessDefinitionRecord, ProcessDefinitionActionVariableRecord
from src.domain.process_definition import ProcessDefinition


logger = logging.getLogger(__name__)

def definition_load_options() -> Tuple[Load, ...]:
    # Domain mapping accesses these relationships synchronously: load them explicitly.
    """
    Build eager-loading options for mapping process definitions to domain objects.

    :return: Loader options for action variables, their attributes, generic variables and temporal constraints.
    :rtype: Tuple[sqlalchemy.orm.Load, ...]
    """
    return (
        selectinload(ProcessDefinitionRecord.action_variables).selectinload(
            ProcessDefinitionActionVariableRecord.action_definition_attribute),
        selectinload(ProcessDefinitionRecord.variables),
        selectinload(ProcessDefinitionRecord.temporal_constraints),
    )


class ProcessDefinitionRepository:

    db: AsyncSession

    def __init__(self, db: AsyncSession):
        """
        Initialize the process definition repository.

        :param db: Asynchronous database session used by the repository.
        :type db: sqlalchemy.ext.asyncio.AsyncSession
        """
        self.db = db

    async def _record(self, identifier: str) -> Optional[ProcessDefinitionRecord]:
        """
        Retrieve a process definition record with its required relationships loaded.

        :param identifier: Internal process definition identifier.
        :type identifier: str
        :return: Matching record, or None if no record exists.
        :rtype: Optional[ProcessDefinitionRecord]
        """
        return await self.db.scalar(select(ProcessDefinitionRecord).where(
            ProcessDefinitionRecord.id == identifier).options(*definition_load_options()))

    async def save_process_definition(self, definition: ProcessDefinition) -> Optional[ProcessDefinition]:
        """
        Insert a process definition and return its domain representation.

        Uses <plan_id>_<version> as the identifier and validates the single-level parent-child relationship. The version is provided by the caller and may differ from the parent version. Insertion and mapping failures are logged and rollback is attempted without propagating exceptions to the caller.

        :param definition: Definition to insert, including its declarations and optional parent.
        :type definition: ProcessDefinition
        :return: Inserted definition, or None if it already exists, is invalid or cannot be inserted.
        :rtype: Optional[ProcessDefinition]
        """
        try:
            definition.id = process_definition_id(definition.plan_definition_id, definition.version)
            if await self._record(definition.id) is not None:
                return None
            if definition.parent_definition_id:
                parent = await self.db.get(ProcessDefinitionRecord, definition.parent_definition_id)
                if parent is None or parent.parent_definition_id is not None or parent.revision != 1:
                    return None
                if parent.plan_definition_id != definition.plan_definition_id:
                    return None
                if definition.revision != 2 or not definition.specialization_key:
                    return None
            elif definition.revision != 1:
                return None
            self.db.add(definition.to_record())
            await self.db.flush()
            # Load and map before commit: a conversion failure must not leave an inserted row.
            record = await self._record(definition.id)
            if record is None:
                await self.db.rollback()
                return None
            result = ProcessDefinition.from_record(record)
            await self.db.commit()
            return result
        except Exception:
            logger.exception('Could not insert process definition')
            try:
                await self.db.rollback()
            except Exception:
                logger.exception('Could not roll back process definition insertion')
            return None

    async def get_process_definition_by_id(self, identifier: str) -> Optional[ProcessDefinition]:
        """
        Retrieve a process definition by its internal identifier.

        :param identifier: Internal process definition identifier.
        :type identifier: str
        :return: Matching definition, or None if no definition exists.
        :rtype: Optional[ProcessDefinition]
        """
        record = await self._record(identifier)
        return ProcessDefinition.from_record(record) if record else None

    async def get_process_definition_by_plan_definition(self, identifier: str, version: Optional[str] = None) -> Optional[ProcessDefinition]:
        """
        Retrieve the most recently inserted root definition for a FHIR PlanDefinition.

        Specialized child definitions are excluded from this lookup.

        :param identifier: Source PlanDefinition resource identifier.
        :type identifier: str
        :param version: FHIR version to match, or None to search across versions.
        :type version: Optional[str]
        :return: Matching root definition, or None if no definition exists.
        :rtype: Optional[ProcessDefinition]
        """
        query = select(ProcessDefinitionRecord).where(
            ProcessDefinitionRecord.plan_definition_id == identifier,
            ProcessDefinitionRecord.parent_definition_id.is_(None))
        if version is not None:
            query = query.where(ProcessDefinitionRecord.version == version)
        record = await self.db.scalar(query.options(*definition_load_options()).order_by(
            ProcessDefinitionRecord.insert_time.desc(), ProcessDefinitionRecord.id).limit(1))
        return ProcessDefinition.from_record(record) if record else None

    async def get_children(self, identifier: str) -> List[ProcessDefinition]:
        """
        Retrieve the direct specializations of a process definition.

        :param identifier: Internal identifier of the parent process definition.
        :type identifier: str
        :return: Direct child definitions; an empty list if none exist.
        :rtype: List[ProcessDefinition]
        """
        records = await self.db.scalars(select(ProcessDefinitionRecord).where(
            ProcessDefinitionRecord.parent_definition_id == identifier).options(*definition_load_options()))
        return [ProcessDefinition.from_record(r) for r in records]
