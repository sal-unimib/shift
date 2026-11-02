from pathlib import Path
from src.utils.settings import settings
import json
from src.domain.cfg import ControlFlowGraphFactory, ControlFlowGraph, InstanceControlFlowGraph
from src.domain.enums import CFGType, BPMNEngines
from src.domain.exceptions import ArtifactReadException, ArtifactWriteException
from src.mappers.bpmn_mapper import BPMNStandardMapper
from src.mappers.camunda_enricher import CamundaBPMNEnricher
from src.domain.bpmn import Definitions
from src.utils.serializers import BPMNSerializer
from typing import Optional, Union

class ArtifactRepository:
    def __init__(self, root_dir: Optional[Union[str, Path]] = None):
        """
        Initialize filesystem storage and the BPMN serializer.

        :param root_dir: Storage directory override; None uses settings.filesystem.artifacts_dir.
        :type root_dir: Optional[Union[str, pathlib.Path]]
        """
        self.root_dir = Path(root_dir) if root_dir is not None else settings.filesystem.artifacts_dir
        self.bpmn_serializer = BPMNSerializer()

    @staticmethod
    def _part(value):
        value = str(value)
        if not value or value in ('.','..') or '/' in value or '\\' in value:
            raise ValueError('Invalid artifact identifier/version')
        return value

    def _path(self, identifier: str, version: str, suffix: str) -> Path:
        """
        Helper method for building the filesystem path

        :param identifier: Resource identifier
        :type identifier: str
        :param version: Resource version
        :type version: str
        :param suffix: Suffix for the requested resource
        :type suffix: str
        :return: Path for the resource
        :rtype: Path
        """
        # return self.root_dir / f'{self._part(identifier)}_{self._part(version)}{suffix}'
        return self.root_dir / f'{identifier}_{version}{suffix}'

    def save_cfg(self, cfg: ControlFlowGraph) -> Path:
        """
        Save CFG artifact in the filesystem as a JSON file.

        :param cfg: CFG object to save
        :type cfg: ControlFlowGraph
        :return: Saved artifact path.
        :rtype: Path
        """
        try:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            if isinstance(cfg, InstanceControlFlowGraph):
                path = self._path(cfg.id,cfg.get_specialized_version(),f'.cfg.{cfg.cfg_type.value}.json')
            else:
                path = self._path(cfg.id,cfg.version,f'.cfg.{cfg.cfg_type.value}.json')
            path.write_text(json.dumps(cfg.to_json(),indent=2),encoding='utf-8')
            return path
        except Exception as e:
            raise ArtifactWriteException(f"Something went wrong while writing {cfg.cfg_type.value} CFG artifact: {e}")

    def read_cfg(self, plan_definition_id: str, version: str, cfg_type: CFGType) -> ControlFlowGraph:
        """
        Read CFG artifact from the filesystem.

        :param plan_definition_id: PlanDefinition identifier to read
        :type plan_definition_id: str
        :param version: PlanDefinition version to read
        :type version: str
        :param cfg_type: CFG type to read
        :type cfg_type: CFGType
        :return: CFG object
        :rtype: ControlFlowGraph
        """
        try:
            path = self._path(plan_definition_id,version,f'.cfg.{cfg_type.value}.json')
            if not path.exists():
                raise ArtifactReadException(f"{cfg_type.value} CFG artifact doesn't exists for PlanDefinition {plan_definition_id} version {version}")
            return ControlFlowGraphFactory.from_json(json.loads(path.read_text(encoding='utf-8')))
        except Exception as e:
            raise ArtifactReadException(f"Something went wrong while reading {cfg_type.value} CFG for PlanDefinition {plan_definition_id} version {version}: {e}")

    def save_bpmn(self, bpmn_definition: Definitions, plan_definition_id: str, version: str, engine: Optional[BPMNEngines]=None) -> Path:
        """
        Save BPMN process definition artifact as XML BPMN2.0.

        :param bpmn_definition: BPMN definition model object
        :type bpmn_definition: Definitions
        :param plan_definition_id: PlanDefinition identifier of the BPMN definition to write
        :type plan_definition_id: str
        :param version: PlanDefinition version of the BPMN definition to write
        :type version: str
        :param engine: BPE to what BPMN is enriched for, otherwise standard BPMN2.0
        :type engine: Optional[BPMNEngines]
        :return: Saved artifact path.
        :rtype: Path
        """
        try:
            self.root_dir.mkdir(parents=True, exist_ok=True)
            suffix = f'.{engine.value}.bpmn' if engine else '.bpmn'
            path = self._path(plan_definition_id,version,suffix)
            if engine:
                path.write_text(self.bpmn_serializer.serialize(bpmn_definition, CamundaBPMNEnricher.get_namespaces()),encoding='utf-8')
            else:
                path.write_text(self.bpmn_serializer.serialize(bpmn_definition, BPMNStandardMapper.get_namespaces()),encoding='utf-8')
            return path
        except Exception as e:
            if engine:
                raise ArtifactWriteException(f"Something went wrong while writing BPMN artifact for PlanDefinition {plan_definition_id}, version {version} for engine {version}: {e}")
            else:
                raise ArtifactWriteException(f"Something went wrong while writing BPMN artifact for PlanDefinition {plan_definition_id}, version {version}: {e}")

    def read_bpmn(self, plan_definition_id: str, version: str, engine: Optional[BPMNEngines]=None) -> Definitions:
        """
        Read BPMN artifact from the filesystem.

        :param plan_definition_id: PlanDefinition identifier of the BPMN to read
        :type plan_definition_id: str
        :param version: PlanDefinition version of the BPMN to read
        :type version: str
        :param engine: BPE to what BPMN is enriched for, otherwise standard BPMN2.0
        :type engine: Optional[BPMNEngines]
        :return: CFG object
        :rtype: ControlFlowGraph
        """
        try:
            suffix = f'.{engine.value}.bpmn' if engine else '.bpmn'
            path = self._path(plan_definition_id,version,suffix)
            if not path.exists():
                if engine:
                    message = f"BPMN artifact doesn't exists for PlanDefinition {plan_definition_id} version {version} for engine {engine.value}"
                else:
                    message = f"BPMN artifact doesn't exists for PlanDefinition {plan_definition_id} version {version}"
                raise ArtifactReadException(message)
            return self.bpmn_serializer.parse(str(path),CamundaBPMNEnricher.get_namespaces())
        except Exception as e:
            if engine:
                raise ArtifactReadException(f"Something went wrong while reading BPMN artifact for PlanDefinition {plan_definition_id}, version {version} for engine {engine.value}: {e}")
            else:
                raise ArtifactReadException(f"Something went wrong while reading BPMN artifact for PlanDefinition {plan_definition_id}, version {version}: {e}")
