from __future__ import annotations

from dataclasses import dataclass

from src.domain.bpmn.t_choreography import TChoreography

__NAMESPACE__ = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class Choreography(TChoreography):
    class Meta:
        name = "choreography"
        namespace = "http://www.omg.org/spec/BPMN/20100524/MODEL"
