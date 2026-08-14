from contextlib import asynccontextmanager
from fastapi import FastAPI
from datetime import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import sys

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
log_dir = "logs"
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
async def lifespan(app: FastAPI):
    """
    Lifespan method for handling startup and shutdown operation of this service.

    :param app: FastAPI application object
    :type app: FastAPI
    """
    # Startup Phase
    logger.info("SHIFT Service starting up ...")

    # 1. Initialize DB
    # logger.info("Initializing the database connection...")
    # db_source = DatabaseSource()
    # await db_source.connect()
    # await db_source.init_database()
    
    yield

    # Shutdown Phase
    logger.info("SHIFT Service shutting up ...")
    
    # Close DB connection
    # logger.info("Closing the database connection...")
    # await db_source.close()

app = FastAPI(lifespan=lifespan, redirect_slashes=False)