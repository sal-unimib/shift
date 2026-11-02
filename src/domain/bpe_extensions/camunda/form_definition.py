from dataclasses import dataclass, field

__NAMESPACE__ = "http://camunda.org/schema/zeebe/1.0"

@dataclass
class FormDefinition:
    class Meta:
        name = "formDefinition"
        namespace = __NAMESPACE__

    formKey: str = field(
        default=None,
        metadata={
            "type": "Attribute"
        }
    )