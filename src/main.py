from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from datetime import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import sys
from src.api.webhooks import router as webhooks_router
from src.database.connection import engine
from src.database.initialization import initialize_database
from src.utils.settings import settings
from src.sources.camunda_source import CamundaSource

# Logging
logger = logging.getLogger("shift")
logger.setLevel(logging.DEBUG)

if logger.hasHandlers():
    logger.handlers.clear()

# Logging - Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Logging - File handler
log_dir = settings.filesystem.logs_dir
os.makedirs(log_dir, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_dir, f"shift_{timestamp}.log")

file_handler = TimedRotatingFileHandler(
    filename=os.path.join(log_dir, f"shift_{timestamp}.log"),
    when="midnight",
    interval=1,
    backupCount=30,
    encoding="utf-8",
    utc=True
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)
logger.propagate = False

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Initialize missing tables and close Camunda and database clients on shutdown.

    Startup errors propagate and prevent the application from accepting requests.

    :param app: FastAPI application using this lifespan context manager.
    :type app: fastapi.FastAPI
    :return: Async iterator yielding after successful schema initialization.
    :rtype: collections.abc.AsyncIterator[None]
    """
    # Startup Phase
    logger.info("SHIFT Service starting up ...")

    try:
        await initialize_database()
        logger.info("SHIFT database schema initialized")
        yield
    finally:
        logger.info("SHIFT Service shutting down ...")
        try:
            await CamundaSource.close()
        finally:
            await engine.dispose()

app = FastAPI(lifespan=lifespan, redirect_slashes=False)

app.include_router(webhooks_router)
