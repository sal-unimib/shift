from dataclasses import dataclass, field

__NAMESPACE__ = "http://camunda.org/schema/zeebe/1.0"

@dataclass
class VersionTag:
    class Meta:
        name = "versionTag"
        namespace = __NAMESPACE__
    
    value: str = field(
        default=None,
        metadata={
            "type": "Attribute"
        }
    )