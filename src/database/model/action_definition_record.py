from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List

from src.database.base import Base
from src.database.mixin import SHIFTModelMixin

class ActionDefinitionAttributeRecord(Base, SHIFTModelMixin):
    __tablename__ = "action_definition_attribute"

    action_definition_id: Mapped[str] = mapped_column(
        ForeignKey("action_definition.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    path: Mapped[str] = mapped_column(String, nullable=False)
    expression: Mapped[str] = mapped_column(String, nullable=False)
    fhir_type: Mapped[str] = mapped_column(String, nullable=False)
    action_definition: Mapped["ActionDefinitionRecord"] = relationship(back_populates="attributes")

class ActionDefinitionRecord(Base, SHIFTModelMixin):
    __tablename__ = "action_definition"

    name: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    request_kind: Mapped[str] = mapped_column(String, nullable=False)
    attributes: Mapped[List[ActionDefinitionAttributeRecord]] = relationship(
        back_populates="action_definition",
        cascade="all, delete-orphan"
    )
