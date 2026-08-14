from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.bpmn.bounds import Bounds
from src.domain.bpmn.node import Node

__NAMESPACE__ = "http://www.omg.org/spec/DD/20100524/DI"


@dataclass(kw_only=True)
class Shape(Node):
    class Meta:
        namespace = "http://www.omg.org/spec/DD/20100524/DI"

    bounds: Bounds = field(
        metadata={
            "name": "Bounds",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/DD/20100524/DC",
        }
    )
