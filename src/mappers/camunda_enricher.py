import copy
import json
import re
from dataclasses import fields
from typing import Any, Dict, Iterator, List, Union

from src.domain import bpmn as bpmn_model
from src.domain.bpe_extensions import camunda as camunda_extensions_model
from src.domain.exceptions import BPMNGenerationException
from src.mappers.bpmn_enricher import BPMNEnricher

BPMNScope = Union[bpmn_model.Process, bpmn_model.SubProcess]


class CamundaBPMNEnricher(BPMNEnricher):
    """Bind declaration-only process data to Camunda tasks, timers and forms."""

    @staticmethod
    def get_namespaces() -> Dict[str, str]:
        """
        Return namespaces used to serialize Camunda BPMN extensions.

        :return: Namespace prefixes and URIs.
        :rtype: Dict[str, str]
        """
        return {
            "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
            "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
            "di": "http://www.omg.org/spec/DD/20100524/DI",
            "dc": "http://www.omg.org/spec/DD/20100524/DC",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "zeebe": "http://camunda.org/schema/zeebe/1.0",
        }

    @staticmethod
    def _scopes(scope: BPMNScope) -> Iterator[BPMNScope]:
        """
        Visit a process and its nested subprocesses.

        :param scope: Root process or nested subprocess.
        :type scope: Union[bpmn_model.Process, bpmn_model.SubProcess]
        :return: Recursive scope iterator.
        :rtype: Iterator[Union[bpmn_model.Process, bpmn_model.SubProcess]]
        """
        yield scope
        for subprocess in scope.sub_process:
            yield from CamundaBPMNEnricher._scopes(subprocess)

    @staticmethod
    def _extend(element: Any, extension: Any) -> None:
        """
        Replace an extension of the same type while preserving other extensions.

        :param element: BPMN element receiving the extension.
        :type element: Any
        :param extension: New Camunda extension.
        :type extension: Any
        :return: None.
        :rtype: None
        """
        if element.extension_elements is None:
            element.extension_elements = bpmn_model.ExtensionElements()
        values = element.extension_elements.other_element
        values[:] = [old for old in values if not isinstance(old, type(extension))]
        values.append(extension)

    @staticmethod
    def _feel_name(name: str) -> str:
        """
        Encode a runtime name as a FEEL identifier.

        :param name: Runtime variable name.
        :type name: str
        :return: Plain or escaped FEEL identifier.
        :rtype: str
        """
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            return name
        return "`" + name.replace("\\", "\\\\").replace("`", "\\`") + "`"

    @staticmethod
    def _condition(expression: str) -> str:
        """
        Convert percent-variable references while preserving quoted literals.

        This supports the existing simple comparison expressions, not arbitrary
        evaluation or translation of the FHIRPath language.

        :param expression: Current condition expression.
        :type expression: str
        :return: Camunda expression using runtime condition variable names.
        :rtype: str
        """
        pattern = re.compile(
            r"%(?P<name>[A-Za-z_][A-Za-z0-9_]*|`(?:\\.|[^`\\])+`|'(?:\\.|[^'\\])+')"
            r"|//[^\n]*|/\*.*?\*/|'(?:\\.|''|[^'\\])*'|\"(?:\\.|[^\"\\])*\"",
            re.DOTALL,
        )

        def replace(match: re.Match[str]) -> str:
            """
            Replace a variable token while retaining literals and comments.

            :param match: Token matched in the condition.
            :type match: re.Match[str]
            :return: Original token or its runtime FEEL name.
            :rtype: str
            """
            name = match.group("name")
            if name is None:
                return match.group(0)
            if name[0] in {"`", "'"}:
                name = re.sub(r"\\(.)", r"\1", name[1:-1])
            return CamundaBPMNEnricher._feel_name(name)

        return "= " + pattern.sub(replace, expression).strip().removeprefix("=").lstrip()

    @staticmethod
    def _field(key: str, component_id: str) -> Dict[str, Any]:
        """
        Declare a textual form field without label, default or runtime value.

        :param key: Relative variable key within its enclosing group.
        :type key: str
        :param component_id: Globally unique form component ID.
        :type component_id: str
        :return: Empty Camunda Form text field.
        :rtype: Dict[str, Any]
        """
        return {"id": component_id, "type": "textfield", "key": key}

    @staticmethod
    def enrich(
        bpmn_definition: bpmn_model.Definitions,
        version: str,
        variables: Dict[str, Dict[str, Any]],
        action_workers: Dict[str, str],
    ) -> bpmn_model.Definitions:
        """
        Enrich a copied BPMN using complete declarations without instance values.

        :param bpmn_definition: Standard BPMN model to enrich.
        :type bpmn_definition: bpmn_model.Definitions
        :param version: Version of the selected process definition.
        :type version: str
        :param variables: Runtime declarations and reserved definition/binding metadata.
        :type variables: Dict[str, Dict[str, Any]]
        :param action_workers: Action IDs mapped to ActivityDefinition worker names.
        :type action_workers: Dict[str, str]
        :return: Independent executable BPMN containing the embedded Camunda Form.
        :rtype: bpmn_model.Definitions
        :raises BPMNGenerationException: If declarations or bindings cannot be mapped.
        """
        try:
            enriched = copy.deepcopy(bpmn_definition)
            if len(enriched.process) != 1:
                raise ValueError("Enrichment requires exactly one BPMN process")
            process = enriched.process[0]
            metadata = variables["__process_definition__"]
            form_id = f"Form_{metadata['id']}"
            scopes = list(CamundaBPMNEnricher._scopes(process))
            elements: Dict[str, Any] = {}
            for scope in scopes:
                for task in scope.task:
                    if task.id not in action_workers:
                        raise ValueError(f"Missing job worker for action {task.id}")
                    replacement = bpmn_model.ServiceTask(**{
                        field.name: copy.deepcopy(getattr(task, field.name))
                        for field in fields(task)
                    })
                    scope.service_task.append(replacement)
                scope.task = []
                for task in scope.service_task:
                    if task.id in action_workers:
                        CamundaBPMNEnricher._extend(
                            task, camunda_extensions_model.TaskDefinition(type=action_workers[task.id])
                        )
                    elif task.id in variables and variables[task.id].get("kind") == "action":
                        raise ValueError(f"Missing job worker for action {task.id}")
                for field in fields(scope):
                    value = getattr(scope, field.name)
                    if isinstance(value, list):
                        for element in value:
                            if getattr(element, "id", None):
                                elements[element.id] = element

            components: List[Dict[str, Any]] = []
            for name, declaration in variables.items():
                if name == "__process_definition__":
                    continue
                if declaration["kind"] == "action":
                    keys = ["resource", *(
                        key for key in declaration["properties"] if key != "resource"
                    )]
                    components.append({
                        "id": f"Group_{name}", "type": "group", "path": name,
                        "components": [
                            CamundaBPMNEnricher._field(key, f"Field_{name}_{key}")
                            for key in keys
                        ],
                    })
                else:
                    components.append(CamundaBPMNEnricher._field(name, f"Field_{name}"))
                if declaration["kind"] == "temporal":
                    for element_id in declaration.get("element_ids", []):
                        element = elements.get(element_id)
                        if element is None or not getattr(element, "timer_event_definition", None):
                            raise ValueError(f"Missing timer element {element_id}")
                        timer = element.timer_event_definition[0]
                        for field_name in ("time_cycle", "time_date", "time_duration"):
                            setattr(timer, field_name, None)
                        setattr(timer, declaration["timer_type"], bpmn_model.TFormalExpression(
                            content=["= " + CamundaBPMNEnricher._feel_name(name)]
                        ))

            for flow_id, expression in metadata.get("conditions", {}).items():
                flow = elements.get(flow_id)
                if not isinstance(flow, bpmn_model.SequenceFlow):
                    raise ValueError(f"Missing condition flow {flow_id}")
                flow.condition_expression = bpmn_model.TFormalExpression(
                    content=[CamundaBPMNEnricher._condition(expression)]
                )

            form = {
                "id": form_id, "type": "default", "schemaVersion": 1,
                "components": components,
            }
            CamundaBPMNEnricher._extend(process, camunda_extensions_model.UserTaskForm(
                id=form_id, value=json.dumps(form, ensure_ascii=False)
            ))
            CamundaBPMNEnricher._extend(process, camunda_extensions_model.VersionTag(value=version))
            for start in process.start_event:
                CamundaBPMNEnricher._extend(start, camunda_extensions_model.FormDefinition(
                    formKey=f"camunda-forms:bpmn:{form_id}"
                ))
            process.is_executable = True
            if not enriched.id.endswith("_camunda"):
                enriched.id += "_camunda"
            return enriched
        except (ValueError, KeyError, TypeError) as error:
            raise BPMNGenerationException(f"Cannot enrich BPMN for Camunda: {error}") from error
