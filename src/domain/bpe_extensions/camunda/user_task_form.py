from dataclasses import dataclass, field

__NAMESPACE__ = "http://camunda.org/schema/zeebe/1.0"

@dataclass
class UserTaskForm:
    class Meta:
        name = "userTaskForm"
        namespace = __NAMESPACE__
    
    id: str = field(
        default=None,
        metadata={
            "type": "Attribute"
        }
    )
    value: str = field(
        default=None,
        metadata={
            "type": "Text"
        }
    )