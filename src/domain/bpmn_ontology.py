import owlready2

# Add the 'data' directory to owlready2's search path
owlready2.onto_path.append("data")

# Load BBO ontology
bbo = owlready2.get_ontology("BBO.owl").load()
