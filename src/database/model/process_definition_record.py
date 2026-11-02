from src.database.model.action_definition_record import ActionDefinitionAttributeRecord
from src.domain.enums import TemporalCategory
from typing import List, Dict, Optional
from sqlalchemy import ForeignKey, String, JSON, Enum, Integer, Boolean, UniqueConstraint, ForeignKeyConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base
from src.database.mixin import SHIFTModelMixin

class ProcessDefinitionTemporalConstraintRecord(Base, SHIFTModelMixin):
    __tablename__ = "process_definition_temporal_constraint"
    __table_args__ = (UniqueConstraint("process_definition_id", "action_link_id", "temporal_category", name="uq_definition_action_temporal"),)

    process_definition_id: Mapped[str] = mapped_column(
        ForeignKey("process_definition.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    action_link_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    element_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    temporal_category: Mapped[TemporalCategory] = mapped_column(Enum(TemporalCategory), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[Optional[Dict]] = mapped_column(JSON(none_as_null=True), nullable=True)
    process_definition: Mapped["ProcessDefinitionRecord"] = relationship(back_populates="temporal_constraints")
    
class ProcessDefinitionActionVariableRecord(Base, SHIFTModelMixin):
    __tablename__ = "process_definition_action_variable"
    __table_args__ = (UniqueConstraint("process_def_id", "action_link_id", "action_def_attribute_id", name="uq_definition_action_attribute"),)

    action_def_attribute_id: Mapped[str] = mapped_column(
        ForeignKey("action_definition_attribute.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    process_def_id: Mapped[str] = mapped_column(
        ForeignKey("process_definition.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    action_link_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    default_value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action_definition_attribute: Mapped[ActionDefinitionAttributeRecord] = relationship()
    process_definition: Mapped["ProcessDefinitionRecord"] = relationship(back_populates="action_variables")

class ProcessDefinitionVariableRecord(Base, SHIFTModelMixin):
    """Generic variable bound to BPMN and optionally to a source PlanDefinition action."""
    __tablename__ = "process_definition_variable"
    __table_args__ = (UniqueConstraint("process_def_id", "bpmn_element_id", "name", name="uq_definition_element_variable_name"),)
    process_def_id: Mapped[str] = mapped_column(ForeignKey("process_definition.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    bpmn_element_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    action_link_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    default_value: Mapped[Optional[object]] = mapped_column(JSON(none_as_null=True), nullable=True)
    process_definition: Mapped["ProcessDefinitionRecord"] = relationship(back_populates="variables")

class ProcessDefinitionRecord(Base, SHIFTModelMixin):
    __tablename__ = "process_definition"
    __table_args__ = (
        UniqueConstraint("id", "revision", name="uq_definition_id_revision"),
        ForeignKeyConstraint(["parent_definition_id", "parent_revision"],
            ["process_definition.id", "process_definition.revision"],
            name="fk_definition_parent_level", ondelete="RESTRICT"),
        CheckConstraint(
            "(parent_definition_id IS NULL AND parent_revision IS NULL AND revision = 1 AND specialization_key IS NULL) OR "
            "(parent_definition_id IS NOT NULL AND parent_revision IS NOT NULL AND parent_revision = 1 AND revision = 2 AND specialization_key IS NOT NULL)",
            name="ck_definition_single_level"),
        UniqueConstraint("plan_definition_id", "artifact_version", name="uq_definition_artifact_version"),
        UniqueConstraint("parent_definition_id", "specialization_key", name="uq_definition_specialization"),
    )
    parent_definition_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, index=True)
    parent_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    artifact_version: Mapped[str] = mapped_column(String, nullable=False)
    specialization_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    parent: Mapped[Optional["ProcessDefinitionRecord"]] = relationship(
        remote_side="[ProcessDefinitionRecord.id, ProcessDefinitionRecord.revision]", back_populates="children")
    children: Mapped[List["ProcessDefinitionRecord"]] = relationship(back_populates="parent", passive_deletes="all")

    plan_definition_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    version: Mapped[str] = mapped_column(String, nullable=False)
    action_variables: Mapped[List[ProcessDefinitionActionVariableRecord]] = relationship(
        back_populates="process_definition",
        cascade="all, delete-orphan"
    )
    variables: Mapped[List[ProcessDefinitionVariableRecord]] = relationship(back_populates="process_definition", cascade="all, delete-orphan")
    temporal_constraints: Mapped[List[ProcessDefinitionTemporalConstraintRecord]] = relationship(
        back_populates="process_definition",
        cascade="all, delete-orphan"
    )
