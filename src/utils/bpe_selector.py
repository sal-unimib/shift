from typing import Tuple, Type

from src.domain.bpmn.definitions import Definitions
from src.domain.enums import BPMNEngines
from src.mappers.camunda_enricher import CamundaBPMNEnricher
from src.mappers.bpmn_enricher import BPMNEnricher
from src.sources.bpe_source import BPESource
from src.sources.camunda_source import CamundaSource

class BPESelector:

    @staticmethod
    def select_bpe(bpmn_process: Definitions) -> Tuple[BPMNEngines, Type[BPMNEnricher], BPESource]:
        return BPMNEngines.CAMUNDA, CamundaBPMNEnricher, CamundaSource()
