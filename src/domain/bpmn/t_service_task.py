from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree.ElementTree import QName

from src.domain.bpmn.t_implementation_value import TImplementationValue
from src.domain.bpmn.t_task import TTask

__NAMESPACE__ = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class TServiceTask(TTask):
    class Meta:
        name = "tServiceTask"

    implementation: str | TImplementationValue = field(
        default=TImplementationValue.WEB_SERVICE,
        metadata={
            "type": "Attribute",
        },
    )
    operation_ref: None | QName = field(
        default=None,
        metadata={
            "name": "operationRef",
            "type": "Attribute",
        },
    )
