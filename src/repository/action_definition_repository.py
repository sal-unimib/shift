from src.utils.definition_identifiers import action_definition_id as normalize_action_definition_id
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.database.model.action_definition_record import ActionDefinitionRecord
from src.domain.action_definition import ActionDefinition


class ActionDefinitionRepository:
    def __init__(self, db: AsyncSession):
        """
        Initialize the action definition repository.

        :param db: Asynchronous database session used by the repository.
        :type db: sqlalchemy.ext.asyncio.AsyncSession
        """
        self.db = db

    async def get_action_definition_by_id(self, action_definition_id: str) -> Optional[ActionDefinition]:
        """
        Retrieve an action definition and eagerly load its declared attributes.

        :param action_definition_id: ActivityDefinition identifier stored in SHIFT.
        :type action_definition_id: str
        :return: Matching action definition, or None if no definition exists.
        :rtype: typing.Optional[ActionDefinition]
        """
        record = await self.db.scalar(select(ActionDefinitionRecord).where(
            ActionDefinitionRecord.id == normalize_action_definition_id(action_definition_id)).options(
                selectinload(ActionDefinitionRecord.attributes)))
        return ActionDefinition.from_record(record) if record else None
