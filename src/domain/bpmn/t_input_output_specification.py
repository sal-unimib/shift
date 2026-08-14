from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.bpmn.data_input import DataInput
from src.domain.bpmn.data_output import DataOutput
from src.domain.bpmn.input_set import InputSet
from src.domain.bpmn.output_set import OutputSet
from src.domain.bpmn.t_base_element import TBaseElement

__NAMESPACE__ = "http://www.omg.org/spec/BPMN/20100524/MODEL"


@dataclass(kw_only=True)
class TInputOutputSpecification(TBaseElement):
    class Meta:
        name = "tInputOutputSpecification"

    data_input: list[DataInput] = field(
        default_factory=list,
        metadata={
            "name": "dataInput",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    data_output: list[DataOutput] = field(
        default_factory=list,
        metadata={
            "name": "dataOutput",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        },
    )
    input_set: list[InputSet] = field(
        default_factory=list,
        metadata={
            "name": "inputSet",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
            "min_occurs": 1,
        },
    )
    output_set: list[OutputSet] = field(
        default_factory=list,
        metadata={
            "name": "outputSet",
            "type": "Element",
            "namespace": "http://www.omg.org/spec/BPMN/20100524/MODEL",
            "min_occurs": 1,
        },
    )
