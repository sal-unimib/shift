from typing import Union, Optional
from urllib.parse import urlsplit
from src.domain.enums import TemporalCategory
from src.domain.exceptions import ContractIdException


def contract_id(prefix: str, *parts: str) -> str:
    """
    Compose a readable identifier by joining its components with underscores.

    :param prefix: Entity prefix, or an empty string for an unprefixed identifier.
    :type prefix: str
    :param parts: Ordered, non-empty identifier components.
    :type parts: str
    :return: Identifier preserving the original component values.
    :rtype: str
    :raises ContractIdException: If an identifier component or FHIR reference is invalid.
    """
    if not isinstance(prefix, str) or not parts or any(not isinstance(part, str) or not part for part in parts):
        raise ContractIdException('Identifier components must be non-empty strings.')
    return '_'.join((prefix, *parts) if prefix else parts)


def fhir_resource_id(reference: str, resource_type: Optional[str] = None) -> str:
    """
    Extract a logical ID from an unversioned FHIR resource reference or a bare ID.

    :param reference: Bare ID or reference such as PlanDefinition/1 or ServiceRequest/REQ-01; absolute HTTP references are also accepted.
    :type reference: str
    :param resource_type: Expected resource type when the reference includes one; None accepts any type.
    :type resource_type: Optional[str]
    :return: Logical resource ID, without resource type or base URL.
    :rtype: str
    :raises ContractIdException: If an identifier component or FHIR reference is invalid.
    """
    if not isinstance(reference, str) or not reference.strip():
        raise ContractIdException('A FHIR resource ID or reference is required.')
    if resource_type is not None and (not isinstance(resource_type, str) or not resource_type):
        raise ContractIdException('The expected resource type must be a non-empty string.')
    reference = reference.strip()
    if '|' in reference or '/_history/' in reference:
        raise ContractIdException('FHIR references must not include a resource version.')
    try:
        parsed = urlsplit(reference)
    except ValueError:
        raise ContractIdException('Invalid FHIR resource reference.') from None
    if parsed.query or parsed.fragment:
        raise ContractIdException('A FHIR resource reference cannot contain query parameters or a fragment.')
    if parsed.scheme:
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            raise ContractIdException('Unsupported FHIR resource reference.')
        parts = parsed.path.strip('/').split('/')
        if len(parts) < 2 or parsed.path.endswith('/'):
            raise ContractIdException('A resource reference must include its type and ID.')
        parts = parts[-2:]
    else:
        parts = reference.split('/')
        if len(parts) not in (1, 2) or any(not part for part in parts):
            raise ContractIdException('Expected a resource ID or a ResourceType/ID reference.')
    if resource_type is not None and len(parts) == 2 and parts[0] != resource_type:
        raise ContractIdException('The FHIR reference has an unexpected resource type.')
    return parts[-1]


def plan_definition_id(reference: str) -> str:
    """
    Extract the PlanDefinition ID referenced by RequestOrchestration.instantiatesCanonical.

    :param reference: PlanDefinition ID or unversioned PlanDefinition/<ID> reference.
    :type reference: str
    :return: PlanDefinition logical ID; its version is obtained separately.
    :rtype: str
    :raises ContractIdException: If an identifier component or FHIR reference is invalid.
    """
    return fhir_resource_id(reference, 'PlanDefinition')


def action_definition_id(reference: str) -> str:
    """
    Extract the ActivityDefinition ID referenced by PlanDefinition.action.definitionCanonical.

    :param reference: ActivityDefinition ID or unversioned ActivityDefinition/<ID> reference.
    :type reference: str
    :return: ActivityDefinition logical ID, without a resource type or version.
    :rtype: str
    :raises ContractIdException: If an identifier component or FHIR reference is invalid.
    """
    return fhir_resource_id(reference, 'ActivityDefinition')


def request_resource_id(reference: str) -> str:
    """
    Extract a request ID from RequestOrchestration.action.resource.reference.

    :param reference: Request ID or unversioned reference such as ServiceRequest/REQ-01.
    :type reference: str
    :return: Request resource logical ID; the original reference retains its resource type.
    :rtype: str
    :raises ContractIdException: If an identifier component or FHIR reference is invalid.
    """
    return fhir_resource_id(reference)


