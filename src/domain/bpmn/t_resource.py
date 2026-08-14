from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.bpmn.resource_parameter import ResourceParameter
from src.domain.bpmn.t_root_element import TRootElement

__NAMESPACE__ = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class TResource(TRootElement):
    class Meta:
        name = "tResource"

    resource_parameter: list[ResourceParameter] = field(
        default_factory=list,
        metadata={
            "name": "resourceParameter",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    name: str = field(
        metadata={
            "type": "Attribute",
        }
    )
