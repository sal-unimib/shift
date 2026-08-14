from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree.ElementTree import QName

from src.domain.bpmn.t_root_element import TRootElement

__NAMESPACE__ = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class TPartnerEntity(TRootElement):
    class Meta:
        name = "tPartnerEntity"

    participant_ref: list[QName] = field(
        default_factory=list,
        metadata={
            "name": "participantRef",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    name: None | str = field(
        default=None,
        metadata={
            "type": "Attribute",
        },
    )
