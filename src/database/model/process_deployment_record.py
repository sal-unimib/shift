from src.database.model.process_definition_record import ProcessDefinitionRecord
from src.domain.enums import BPMNEngines
from sqlalchemy import ForeignKey, String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base
from src.database.mixin import SHIFTModelMixin

class ProcessDeploymentRecord(Base, SHIFTModelMixin):
    __tablename__ = "process_deployment"

    deployment_version: Mapped[str] = mapped_column(String, nullable=False)
    deployment_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    process_def_id: Mapped[str] = mapped_column(
        ForeignKey("process_definition.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    engine: Mapped[BPMNEngines] = mapped_column(Enum(BPMNEngines), nullable=False)
    process_definition: Mapped[ProcessDefinitionRecord] = relationship()
