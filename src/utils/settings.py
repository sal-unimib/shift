from datetime import time
from typing import Any, Dict, List, Literal, Optional
from src.domain.enums import EventTimingValueSet
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
import os

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DBSettings(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    url: SecretStr
    echo: bool = False
    pool_size: int = Field(default=5, ge=1)
    max_overflow: int = Field(default=10, ge=0)
    pool_timeout: float = Field(default=30.0, gt=0)

    @field_validator('url')
    @classmethod
    def validate_url(cls, value: SecretStr) -> SecretStr:
        """
        Validate and normalize a PostgreSQL connection URL for the asyncpg driver.

        Accepts postgresql URLs and rejects missing database names, malformed URLs and other drivers.

        :param value: Database URL with protected credentials.
        :type value: pydantic.SecretStr
        :return: Validated URL using the postgresql+asyncpg driver.
        :rtype: pydantic.SecretStr
        """
        try:
            url = make_url(value.get_secret_value().strip())
            if url.drivername == 'postgresql':
                url = url.set(drivername='postgresql+asyncpg')
            if url.drivername != 'postgresql+asyncpg' or not url.database:
                raise ValueError
        except (ArgumentError, ValueError, TypeError):
            raise ValueError('DB URL must specify a PostgreSQL database using asyncpg.') from None
        return SecretStr(url.render_as_string(hide_password=False))

    @property
    def sqlalchemy_url(self) -> URL:
        """
        Build the SQLAlchemy URL used to configure the asynchronous engine.

        :return: Parsed PostgreSQL URL, including credentials needed by the driver.
        :rtype: sqlalchemy.engine.URL
        """
        return make_url(self.url.get_secret_value())


def _default_when_times() -> Dict[EventTimingValueSet, List[time]]:
    """Return independent conventional UTC clock times for every event-timing code.

    :return: Clock-time policy; IMD is immediate and has no daily clock time.
    :rtype: Dict[EventTimingValueSet, List[datetime.time]]
    """
    values = {
        "MORN": ["09:00:00"], "MORN.early": ["07:00:00"], "MORN.late": ["11:00:00"],
        "NOON": ["12:00:00"], "AFT": ["15:00:00"], "AFT.early": ["14:00:00"],
        "AFT.late": ["17:00:00"], "EVE": ["19:00:00"], "EVE.early": ["18:00:00"],
        "EVE.late": ["21:00:00"], "NIGHT": ["23:00:00"], "PHS": ["23:00:00"],
        "IMD": [], "HS": ["22:00:00"], "WAKE": ["07:00:00"],
        "C": ["08:00:00", "13:00:00", "20:00:00"], "CM": ["08:00:00"],
        "CD": ["13:00:00"], "CV": ["20:00:00"],
        "AC": ["07:30:00", "12:30:00", "19:30:00"], "ACM": ["07:30:00"],
        "ACD": ["12:30:00"], "ACV": ["19:30:00"],
        "PC": ["08:30:00", "13:30:00", "20:30:00"], "PCM": ["08:30:00"],
        "PCD": ["13:30:00"], "PCV": ["20:30:00"],
    }
    return {EventTimingValueSet(code): [time.fromisoformat(t) for t in times]
            for code, times in values.items()}


class TemporalSettings(BaseModel):
    when_times: Dict[EventTimingValueSet, List[time]] = Field(default_factory=_default_when_times)
    sleep_time: time = time(22, 30)

    @field_validator('when_times', mode='before')
    @classmethod
    def merge_when_times(cls, value: Any) -> Dict[EventTimingValueSet, Any]:
        """Merge partial clock overrides with the complete default policy.

        :param value: Mapping from FHIR event-timing codes to clock-time lists.
        :type value: Any
        :return: Complete policy for subsequent Pydantic time validation.
        :rtype: Dict[EventTimingValueSet, Any]
        """
        if not isinstance(value, dict):
            raise ValueError('when_times must be a mapping of codes to time lists')
        return {**_default_when_times(), **{EventTimingValueSet(k): v for k, v in value.items()}}

    @field_validator('when_times')
    @classmethod
    def validate_when_times(cls, value: Dict[EventTimingValueSet, List[time]]) -> Dict[EventTimingValueSet, List[time]]:
        """Validate complete UTC clock conventions while preserving immediate execution.

        :param value: Parsed event-time mapping.
        :type value: Dict[EventTimingValueSet, List[datetime.time]]
        :return: Validated clock policy.
        :rtype: Dict[EventTimingValueSet, List[datetime.time]]
        """
        for code, times in value.items():
            if (code == EventTimingValueSet.IMD and times) or (code != EventTimingValueSet.IMD and not times):
                raise ValueError('Only IMD must have an empty clock-time list')
            for clock in times:
                cls.validate_sleep_time(clock)
        return value

    @field_validator('sleep_time')
    @classmethod
    def validate_sleep_time(cls, value: time) -> time:
        """Require whole-second UTC clock conventions without embedded offsets.

        :param value: Clock time interpreted by the UTC scheduling policy.
        :type value: datetime.time
        :return: Validated clock time.
        :rtype: datetime.time
        """
        if value.tzinfo is not None or value.microsecond:
            raise ValueError('Clock conventions require whole seconds without timezone offsets; cron uses UTC')
        return value


class FilesystemSettings(BaseModel):
    artifacts_dir: Path = PROJECT_ROOT / 'data/storage/fs'
    ontology_dir: Path = PROJECT_ROOT / 'data/ontology'
    bpmn_schema_dir: Path = PROJECT_ROOT / 'data/bpmn_schema'
    logs_dir: Path = PROJECT_ROOT / 'logs'

    @field_validator('artifacts_dir', 'ontology_dir', 'bpmn_schema_dir', 'logs_dir')
    @classmethod
    def resolve_path(cls, value: Path) -> Path:
        """
        Resolve a configured filesystem path against the SHIFT project directory.

        :param value: Absolute or project-relative path; home-directory notation is supported.
        :type value: pathlib.Path
        :return: Expanded absolute filesystem path.
        :rtype: pathlib.Path
        """
        value = value.expanduser()
        return (PROJECT_ROOT / value).resolve() if not value.is_absolute() else value.resolve()


class CamundaSettings(BaseModel):
    """Connection and authentication settings for the Camunda REST client."""

    model_config = ConfigDict(hide_input_in_errors=True)

    rest_address: str = "http://localhost:8080/v2"
    auth_strategy: Literal["NONE", "BASIC", "OAUTH"] = "NONE"
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    client_id: Optional[str] = None
    client_secret: Optional[SecretStr] = None
    oauth_url: str = "https://login.cloud.camunda.io/oauth/token"
    token_audience: str = "zeebe.camunda.io"
    tenant_id: Optional[str] = None
    request_timeout: float = Field(default=30.0, gt=0)
    verify_ssl: bool = True

    @field_validator("rest_address", "oauth_url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        """
        Require an absolute HTTP(S) endpoint without query or fragment.

        :param value: Configured REST or OAuth endpoint.
        :type value: str
        :return: Endpoint without a trailing slash.
        :rtype: str
        """
        try:
            parsed = urlsplit(value)
            _ = parsed.port
            valid = (
                parsed.scheme in {"http", "https"} and parsed.hostname
                and not parsed.query and not parsed.fragment
                and not any(char.isspace() for char in value)
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Camunda endpoints must be absolute HTTP(S) URLs.")
        return value.rstrip("/")

    @field_validator("auth_strategy", mode="before")
    @classmethod
    def normalize_auth_strategy(cls, value: str) -> str:
        """
        Normalize the configured authentication strategy.

        :param value: Authentication strategy name.
        :type value: str
        :return: Uppercase strategy name.
        :rtype: str
        """
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_credentials(self) -> "CamundaSettings":
        """
        Require credentials for the selected authentication strategy.

        :return: Validated Camunda configuration.
        :rtype: CamundaSettings
        """
        if self.auth_strategy == "BASIC" and (
            not self.username or self.password is None or not self.password.get_secret_value()
        ):
            raise ValueError("Camunda BASIC authentication requires username and password.")
        if self.auth_strategy == "OAUTH" and (
            not self.client_id or self.client_secret is None or not self.client_secret.get_secret_value()
        ):
            raise ValueError("Camunda OAUTH authentication requires client_id and client_secret.")
        return self

    def sdk_configuration(self) -> Dict[str, Any]:
        """
        Build explicit SDK configuration without changing process environment.

        :return: SDK settings containing unwrapped credentials for client construction only.
        :rtype: Dict[str, Any]
        """
        return {
            "CAMUNDA_REST_ADDRESS": self.rest_address,
            "CAMUNDA_AUTH_STRATEGY": self.auth_strategy,
            "CAMUNDA_BASIC_AUTH_USERNAME": self.username,
            "CAMUNDA_BASIC_AUTH_PASSWORD": self.password.get_secret_value() if self.password else None,
            "CAMUNDA_CLIENT_ID": self.client_id,
            "CAMUNDA_CLIENT_SECRET": self.client_secret.get_secret_value() if self.client_secret else None,
            "CAMUNDA_OAUTH_URL": self.oauth_url,
            "CAMUNDA_TOKEN_AUDIENCE": self.token_audience,
            "CAMUNDA_TENANT_ID": self.tenant_id,
            "CAMUNDA_TOKEN_DISK_CACHE_DISABLE": True,
            "CAMUNDA_TOKEN_CACHE_DIR": None,
            "CAMUNDA_SDK_LOG_LEVEL": "error",
            "CAMUNDA_LOAD_ENVFILE": False,
        }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix='SHIFT_', env_nested_delimiter='__',
        env_file=PROJECT_ROOT / '.env', env_file_encoding='utf-8',
        extra='ignore', hide_input_in_errors=True,
    )
    db: DBSettings
    camunda: CamundaSettings = Field(default_factory=CamundaSettings)
    temporal: TemporalSettings = Field(default_factory=TemporalSettings)
    filesystem: FilesystemSettings = Field(default_factory=FilesystemSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Load and cache the application settings from environment variables and a dotenv file.

    Environment variables override dotenv values. SHIFT_ENV_FILE selects an alternative file; otherwise the project .env is used. An explicitly selected file must exist.

    :return: Validated database and filesystem settings.
    :rtype: Settings
    """
    config_file = os.environ.get('SHIFT_ENV_FILE')
    if config_file:
        path = Path(config_file).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path.is_file():
            raise FileNotFoundError('SHIFT_ENV_FILE does not refer to an existing configuration file.')
        return Settings(_env_file=path)
    return Settings()


settings = get_settings()
