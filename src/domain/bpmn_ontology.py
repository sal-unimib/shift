import owlready2
from src.utils.settings import settings

# Resolve BBO and its bundled imports independently of the working directory.
owlready2.onto_path.append(str(settings.filesystem.ontology_dir))
bbo = owlready2.get_ontology((settings.filesystem.ontology_dir / "BBO.owl").as_uri()).load()
