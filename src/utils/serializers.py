import re
from typing import Dict, Optional
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig
from src.domain.bpmn.definitions import Definitions

class BPMNSerializer():
    """
    Helper class to serialize BPMN in XML.
    """

    context : XmlContext
    """XML context instance for XML serializer and parser."""
    config : SerializerConfig
    """XML serializer configuration."""
    serializer : XmlSerializer
    """XML serializer to write BPMN files."""
    parser : XmlParser
    """XML parser to read BPMN files."""

    def __init__(self):
        self.context = XmlContext()
        self.config = SerializerConfig(
            ignore_default_attributes=True,
            pretty_print=True,
            indent="\t"
        )
        self.serializer = XmlSerializer(
            config=self.config,
            context=self.context
        )
        self.parser = XmlParser(
            # TODO config ?
            context = self.context
        )
    
    def serialize(self, bpmn_definition: Definitions, namespaces: Dict[str, str]) -> str:
        """
        
        """
        return self.serializer.render(bpmn_definition, ns_map=namespaces)
    
    def parse(self, file_path: str, namespaces: Dict[Optional[str], str]) -> Definitions:
        """Deserialize a BPMN document using the configured xsdata backend.

        A binary stream supports both the native and lxml handlers and lets the
        XML declaration determine the document encoding.

        :param file_path: Path to the BPMN XML document.
        :type file_path: str
        :param namespaces: Prefix-to-URI mappings, including an optional default prefix.
        :type namespaces: Dict[Optional[str], str]
        :return: Parsed BPMN domain definition.
        :rtype: Definitions
        """
        with open(file_path, 'rb') as bpmn_file:
            return self.parser.parse(
                source=bpmn_file,
                clazz=Definitions,
                ns_map=namespaces
            )


def from_camel_to_snake(name: str) -> str:
    """
    Method to convert a string from *camelCase* or *PascalCase* to *snake_case*.
    
    :param name: String in *camelCase* or *PascalCase*.
    :type name: str
    :return: The input string in *snake_case*.
    :rtype: str
    """
    # Add underscore before capital letters that are not the first character
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    # Handle lowercase characters followed by uppercase letters
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.lower()

def from_snake_to_camel(name: str, pascal: bool = True) -> str:
    """
    Method to convert a string from *snake_case* to *camelCase* or *PascalCase*.
    
    :param name: String in *snake_case*.
    :type name: str
    :param pascal: If True (default), generate *PascalCase* string. Otherwise, *camelCase* string.
    :type pascal: bool
    :return: The input string in *camelCase* or *PascalCase*.
    :rtype: str
    """
    components = name.split('_')
    if pascal:
        # First capital letter of each component
        return ''.join(x.title() for x in components)
    else:
        # First word lowercase, others with first capital letter
        return components[0].lower() + ''.join(x.title() for x in components[1:])
