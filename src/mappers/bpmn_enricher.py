from abc import ABC, abstractmethod
from typing import Any, Dict

from src.domain.bpmn.definitions import Definitions


class BPMNEnricher(ABC):

    @staticmethod
    @abstractmethod
    def get_namespaces() -> Dict[str, str]:
        """
        Return engine-specific serialization namespaces.

        :return: Namespace prefixes and URIs.
        :rtype: Dict[str, str]
        """
        pass

    @staticmethod
    @abstractmethod
    def enrich(bpmn_definition: Definitions, version: str, *args: Any, **kwargs: Any) -> Definitions:
        """
        Enrich a standard BPMN using engine-specific declaration metadata.

        :param bpmn_definition: Standard BPMN model.
        :type bpmn_definition: Definitions
        :param version: Selected process definition version.
        :type version: str
        :param args: Additional engine-specific arguments.
        :type args: Any
        :param kwargs: Additional engine-specific keyword arguments.
        :type kwargs: Any
        :return: Enriched BPMN model.
        :rtype: Definitions
        """
        pass
