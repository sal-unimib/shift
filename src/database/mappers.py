from typing import Optional
from src.utils.definition_identifiers import contract_id
from src.domain.enums import TemporalCategory
from src.domain.temporal_constraint import (
    TemporalConstraint,
    StandardCycleTemporalConstraint,
    InstanceCycleTemporalConstraint,
    ExecutionDurationTemporalConstraint,
    ExecutionBoundTemporalConstraint,
    ExactTemporalConstraint,
    OffsetTemporalConstraint,
    ExecutionIterationTemporalConstraint,
    KeepAliveBoundTemporalConstraint

)
from src.database.model.process_definition_record import ProcessDefinitionTemporalConstraintRecord

class TemporalConstraintRecordMapper:

    @staticmethod
    def to_record(
        temporal_constraint: TemporalConstraint,
        process_definition_id: str,
        action_id : str,
        element_id : str,
    ) -> ProcessDefinitionTemporalConstraintRecord:
        """
        Convert a temporal constraint using the same readable ID as definition mapping.

        :param temporal_constraint: SHIFT temporal constraint to persist.
        :type temporal_constraint: TemporalConstraint
        :param process_definition_id: Owner ID in the format <plan_id>_<version>.
        :type process_definition_id: str
        :param action_id: FHIR action linkId or shared-action identifier.
        :type action_id: str
        :param element_id: Associated BPMN element identifier.
        :type element_id: str
        :return: Record identified by ptv_<plan_id>_<version>_<action_id>_<category>.
        :rtype: ProcessDefinitionTemporalConstraintRecord
        """


        return ProcessDefinitionTemporalConstraintRecord(
            id=contract_id('ptv', process_definition_id, action_id, temporal_constraint.temporal_category.value),
            process_definition_id=process_definition_id,
            action_link_id=action_id,
            element_id=element_id,
            temporal_category=temporal_constraint.temporal_category,
            label=temporal_constraint.label,
            value=temporal_constraint.to_json(),
        )
    
    @staticmethod
    def from_record(record: ProcessDefinitionTemporalConstraintRecord) -> Optional[TemporalConstraint]:
        """
        Restore a concrete constraint from a persisted default, if one is present.

        :param record: Temporal declaration with an optional serialized default.
        :type record: ProcessDefinitionTemporalConstraintRecord
        :return: Concrete default constraint, or None for an unvalued declaration.
        :rtype: Optional[TemporalConstraint]
        :raises ValueError: If the record category and serialized category disagree.
        """
        if record.value is None:
            return None
        constraint = TemporalConstraint.from_json(record.value)
        if constraint.temporal_category != record.temporal_category:
            raise ValueError("The stored temporal category does not match its value.")
        return constraint
