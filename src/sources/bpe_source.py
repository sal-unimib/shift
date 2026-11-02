from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Tuple, Union

class BPESource(ABC):
    
    @abstractmethod
    async def authenticate(self) -> None:
        pass
    
    @abstractmethod
    async def deploy_bpmn(self, path: Union[str, Path]) -> Tuple[str, str]:
        pass
    
    @abstractmethod
    async def create_process_instance_by_id(
            self,
            process_definition_id: str,
            process_definition_version: str,
            variables: Dict[str, Any],
        ) -> str:
        pass

    @abstractmethod
    async def create_process_instance_by_deployment_key(
            self,
            deployment_key: str,
            variables: Dict[str, Any]
        ) -> str:
        pass
