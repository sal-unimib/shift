from dataclasses import dataclass, field

__NAMESPACE__ = "http://camunda.org/schema/zeebe/1.0"

@dataclass
class TaskDefinition:
    class Meta:
        name = "taskDefinition"
        namespace = __NAMESPACE__

    type: str = field(
        default=None,
        metadata= {
            "type": "Attribute"
        }
    )
