from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.bpmn.human_performer import HumanPerformer
from src.domain.bpmn.performer import Performer
from src.domain.bpmn.potential_owner import PotentialOwner
from src.domain.bpmn.resource_role import ResourceRole
from src.domain.bpmn.t_callable_element import TCallableElement

__NAMESPACE__ = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class TGlobalTask(TCallableElement):
    class Meta:
        name = "tGlobalTask"

    potential_owner: list[PotentialOwner] = field(
        default_factory=list,
        metadata={
            "name": "potentialOwner",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    human_performer: list[HumanPerformer] = field(
        default_factory=list,
        metadata={
            "name": "humanPerformer",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    performer: list[Performer] = field(
        default_factory=list,
        metadata={
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    resource_role: list[ResourceRole] = field(
        default_factory=list,
        metadata={
            "name": "resourceRole",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
