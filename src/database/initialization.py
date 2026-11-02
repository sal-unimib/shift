from sqlalchemy.ext.asyncio import AsyncEngine
from src.database.base import Base
from src.database.connection import engine
from src.database.model import (
    action_definition_record,
    process_definition_record,
    process_deployment_record,
    process_instance_record,
)

# Import every model module above before create_all, including instance-level tables.


async def initialize_database(db_engine: AsyncEngine = engine) -> None:
    """Create missing SHIFT tables using the complete SQLAlchemy metadata.

    The configured PostgreSQL database must already exist. Existing tables and data
    are retained; this operation does not update existing table structures.

    :param db_engine: Asynchronous engine; defaults to the configured PostgreSQL engine.
    :type db_engine: sqlalchemy.ext.asyncio.AsyncEngine
    :return: None.
    :rtype: None
    :raises sqlalchemy.exc.SQLAlchemyError: If connection or schema creation fails.
    """
    async with db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all, checkfirst=True)
