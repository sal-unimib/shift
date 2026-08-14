#!/bin/bash
set -e

SCHEMA_DIR="data/bpmn_schema"
OUTPUT_PACKAGE="src.domain.bpmn"
OUTPUT_DIR="src/domain/bpmn"

if [ ! -d "$SCHEMA_DIR" ]; then
    echo "Schema directory '$SCHEMA_DIR' does not exist. Run ./download_resources.sh first."
    exit 1
fi

# Ensure PATH includes .venv/bin if virtual environment exists
if [ -d ".venv/bin" ]; then
    export PATH=".venv/bin:$PATH"
fi

echo "Cleaning previous generated files in '$OUTPUT_DIR'..."
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

echo "Generating Python model classes from BPMN XSD schemas..."
xsdata generate "$SCHEMA_DIR" --structure-style clusters -p "$OUTPUT_PACKAGE"

echo "BPMN model generated successfully in '$OUTPUT_DIR'!"
