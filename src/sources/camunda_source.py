import copy
from httpx import Timeout
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar, Dict, Optional, Tuple, Union

from camunda_orchestration_sdk import CamundaAsyncClient
from camunda_orchestration_sdk.models.process_creation_by_id import ProcessCreationById
from camunda_orchestration_sdk.models.process_creation_by_key import ProcessCreationByKey
from camunda_orchestration_sdk.models.process_instance_creation_instruction_by_id_variables import ProcessInstanceCreationInstructionByIdVariables
from camunda_orchestration_sdk.models.process_instance_creation_instruction_by_key_variables import ProcessInstanceCreationInstructionByKeyVariables
from camunda_orchestration_sdk.semantic_types import ProcessDefinitionKey

from src.domain.exceptions import CamundaDeploymentException, CamundaInstanceException
from src.sources.bpe_source import BPESource
from src.utils.settings import CamundaSettings, settings


class CamundaSource(BPESource):
    """Share one asynchronous Camunda client per application process."""

    _instance: ClassVar[Optional["CamundaSource"]] = None
    _instance_lock: ClassVar[Lock] = Lock()

    _settings: CamundaSettings
    _client: CamundaAsyncClient
    _closed: bool

    def __new__(cls) -> "CamundaSource":
        """
        Initialize the singleton from SHIFT settings without contacting Camunda.

        :return: Shared source instance.
        :rtype: CamundaSource
        """
        with cls._instance_lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._settings = settings.camunda.model_copy(deep=True)
                instance._client = CamundaAsyncClient(
                    configuration=instance._settings.sdk_configuration(),
                    timeout=Timeout(instance._settings.request_timeout),
                    verify_ssl=instance._settings.verify_ssl,
                )
                instance._closed = False
                cls._instance = instance
            return cls._instance

    @property
    def client(self) -> CamundaAsyncClient:
        """
        Return the shared client while the source is open.

        :return: Asynchronous SDK client.
        :rtype: CamundaAsyncClient
        :raises RuntimeError: If this source has been closed.
        """
        if self._closed:
            raise RuntimeError("CamundaSource has been closed.")
        return self._client

    async def authenticate(self) -> None:
        """
        Prepare authentication using the SDK's configured provider.

        OAuth obtains or reuses a token; Basic and NONE prepare local headers.
        API requests apply authentication automatically. This does not perform
        a permissions check against Camunda.

        :return: None.
        :rtype: None
        """
        provider = self.client.auth_provider
        async_headers = getattr(provider, "aget_headers", None)
        if async_headers is not None:
            await async_headers()
        else:
            provider.get_headers()

    async def deploy_bpmn(self, path: Union[str, Path]) -> Tuple[str, str]:
        """
        Deploy a BPMN file and return only its deployment key and engine version.

        Retains the deployment-to-process key association for subsequent creation
        through this source. A single process definition must be deployed.

        :param path: Path to the BPMN file.
        :type path: Union[str, pathlib.Path]
        :return: Camunda deployment key and assigned process definition version.
        :rtype: Tuple[str, str]
        :raises CamundaDeploymentException: If file access, deployment or response mapping fails.
        """
        try:
            result = await self.client.deploy_resources_from_files(
                [Path(path)], tenant_id=self._settings.tenant_id
            )
            processes = [
                item.process_definition for item in result.deployments
                if item.process_definition is not None
            ]
            if len(processes) != 1:
                raise ValueError(
                    f"Expected one deployed process definition, received {len(processes)}."
                )
            process = processes[0]
            return result.deployment_key, str(process.process_definition_version)
        except Exception as error:
            raise CamundaDeploymentException(
                f"Cannot deploy BPMN file '{path}' to Camunda: {error}"
            ) from error

    async def create_process_instance_by_id(
        self,
        process_definition_id: str,
        process_definition_version: str,
        variables: Dict[str, Any],
    ) -> str:
        """
        Start an exact BPMN process ID/version and return its instance key.

        :param process_definition_id: BPMN process ID, such as P02.
        :type process_definition_id: str
        :param process_definition_version: Engine-assigned version.
        :type process_definition_version: str
        :param variables: Runtime variables supplied by the caller.
        :type variables: Dict[str, Any]
        :return: Camunda process instance key.
        :rtype: str
        :raises CamundaInstanceException: If instance creation or input conversion fails.
        """
        try:
            data = ProcessCreationById(
                process_definition_id=process_definition_id,
                process_definition_version=int(process_definition_version),
                variables=ProcessInstanceCreationInstructionByIdVariables.from_dict(copy.deepcopy(variables))
            )
            result = await self.client.create_process_instance(data=data)
            return str(result.process_instance_key)
        except Exception as error:
            raise CamundaInstanceException(
                f"Cannot create Camunda instance for process '{process_definition_id}' "
                f"version {process_definition_version}: {error}"
            ) from error

    async def create_process_instance_by_deployment_key(
        self,
        deployment_key: str,
        variables: Dict[str, Any]
    ) -> str:
        """
        Start the process associated with a deployment made by this source.

        Camunda requires a process definition key, not the deployment key.
        This method resolves the association retained when deploy_bpmn succeeds.

        :param deployment_key: Actual deployment key returned by deploy_bpmn.
        :type deployment_key: str
        :param variables: Runtime variables supplied by the caller.
        :type variables: Dict[str, Any]
        :return: Camunda process instance key.
        :rtype: str
        :raises CamundaInstanceException: If the deployment is unknown or creation fails.
        """
        try:
            process_key = self._deployment_process_keys.get(deployment_key)
            if process_key is None:
                raise ValueError(
                    "The deployment key is not known to this source. "
                    "For a deployment loaded after restart, create by process ID and version."
                )
            tenant = self._settings.tenant_id
            data = ProcessCreationByKey(
                process_definition_key=ProcessDefinitionKey(process_key),
                variables=ProcessInstanceCreationInstructionByKeyVariables.from_dict(copy.deepcopy(variables))
            )
            result = await self.client.create_process_instance(data=data)
            return str(result.process_instance_key)
        except Exception as error:
            raise CamundaInstanceException(
                f"Cannot create Camunda instance for deployment '{deployment_key}': {error}"
            ) from error

    async def aclose(self) -> None:
        """
        Close API and authentication clients and release the singleton.

        Call after in-flight application requests have finished. Existing references
        become closed; the next construction can initialize a new source.

        :return: None.
        :rtype: None
        """
        if self._closed:
            return
        self._closed = True
        try:
            await self._client.aclose()
        finally:
            with type(self)._instance_lock:
                if type(self)._instance is self:
                    type(self)._instance = None

    @classmethod
    async def close(cls) -> None:
        """
        Close the existing singleton without creating a client solely for shutdown.

        :return: None.
        :rtype: None
        """
        instance = cls._instance
        if instance is not None:
            await instance.aclose()
