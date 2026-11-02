import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict

from dotenv import dotenv_values

from camunda_orchestration_sdk import CamundaAsyncClient, WorkerConfig

from camunda_jobworkers.common import INVOCATION_LOGGER, WORKER_LOGGER
from camunda_jobworkers.registry import WORKERS


BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
ENV_FILE = BASE_DIR.parent / ".env"
CAMUNDA_ENV_KEYS = {
    "CAMUNDA_REST_ADDRESS": "SHIFT_CAMUNDA__REST_ADDRESS",
    "CAMUNDA_AUTH_STRATEGY": "SHIFT_CAMUNDA__AUTH_STRATEGY",
    "CAMUNDA_OAUTH_URL": "SHIFT_CAMUNDA__OAUTH_URL",
    "CAMUNDA_CLIENT_ID": "WORKERS_CAMUNDA_CLIENT_ID",
    "CAMUNDA_CLIENT_SECRET": "WORKERS_CAMUNDA_CLIENT_SECRET",
    "CAMUNDA_TOKEN_AUDIENCE": "WORKERS_CAMUNDA_TOKEN_AUDIENCE",
}


def client_configuration() -> Dict[str, str]:
    """
    Read shared connection settings and worker credentials from env/.env.

    Environment variables override the project .env without modifying os.environ.
    Connection address, authentication strategy and OAuth URL are shared with
    SHIFT; client ID, client secret and audience belong to the workers.

    :return: Explicit configuration using the SDK's CAMUNDA_* keys.
    :rtype: Dict[str, str]
    :raises KeyError: If a required setting is absent or empty.
    """
    file_values = dotenv_values(ENV_FILE)
    configuration: Dict[str, str] = {}
    for sdk_key, source_key in CAMUNDA_ENV_KEYS.items():
        value = os.environ.get(source_key, file_values.get(source_key))
        if value is None or not value.strip():
            raise KeyError(source_key)
        configuration[sdk_key] = value
    return configuration


def close_log_handlers() -> None:
    """
    Flush and close the runner's operational and invocation handlers.

    :return: None.
    :rtype: None
    """
    for logger in (WORKER_LOGGER, INVOCATION_LOGGER):
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()


def configure_logging() -> None:
    """
    Write operational logs to stdout/logs and invocation records to data.

    Directory paths are relative to this package, regardless of the working
    directory. Operational messages never include initial process variables.

    :return: None.
    :rtype: None
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    close_log_handlers()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    operational_file = logging.FileHandler(
        LOGS_DIR / "workers.log", mode="a", encoding="utf-8"
    )
    operational_file.setFormatter(formatter)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    WORKER_LOGGER.addHandler(operational_file)
    WORKER_LOGGER.addHandler(console)
    WORKER_LOGGER.setLevel(logging.INFO)
    WORKER_LOGGER.propagate = False

    records = logging.FileHandler(
        DATA_DIR / "invocations.jsonl", mode="a", encoding="utf-8"
    )
    records.setFormatter(logging.Formatter("%(message)s"))
    INVOCATION_LOGGER.addHandler(records)
    INVOCATION_LOGGER.setLevel(logging.INFO)
    INVOCATION_LOGGER.propagate = False


async def run(job_timeout_ms: int = 30000, max_concurrent_jobs: int = 10) -> None:
    """
    Start all workers with shared SHIFT endpoints and WORKERS_CAMUNDA credentials.

    :param job_timeout_ms: Camunda job activation timeout in milliseconds.
    :type job_timeout_ms: int
    :param max_concurrent_jobs: Concurrent jobs per registered worker.
    :type max_concurrent_jobs: int
    :return: None.
    :rtype: None
    :raises KeyError: If a required shared or worker setting is absent.
    """
    configure_logging()
    try:
        configuration = client_configuration()
        async with CamundaAsyncClient(
            configuration=configuration,
            logger=WORKER_LOGGER.getChild("sdk"),
        ) as client:
            workers = []
            try:
                for name, callback in WORKERS.items():
                    workers.append(client.create_job_worker(
                        config=WorkerConfig(
                            job_type=name,
                            job_timeout_milliseconds=job_timeout_ms,
                            max_concurrent_jobs=max_concurrent_jobs,
                            worker_name=f"shift-{name}",
                        ),
                        callback=callback,
                        execution_strategy="async",
                    ))
                    WORKER_LOGGER.info("Registered worker %s", name)
                WORKER_LOGGER.info(
                    "Started all %s workers; records: %s",
                    len(workers), DATA_DIR / "invocations.jsonl",
                )
                await client.run_workers()
            finally:
                for worker in workers:
                    worker.stop()
                await asyncio.sleep(0)
                WORKER_LOGGER.info("Stopped job workers")
    except Exception:
        WORKER_LOGGER.exception("Job worker runner failed")
        raise
    finally:
        close_log_handlers()


def positive_integer(value: str) -> int:
    """
    Parse a positive CLI integer.

    :param value: Command-line argument.
    :type value: str
    :return: Positive integer.
    :rtype: int
    :raises argparse.ArgumentTypeError: If the value is not a positive integer.
    """
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected a positive integer") from error
    if number <= 0:
        raise argparse.ArgumentTypeError("Expected a positive integer")
    return number


def main() -> None:
    """
    Start all ActivityDefinition job workers from the command line.

    :return: None.
    :rtype: None
    """
    parser = argparse.ArgumentParser(
        description="Start all workers using shared SHIFT and WORKERS_CAMUNDA settings."
    )
    parser.add_argument("--job-timeout-ms", type=positive_integer, default=30000)
    parser.add_argument("--max-concurrent-jobs", type=positive_integer, default=10)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.job_timeout_ms, args.max_concurrent_jobs))
    except KeyboardInterrupt:
        pass
