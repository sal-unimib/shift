from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.bpmn.bpmnedge import Bpmnedge
from src.domain.bpmn.bpmnshape import Bpmnshape
from src.domain.bpmn.diagram_element import DiagramElement
from src.domain.bpmn.node import Node

__NAMESPACE__ = "http://www.omg.org/spec/DD/20100524/DI"


@dataclass(kw_only=True)
class Plane(Node):
    class Meta:
        namespace = "http://www.omg.org/spec/DD/20100524/DI"

    bpmnshape: list[Bpmnshape] = field(
        default_factory=list,
        metadata={
            "name": "BPMNShape",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/DI",
        },
    )
    bpmnedge: list[Bpmnedge] = field(
        default_factory=list,
        metadata={
            "name": "BPMNEdge",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/DI",
        },
    )
    diagram_element: list[DiagramElement] = field(
        default_factory=list,
        metadata={
            "name": "DiagramElement",
            "type": "Element",
        },
    )
