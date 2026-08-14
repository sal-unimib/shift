from __future__ import annotations

from dataclasses import dataclass

from src.domain.bpmn.t_choreography_task import TChoreographyTask

__NAMESPACE__ = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class ChoreographyTask(TChoreographyTask):
    class Meta:
        name = "choreographyTask"
        namespace = "http://www.omg.org/spec/BPMN/20100524/MODEL"
