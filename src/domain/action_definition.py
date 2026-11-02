from src.database.model.action_definition_record import ActionDefinitionRecord
from src.database.model.action_definition_record import ActionDefinitionAttributeRecord
from typing import List, Optional
from src.utils.definition_identifiers import action_definition_id, action_definition_attribute_id

class ActionDefinitionAttribute:
    """
    Represents an attribute of an action definition.
    """
    id: str
    path: str
    expression: str
    fhir_type: str

    def __init__(
        self,
        id: str,
        path: str,
        expression: str,
        fhir_type: str
    ):
        self.id = id
        self.path = path
        self.expression = expression
        self.fhir_type = fhir_type
    
    @staticmethod
    def from_record(record: ActionDefinitionAttributeRecord) -> "ActionDefinitionAttribute":
        return ActionDefinitionAttribute(
            id=record.id,
            path=record.path,
            expression=record.expression,
            fhir_type=record.fhir_type
        )

    def to_record(self, owner_id: Optional[str] = None) -> ActionDefinitionAttributeRecord:
        """
        Convert the attribute into a database record using its readable identifier.

        :param owner_id: Owning ActivityDefinition identifier; None preserves the current attribute ID.
        :type owner_id: typing.Optional[str]
        :return: Attribute record identified by <action_definition_id>_<expression_without_percent> when the owner is supplied.
        :rtype: ActionDefinitionAttributeRecord
        """
        if owner_id is not None:
            self.id = action_definition_attribute_id(owner_id, self.expression)
        return ActionDefinitionAttributeRecord(
            id=self.id,
            path=self.path,
            expression=self.expression,
            fhir_type=self.fhir_type
        )

class ActionDefinition:
    """Represents an action definition."""

    id: str
    name: str
    title: str
    description: str
    request_kind: str
    attributes: List[ActionDefinitionAttribute]

    def __init__(
        self,
        id: str,
        name: str,
        title: str,
        description: str,
        request_kind: str,
        attributes: Optional[List[ActionDefinitionAttribute]] = None
    ):
        """
        Initialize an action definition using its unversioned FHIR resource ID.

        :param id: ActivityDefinition ID or unversioned ActivityDefinition/<ID> reference.
        :type id: str
        :param name: Action definition name.
        :type name: str
        :param title: Human-readable title.
        :type title: str
        :param description: Action definition description.
        :type description: str
        :param request_kind: FHIR request resource type produced by the action.
        :type request_kind: str
        :param attributes: Declared attributes; IDs are derived from their expressions without percent characters.
        :type attributes: Optional[List[ActionDefinitionAttribute]]
        """
        self.id = action_definition_id(id)
        self.name = name
        self.title = title
        self.description = description
        self.request_kind = request_kind
        self.attributes = list(attributes or [])
        for attribute in self.attributes:
            attribute.id = action_definition_attribute_id(self.id, attribute.expression)

    @staticmethod
    def from_record(record: ActionDefinitionRecord) -> "ActionDefinition":
        return ActionDefinition(
            id=record.id,
            name=record.name,
            description=record.description,
            title=record.title,
            request_kind=record.request_kind,
            attributes=[ActionDefinitionAttribute.from_record(attribute) for attribute in record.attributes]
        )

    def to_record(self) -> ActionDefinitionRecord:
        """
        Convert an action definition and its attributes into database records.

        :return: Record using the ActivityDefinition ID without version, with attribute IDs derived from expressions without percent characters.
        :rtype: ActionDefinitionRecord
        """
        self.id = action_definition_id(self.id)
        return ActionDefinitionRecord(
            id=self.id,
            name=self.name,
            title=self.title,
            description=self.description,
            request_kind=self.request_kind,
            attributes=[attribute.to_record(self.id) for attribute in self.attributes]
        )
        