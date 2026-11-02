from __future__ import annotations

from src.database.model.process_definition_record import ProcessDefinitionTemporalConstraintRecord
from src.database.model.process_definition_record import ProcessDefinitionVariableRecord, ProcessDefinitionActionVariableRecord
from sqlalchemy.orm import  Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String
from typing import List, Optional

from src.database.base import Base
from src.database.mixin import SHIFTModelMixin
from src.database.model.process_deployment_record import ProcessDeploymentRecord

class ProcessInstanceTemporalConstraintRecord(Base, SHIFTModelMixin):
    __tablename__ = "process_instance_temporal_constraint"
    
    process_instance_id: Mapped[str] = mapped_column(
        ForeignKey("process_instance.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    temporal_constraint_id: Mapped[str] = mapped_column(
        ForeignKey("process_definition_temporal_constraint.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    label: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    process_instance: Mapped[ProcessInstanceRecord] = relationship(back_populates="temporal_constraints")
    temporal_constraint: Mapped[ProcessDefinitionTemporalConstraintRecord] = relationship()
    
class ProcessInstanceVariableRecord(Base, SHIFTModelMixin):
    __tablename__ = "process_instance_variable"
    
    process_instance_id: Mapped[str] = mapped_column(
        ForeignKey("process_instance.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    process_variable_id: Mapped[str] = mapped_column(
        ForeignKey("process_definition_variable.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    process_instance: Mapped[ProcessInstanceRecord] = relationship(
        back_populates="variables"
    )
    process_variable: Mapped[ProcessDefinitionVariableRecord] = relationship()
    

class ProcessInstanceActionVariableRecord(Base, SHIFTModelMixin):
    __tablename__ = "process_instance_action_variable"

    process_instance_id: Mapped[str] = mapped_column(
        ForeignKey("process_instance.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_variable_id: Mapped[str] = mapped_column(
        ForeignKey("process_definition_action_variable.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    process_instance: Mapped["ProcessInstanceRecord"] = relationship(back_populates="action_variables")
    action_variable: Mapped[ProcessDefinitionActionVariableRecord] = relationship()


class ProcessInstanceRecord(SHIFTModelMixin, Base):
    __tablename__ = "process_instance"
    
    instance_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    deployment_id: Mapped[str] = mapped_column(
        ForeignKey("process_deployment.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    patient_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    variables: Mapped[List[ProcessInstanceVariableRecord]] = relationship(
        back_populates="process_instance",
        cascade="all, delete-orphan"
    )
    action_variables: Mapped[List[ProcessInstanceActionVariableRecord]] = relationship(
        back_populates="process_instance", cascade="all, delete-orphan"
    )
    temporal_constraints: Mapped[List[ProcessInstanceTemporalConstraintRecord]] = relationship(
        back_populates="process_instance",
        cascade="all, delete-orphan"
    )
    deployment: Mapped[ProcessDeploymentRecord] = relationship()
