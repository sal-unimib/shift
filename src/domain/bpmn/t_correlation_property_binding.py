from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree.ElementTree import QName

from src.domain.bpmn.t_base_element import TBaseElement
from src.domain.bpmn.t_formal_expression import TFormalExpression

__NAMESPACE__ = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class TCorrelationPropertyBinding(TBaseElement):
    class Meta:
        name = "tCorrelationPropertyBinding"

    data_path: TFormalExpression = field(
        metadata={
            "name": "dataPath",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        }
    )
    correlation_property_ref: QName = field(
        metadata={
            "name": "correlationPropertyRef",
            "type": "Attribute",
        }
    )
