from __future__ import annotations
import copy
from dataclasses import dataclass
from typing import Any, Optional
from src.utils.definition_identifiers import (
    process_definition_id, process_action_variable_id,
    process_temporal_variable_id, process_variable_id,
)
from src.database.model.process_definition_record import (
    ProcessDefinitionRecord, ProcessDefinitionActionVariableRecord, ProcessDefinitionVariableRecord,
    ProcessDefinitionTemporalConstraintRecord,
)
from src.domain.action_definition import ActionDefinitionAttribute
from src.domain.enums import TemporalCategory
from src.domain.temporal_constraint import TemporalConstraint


@dataclass
class ProcessDefinitionActionVariable:
    id: str
    action_definition_attribute: ActionDefinitionAttribute
    action_link_id: str
    default_value: Optional[str] = None
    is_active: bool = True

    @property
    def key(self):
        return self.action_link_id, self.action_definition_attribute.id

    @staticmethod
    def from_record(record):
        return ProcessDefinitionActionVariable(record.id,
            ActionDefinitionAttribute.from_record(record.action_definition_attribute),
            record.action_link_id, record.default_value, record.active)

    def to_record(self):
        return ProcessDefinitionActionVariableRecord(id=self.id,
            action_def_attribute_id=self.action_definition_attribute.id,
            action_link_id=self.action_link_id, default_value=self.default_value, active=self.is_active)


@dataclass
class ProcessDefinitionVariable:
    """BPMN binding; action_link_id references action.id in the owning PlanDefinition."""
    id: str
    name: str
    bpmn_element_id: str
    action_link_id: Optional[str] = None
    default_value: Any = None
    is_active: bool = True
    prefix: str = "pgv"

    @classmethod
    def from_record(cls, record):
        """
        Convert a generic variable record and recover its prefix, including named condition bindings.

        :param record: Persisted generic variable record.
        :type record: ProcessDefinitionVariableRecord
        :return: Generic declaration including its prefix and optional FHIR action binding.
        :rtype: ProcessDefinitionVariable
        """
        suffix = f"_{record.process_def_id}_{record.bpmn_element_id}"
        named_suffix = suffix + "_" + record.name
        if record.id.endswith(named_suffix):
            prefix = record.id[:-len(named_suffix)]
        else:
            prefix = record.id[:-len(suffix)] if record.id.endswith(suffix) else "pgv"
        return cls(record.id, record.name, record.bpmn_element_id, record.action_link_id,
                   copy.deepcopy(record.default_value), record.active, prefix)

    def to_record(self):
        return ProcessDefinitionVariableRecord(id=self.id, name=self.name,
            bpmn_element_id=self.bpmn_element_id, action_link_id=self.action_link_id,
            default_value=copy.deepcopy(self.default_value), active=self.is_active)


@dataclass
class ProcessDefinitionTemporalVariable:
    """A declaration can have no default; patient-specific values belong to the instance."""
    id: str
    action_link_id: str
    temporal_category: TemporalCategory
    element_id: Optional[str] = None
    label: str = ''
    default_value: Optional[dict] = None
    is_active: bool = True

    @property
    def key(self):
        return self.action_link_id, self.temporal_category

    @property
    def action_id(self):
        return self.action_link_id

    @classmethod
    def from_constraint(cls, constraint, element_id=None):
        return cls('', constraint.action_id, constraint.temporal_category, element_id,
                   constraint.label or '', copy.deepcopy(constraint.to_json()))

    @classmethod
    def from_record(cls, record):
        return cls(record.id, record.action_link_id, record.temporal_category,
                   record.element_id, record.label, copy.deepcopy(record.value), record.is_active)

    def to_record(self):
        return ProcessDefinitionTemporalConstraintRecord(id=self.id,
            action_link_id=self.action_link_id, element_id=self.element_id,
            temporal_category=self.temporal_category, label=self.label,
            value=copy.deepcopy(self.default_value), is_active=self.is_active)

    def to_json(self):
        return copy.deepcopy(self.default_value)

    def to_constraint(self):
        return TemporalConstraint.from_json(self.default_value) if self.default_value is not None else None


class ProcessDefinition:
    def __init__(self, id, plan_definition_id, name, title, description, version,
                 action_variables=None, temporal_constraints=None, *, variables=None, parent_definition_id=None,
                 revision=1, artifact_version=None, specialization_key=None):
        self.id, self.plan_definition_id = id, plan_definition_id
        self.name, self.title, self.description = name, title, description
        self.version = version  # Caller-supplied definition version; no specialization suffix is inferred.
        self.parent_definition_id, self.revision = parent_definition_id, revision
        self.artifact_version = artifact_version or version
        self.specialization_key = specialization_key
        self.action_variables = list(action_variables or [])
        self.variables = list(variables or [])
        self.temporal_constraints = [x if isinstance(x, ProcessDefinitionTemporalVariable)
            else ProcessDefinitionTemporalVariable.from_constraint(x) for x in (temporal_constraints or [])]

    @staticmethod
    def from_record(record):
        return ProcessDefinition(id=record.id, plan_definition_id=record.plan_definition_id,
            name=record.name, title=record.title, description=record.description,
            version=record.version,
            action_variables=[ProcessDefinitionActionVariable.from_record(x) for x in record.action_variables],
            variables=[ProcessDefinitionVariable.from_record(x) for x in record.variables],
            temporal_constraints=[ProcessDefinitionTemporalVariable.from_record(x) for x in record.temporal_constraints],
            parent_definition_id=record.parent_definition_id, revision=record.revision,
            artifact_version=record.artifact_version, specialization_key=record.specialization_key)

    def to_record(self):
        """
        Convert the definition and declarations using readable, versioned identifiers.

        The caller supplies the version; no patient-specific version is generated. Condition bindings include their variable name to distinguish declarations on the same BPMN element.

        :return: Definition record with action, generic and temporal declarations.
        :rtype: ProcessDefinitionRecord
        """
        self.id = process_definition_id(self.plan_definition_id, self.version)
        vs=[]
        for variable in self.action_variables:
            record=variable.to_record()
            record.id=process_action_variable_id(self.plan_definition_id, self.version, *variable.key)
            variable.id=record.id
            vs.append(record)
        gs=[]
        for variable in self.variables:
            record=variable.to_record()
            record.id=process_variable_id(variable.prefix, self.plan_definition_id, self.version,
                variable.bpmn_element_id, variable.name if variable.prefix == 'condvar' else None)
            variable.id=record.id
            gs.append(record)
        ts=[]
        for variable in self.temporal_constraints:
            record=variable.to_record()
            record.id=process_temporal_variable_id(self.plan_definition_id, self.version, variable.action_link_id, variable.temporal_category)
            variable.id=record.id
            ts.append(record)
        return ProcessDefinitionRecord(id=self.id, plan_definition_id=self.plan_definition_id,
            name=self.name, title=self.title, description=self.description, version=self.version,
            parent_definition_id=self.parent_definition_id, parent_revision=1 if self.parent_definition_id else None, revision=self.revision,
            artifact_version=self.artifact_version, specialization_key=self.specialization_key,
            action_variables=vs, variables=gs, temporal_constraints=ts)
