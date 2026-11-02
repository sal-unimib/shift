from src.domain.enums import BPMNEngines
from src.domain.process_definition import ProcessDefinition
from src.database.model.process_deployment_record import ProcessDeploymentRecord

class ProcessDeployment:
    """Represents a deployment of a process definition to a BPM engine."""

    id: str
    deployment_key: str
    deployment_version: str
    process_definition: ProcessDefinition
    engine: BPMNEngines

    def __init__(
        self,
        id: str,
        deployment_key: str,
        deployment_version: str,
        process_definition: ProcessDefinition,
        engine: BPMNEngines
    ):
        """
        Initialize a SHIFT deployment linked to its process definition.

        :param id: SHIFT deployment ID.
        :type id: str
        :param deployment_key: Actual Camunda deployment key.
        :type deployment_key: str
        :param deployment_version: Engine-assigned process definition version.
        :type deployment_version: str
        :param process_definition: Referenced SHIFT definition.
        :type process_definition: ProcessDefinition
        :param engine: Target process engine.
        :type engine: BPMNEngines
        """
        self.id = id
        self.deployment_key = deployment_key
        self.deployment_version = deployment_version
        self.process_definition = process_definition
        self.engine = engine



    def to_record(self) -> ProcessDeploymentRecord:
        """
        Convert a deployment into a database record linked to its definition.

        :return: Deployment record.
        :rtype: ProcessDeploymentRecord
        """
        return ProcessDeploymentRecord(
            id=self.id, deployment_key=self.deployment_key,
            deployment_version=self.deployment_version,
            process_def_id=self.process_definition.id, engine=self.engine,
        )

    @classmethod
    def from_record(cls, record: ProcessDeploymentRecord) -> "ProcessDeployment":
        """
        Restore a deployment with its eagerly loaded process definition.

        :param record: Persisted deployment and definition.
        :type record: ProcessDeploymentRecord
        :return: Domain deployment.
        :rtype: ProcessDeployment
        """
        return cls(
            id=record.id, deployment_key=record.deployment_key,
            deployment_version=record.deployment_version,
            process_definition=ProcessDefinition.from_record(record.process_definition),
            engine=record.engine,
        )
