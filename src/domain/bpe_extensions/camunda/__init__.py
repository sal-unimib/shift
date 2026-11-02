# -------------------------------------------
# Helper classes Camunda => ExtensionElements
# -------------------------------------------

ZEEBE_NAMESPACE = "http://camunda.org/schema/zeebe/1.0"

from src.domain.bpe_extensions.camunda.form_definition import FormDefinition
from src.domain.bpe_extensions.camunda.task_definition import TaskDefinition
from src.domain.bpe_extensions.camunda.user_task_form import UserTaskForm
from src.domain.bpe_extensions.camunda.version_tag import VersionTag

__all__ = [
    "UserTaskForm",
    "VersionTag",
    "FormDefinition",
    "TaskDefinition"
]
