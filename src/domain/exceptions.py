class PlanDefinitionValidationException(Exception):
    """
    Exception raised for errors in the validation of a FHIR PlanDefinition resource.

    :param message: The error message.
    :type message: str
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class CFGGenerationException(Exception):
    """
    Exception raised for errors in the generation of a CFG.

    :param message: The error message.
    :type message: str
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class BPMNGenerationException(Exception):
    """
    Exception raised for errors in the generation of a BPMN process definition.

    :param message: The error message.
    :type message: str
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class ArtifactWriteException(Exception):
    """
    Exception raised for errors while writing of artifacts in the filesystem storage.

    :param message: The error message.
    :type message: str
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class ArtifactReadException(Exception):
    """
    Exception raised for errors while reading of artifacts from the filesystem storage.

    :param message: The error message.
    :type message: str
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class DBWriteException(Exception):
    """
    Exception raised for errors while writing of records in the database storage.

    :param message: The error message.
    :type message: str
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class DBReadException(Exception):
    """
    Exception raised for errors while reading of records from the database storage.

    :param message: The error message.
    :type message: str
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class ContractIdException(Exception):
    """
    Exception raised for errors while generating contract IDs or parsing FHIR references.

    :param message: Description of the identifier or reference validation error.
    :type message: str
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class RequestOrchestrationValidationException(Exception):
    """
    Exception raised for errors in the validation of a FHIR RequestOrchestration resource.

    :param message: The error message.
    :type message: str
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class CamundaDeploymentException(Exception):
    """
    Exception raised when a Camunda BPMN deployment fails.

    :param message: Description of the deployment failure.
    :type message: str
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class CamundaInstanceException(Exception):
    """
    Exception raised when a Camunda process instance cannot be created.

    :param message: Description of the process creation failure.
    :type message: str
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