def action_definition_attribute_id(reference: str, expression: str) -> str:
    """
    Build an attribute identifier from its ActivityDefinition and expression.

    :param reference: ActivityDefinition identifier or unversioned resource reference.
    :type reference: str
    :param expression: Declared expression, with percent characters removed from the identifier.
    :type expression: str
    :return: Identifier in the format <action_definition_id>_<expression_without_percent>.
    :rtype: str
    :raises ContractIdException: If an identifier component or FHIR reference is invalid.
    """
    if not isinstance(expression, str):
        raise ContractIdException('An attribute expression must be a string.')
    return contract_id('', action_definition_id(reference), expression.replace('%', ''))


def process_definition_id(plan_id: str, version: str) -> str:
    """
    Build a readable process definition identifier.

    :param plan_id: Source PlanDefinition ID or unversioned PlanDefinition/<ID> reference.
    :type plan_id: str
    :param version: Version identifying the process definition.
    :type version: str
    :return: Identifier in the format <plan_id>_<version>.
    :rtype: str
    :raises ContractIdException: If an identifier component or FHIR reference is invalid.
    """
    return contract_id('', plan_definition_id(plan_id), version)


def process_action_variable_id(plan_id: str, version: str, action_link_id: str, attribute_id: str) -> str:
    """
    Build an action-variable identifier within a process definition.

    :param plan_id: Source PlanDefinition ID or unversioned PlanDefinition/<ID> reference.
    :type plan_id: str
    :param version: Version assigned to the process definition by its caller.
    :type version: str
    :param action_link_id: FHIR action linkId.
    :type action_link_id: str
    :param attribute_id: ActionDefinitionAttribute identifier.
    :type attribute_id: str
    :return: Identifier in the format pav_<plan_id>_<version>_<action_link_id>_<attribute_id>.
    :rtype: str
    :raises ContractIdException: If an identifier component or FHIR reference is invalid.
    """
    return contract_id('pav', plan_definition_id(plan_id), version, action_link_id, attribute_id)


def process_temporal_variable_id(plan_id: str, version: str, action_link_id: str, category: Union[TemporalCategory, str]) -> str:
    """
    Build a temporal-constraint identifier within a process definition.

    :param plan_id: Source PlanDefinition ID or unversioned PlanDefinition/<ID> reference.
    :type plan_id: str
    :param version: Version assigned to the process definition by its caller.
    :type version: str
    :param action_link_id: FHIR action linkId, including a shared-action identifier when applicable.
    :type action_link_id: str
    :param category: SHIFT temporal category or its serialized value.
    :type category: typing.Union[TemporalCategory, str]
    :return: Identifier in the format ptv_<plan_id>_<version>_<action_link_id>_<temporal_category>.
    :rtype: str
    :raises ContractIdException: If an identifier component or FHIR reference is invalid.
    """
    value = category.value if isinstance(category, TemporalCategory) else category
    return contract_id('ptv', plan_definition_id(plan_id), version, action_link_id, value)


def process_variable_id(prefix: str, plan_id: str, version: str, element_id: str, variable_name: Optional[str] = None) -> str:
    """
    Build a generic variable identifier from its prefix and BPMN element.

    :param prefix: Variable prefix; no prefix is inferred from the BPMN element type.
    :type prefix: str
    :param plan_id: Source PlanDefinition ID or unversioned PlanDefinition/<ID> reference.
    :type plan_id: str
    :param version: Version assigned to the process definition by its caller.
    :type version: str
    :param element_id: Identifier of the associated BPMN element.
    :type element_id: str
    :param variable_name: Optional variable name distinguishing bindings on the same element.
    :type variable_name: Optional[str]
    :return: Identifier in the format <prefix>_<plan_id>_<version>_<element_id>[_<variable_name>].
    :rtype: str
    :raises ContractIdException: If an identifier component or FHIR reference is invalid.
    """
    if not prefix:
        raise ContractIdException('A generic variable prefix is required.')
    parts = (plan_definition_id(plan_id), version, element_id)
    return contract_id(prefix, *parts, variable_name) if variable_name is not None else contract_id(prefix, *parts)
