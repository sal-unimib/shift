from typing import List, Optional

from src.database.model.process_instance_record import (
    ProcessInstanceRecord, ProcessInstanceVariableRecord,
    ProcessInstanceActionVariableRecord, ProcessInstanceTemporalConstraintRecord,
)


class ProcessInstanceVariable:
    """Value of a generic process-definition variable."""

    def __init__(self, id: str, process_variable_id: str, value: Optional[str]):
        """
        Initialize a generic instance variable.

        :param id: SHIFT variable value ID.
        :type id: str
        :param process_variable_id: Referenced generic definition variable ID.
        :type process_variable_id: str
        :param value: Resolved textual value or None.
        :type value: Optional[str]
        """
        self.id = id
        self.process_variable_id = process_variable_id
        self.value = value

    def to_record(self) -> ProcessInstanceVariableRecord:
        """
        Convert a generic instance variable into a database record.

        :return: Generic variable record.
        :rtype: ProcessInstanceVariableRecord
        """
        return ProcessInstanceVariableRecord(
            id=self.id, process_variable_id=self.process_variable_id, value=self.value
        )

    @classmethod
    def from_record(cls, record: ProcessInstanceVariableRecord) -> "ProcessInstanceVariable":
        """
        Restore a generic instance variable.

        :param record: Persisted variable record.
        :type record: ProcessInstanceVariableRecord
        :return: Domain variable.
        :rtype: ProcessInstanceVariable
        """
        return cls(record.id, record.process_variable_id, record.value)


class ProcessInstanceActionVariable:
    """Value of an action-specific process-definition variable."""

    def __init__(self, id: str, action_variable_id: str, value: Optional[str]):
        """
        Initialize an action instance variable.

        :param id: SHIFT variable value ID.
        :type id: str
        :param action_variable_id: Referenced action definition variable ID.
        :type action_variable_id: str
        :param value: Resolved textual value or None.
        :type value: Optional[str]
        """
        self.id = id
        self.action_variable_id = action_variable_id
        self.value = value

    def to_record(self) -> ProcessInstanceActionVariableRecord:
        """
        Convert an action instance variable into a database record.

        :return: Action variable record.
        :rtype: ProcessInstanceActionVariableRecord
        """
        return ProcessInstanceActionVariableRecord(
            id=self.id, action_variable_id=self.action_variable_id, value=self.value
        )

    @classmethod
    def from_record(cls, record: ProcessInstanceActionVariableRecord) -> "ProcessInstanceActionVariable":
        """
        Restore an action instance variable.

        :param record: Persisted action variable record.
        :type record: ProcessInstanceActionVariableRecord
        :return: Domain action variable.
        :rtype: ProcessInstanceActionVariable
        """
        return cls(record.id, record.action_variable_id, record.value)


class ProcessInstanceTemporalConstraint:
    """Resolved value of a process-definition temporal declaration."""

    def __init__(
        self, id: str, temporal_constraint_id: str, label: str, value: Optional[str]
    ):
        """
        Initialize an instance temporal value.

        :param id: SHIFT temporal value ID.
        :type id: str
        :param temporal_constraint_id: Referenced definition constraint ID.
        :type temporal_constraint_id: str
        :param label: Constraint label.
        :type label: str
        :param value: Resolved textual value or None.
        :type value: Optional[str]
        """
        self.id = id
        self.temporal_constraint_id = temporal_constraint_id
        self.label = label
        self.value = value

    def to_record(self) -> ProcessInstanceTemporalConstraintRecord:
        """
        Convert an instance temporal value into a database record.

        :return: Temporal constraint record.
        :rtype: ProcessInstanceTemporalConstraintRecord
        """
        return ProcessInstanceTemporalConstraintRecord(
            id=self.id, temporal_constraint_id=self.temporal_constraint_id,
            label=self.label, value=self.value,
        )

    @classmethod
    def from_record(cls, record: ProcessInstanceTemporalConstraintRecord) -> "ProcessInstanceTemporalConstraint":
        """
        Restore an instance temporal constraint.

        :param record: Persisted temporal value.
        :type record: ProcessInstanceTemporalConstraintRecord
        :return: Domain temporal value.
        :rtype: ProcessInstanceTemporalConstraint
        """
        return cls(record.id, record.temporal_constraint_id, record.label, record.value)


class ProcessInstance:
    """SHIFT instance with separate generic, action and temporal values."""

    def __init__(
        self,
        id: str,
        instance_key: str,
        deployment_id: str,
        patient_id: str,
        variables: Optional[List[ProcessInstanceVariable]] = None,
        action_variables: Optional[List[ProcessInstanceActionVariable]] = None,
        temporal_constraints: Optional[List[ProcessInstanceTemporalConstraint]] = None,
    ):
        """
        Initialize an instance with independently owned variable collections.

        :param id: SHIFT instance ID.
        :type id: str
        :param instance_key: Camunda process instance key.
        :type instance_key: str
        :param deployment_id: Referenced SHIFT deployment ID.
        :type deployment_id: str
        :param patient_id: Patient identifier.
        :type patient_id: str
        :param variables: Generic variable values.
        :type variables: Optional[List[ProcessInstanceVariable]]
        :param action_variables: Action variable values.
        :type action_variables: Optional[List[ProcessInstanceActionVariable]]
        :param temporal_constraints: Temporal values.
        :type temporal_constraints: Optional[List[ProcessInstanceTemporalConstraint]]
        """
        self.id = id
        self.instance_key = instance_key
        self.deployment_id = deployment_id
        self.patient_id = patient_id
        self.variables = list(variables or [])
        self.action_variables = list(action_variables or [])
        self.temporal_constraints = list(temporal_constraints or [])

    def to_record(self) -> ProcessInstanceRecord:
        """
        Convert the instance and all three declaration-value collections.

        :return: Instance record with its dependent variable records.
        :rtype: ProcessInstanceRecord
        """
        return ProcessInstanceRecord(
            id=self.id, instance_key=self.instance_key, deployment_id=self.deployment_id,
            patient_id=self.patient_id,
            variables=[variable.to_record() for variable in self.variables],
            action_variables=[variable.to_record() for variable in self.action_variables],
            temporal_constraints=[constraint.to_record() for constraint in self.temporal_constraints],
        )

    @classmethod
    def from_record(cls, record: ProcessInstanceRecord) -> "ProcessInstance":
        """
        Restore an instance whose dependent collections have been eagerly loaded.

        :param record: Persisted instance record.
        :type record: ProcessInstanceRecord
        :return: Domain instance and its generic, action and temporal values.
        :rtype: ProcessInstance
        """
        return cls(
            id=record.id, instance_key=record.instance_key, deployment_id=record.deployment_id,
            patient_id=record.patient_id,
            variables=[ProcessInstanceVariable.from_record(value) for value in record.variables],
            action_variables=[ProcessInstanceActionVariable.from_record(value) for value in record.action_variables],
            temporal_constraints=[ProcessInstanceTemporalConstraint.from_record(value) for value in record.temporal_constraints],
        )
