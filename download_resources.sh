#!/bin/bash
set -e

# Directory where ontology resources are stored
DATA_DIR="data"

# Create data/ontology directory
ONTO_DIR="$DATA_DIR/ontology"
mkdir -p "$ONTO_DIR"

echo "Downloading BBO.owl..."
curl -sSL https://raw.githubusercontent.com/AminaANNANE/BBO_BPMNbasedOntology/master/BBO.owl -o "$ONTO_DIR/BBO.owl"

# uo.owl is imported by BBO.owl. The release URL in BBO.owl returns 404 upstream, 
# so we download the current uo.owl locally into the data folder for owlready2.
echo "Downloading imported dependency uo.owl..."
curl -sSL http://purl.obolibrary.org/obo/uo.owl -o "$ONTO_DIR/uo.owl"

# Create data/bpmn_schema directory
BPMN_SCHEMA_DIR="$DATA_DIR/bpmn_schema"
mkdir -p "$BPMN_SCHEMA_DIR"

echo "Downloading BPMN 2.0 XSD schemas..."
curl -sSL https://www.omg.org/spec/BPMN/20100501/BPMN20.xsd -o "$BPMN_SCHEMA_DIR/BPMN20.xsd"
curl -sSL https://www.omg.org/spec/BPMN/20100501/BPMNDI.xsd -o "$BPMN_SCHEMA_DIR/BPMNDI.xsd"
curl -sSL https://www.omg.org/spec/BPMN/20100501/DC.xsd -o "$BPMN_SCHEMA_DIR/DC.xsd"
curl -sSL https://www.omg.org/spec/BPMN/20100501/DI.xsd -o "$BPMN_SCHEMA_DIR/DI.xsd"
curl -sSL https://www.omg.org/spec/BPMN/20100501/Semantic.xsd -o "$BPMN_SCHEMA_DIR/Semantic.xsd"

echo "Resources downloaded successfully to '$DATA_DIR/'!"

