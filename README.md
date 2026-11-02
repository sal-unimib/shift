# SHIFT — From FHIR Workflow Definitions to Executable and Patient-Specific BPMN Processes

SHIFT transforms **HL7 FHIR R5 workflow specifications into executable BPMN care processes**. It separates the generation of reusable process definitions from their specialization and preparation for a particular patient.

The definition-level transformation takes a `PlanDefinition` and produces a reusable BPMN model. The instance-level transformation uses a patient-specific `RequestOrchestration` to align the process definition, bind clinical parameters and temporal values, and prepare its execution in Camunda.

This repository includes the implementation, ActivityDefinition job workers, reference datasets, generated artifacts, and evaluation materials.

---

## Repository Structure

```text
.
├── src/                           # Transformation pipeline and HTTP service
├── camunda_jobworkers/            # Clinical activity workers
├── data/
│   ├── ontology/                  # BBO and Units Ontology
│   ├── bpmn_schema/               # BPMN XML schemas
│   └── storage/fs/                # Generated CFG and BPMN artifacts
├── evaluation/
│   ├── dataset/                   # FHIR inputs and ActivityDefinition catalog
│   ├── groundtruth/               # Reference BPMN models and variable values
│   ├── RQ1/                       # Transformation correctness
│   └── RQ2/                       # Execution fidelity
├── camunda/                       # Camunda Docker Compose configuration
├── upload_activity_definition.py  # Load the activity catalog into PostgreSQL
├── docker-compose.yml             # SHIFT PostgreSQL service
├── requirements.txt
├── .env.example
└── README.md
```

## Dataset and Outputs

The evaluation dataset contains twenty clinical pathway cases represented as FHIR `PlanDefinition` and `RequestOrchestration` resources, together with twelve reusable `ActivityDefinition` resources. A separate request dataset provides the compressed temporal values used in the execution experiment.

- `evaluation/dataset/plandefinition/`: reusable clinical workflow definitions.
- `evaluation/dataset/requestorchestration/`: patient-specific workflow requests.
- `evaluation/dataset/requestorchestration_fast_timing/`: requests with accelerated schedules.
- `evaluation/dataset/activitydefinition/`: clinical activity definitions.
- `evaluation/groundtruth/`: reference BPMN models, runtime values, and the frozen activity catalog.
- `data/storage/fs/`: generated control-flow graphs and BPMN models.
- `evaluation/RQ1/results/` and `evaluation/RQ2/results/`: evaluation reports and supporting evidence.

---

## Requirements and Installation

The current environment uses **Python 3.13.15**. PostgreSQL is required for the HTTP service; Camunda is required for deployment and live process execution. The offline evaluations do not connect to these services.

From the repository root:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

## Environment Configuration

Edit `.env` to match your PostgreSQL and Camunda installations. The main settings are:

| Setting | Purpose |
| --- | --- |
| `SHIFT_DB__URL` | PostgreSQL connection URL using the `asyncpg` driver |
| `SHIFT_FILESYSTEM__ARTIFACTS_DIR` | Destination for generated CFG and BPMN files |
| `SHIFT_CAMUNDA__REST_ADDRESS` | Camunda Orchestration Cluster REST API |
| `SHIFT_CAMUNDA__AUTH_STRATEGY` | Authentication strategy: `NONE`, `BASIC`, or `OAUTH` |
| `SHIFT_CAMUNDA__CLIENT_ID` / `SHIFT_CAMUNDA__CLIENT_SECRET` | SHIFT OAuth client credentials |
| `SHIFT_CAMUNDA__OAUTH_URL` / `SHIFT_CAMUNDA__TOKEN_AUDIENCE` | OAuth token endpoint and audience |
| `WORKERS_CAMUNDA_CLIENT_ID` / `WORKERS_CAMUNDA_CLIENT_SECRET` | Worker OAuth client credentials |
| `WORKERS_CAMUNDA_TOKEN_AUDIENCE` | Worker token audience |

The supplied PostgreSQL Compose creates the database `shift` with the user and password configured in `docker-compose.yml`. Match these values in `SHIFT_DB__URL`. The supplied Camunda Compose exposes the REST API at `http://localhost:8082/v2`; configure the corresponding authentication settings in `.env`.

The offline transformation tools also load the project settings, so a syntactically valid `SHIFT_DB__URL` must be configured even when no database connection is used. Relative storage paths resolve against the repository root. Keep local credentials out of version control.

---

## Starting External Services

Start the SHIFT PostgreSQL service:

```bash
docker compose up -d
```

The Camunda environment is provided separately in `camunda/`. Configure its local `.env` and `connector-secrets.txt`, including image versions and authentication settings, before starting it:

```bash
docker compose --project-directory camunda up -d
```

The Camunda configuration uses the YAML files in the hidden directories under `camunda/`; these directories must remain alongside its Compose file.

## Running SHIFT

Start the HTTP service from the repository root:

```bash
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Application startup initializes missing database tables. Before registering a clinical workflow, load the ActivityDefinition catalog: set the database connection parameters at the top of `upload_activity_definition.py` to the same database used by SHIFT, then run in another terminal:

```bash
python upload_activity_definition.py
```

The service accepts FHIR resources at:

| Endpoint | Input | Operation |
| --- | --- | --- |
| `POST /webhooks/plandefinition` | `PlanDefinition` | Generate and register a reusable process definition |
| `POST /webhooks/requestorchestration` | `RequestOrchestration` | Prepare, deploy, and start a patient-specific process |

Register the referenced `PlanDefinition` before submitting its patient-specific request. The endpoints accept the resource itself as the JSON request body.

To execute clinical activities, start the workers in a separate terminal:

```bash
python -m camunda_jobworkers
```

The observation worker integrates with ARES and a FHIR server for the five capability mappings used in CARE; other observation codes use simulated outputs. Configure `WORKERS_ARES_*` and `WORKERS_FHIR_*` when using this integration. Connection settings and supported mappings are described in [camunda_jobworkers/ARES.md](camunda_jobworkers/ARES.md).

---

## Research Questions

The component evaluation addresses two research questions:

- **RQ1 — Transformation correctness:** agreement of definition-level and patient-specific BPMN models with the reference models, including supported control flow, temporal constructs, parameters, and specialization.
- **RQ2 — Execution fidelity:** agreement between observed Camunda executions and reference-model traces under the recorded worker inputs, including clinical actions, input bindings, precedence, and timing.

Structural agreement and execution fidelity are assessed separately. The evaluation concerns the supported constructs and the twenty supplied cases.

## Running the Evaluation

Run the following commands from the repository root with the Python environment activated and `.env` configured. New reports are written to `reproduced/`, keeping the supplied reports separate.

### RQ1 — Transformation Correctness

Generate and evaluate definition-level models without accessing PostgreSQL or Camunda:

```bash
python evaluation/RQ1/definition_level.py \
  --generate --output reproduced/rq1/definition
```

Generate and evaluate patient-specific models, including runtime variable values:

```bash
python evaluation/RQ1/instance_level.py \
  --generate --output reproduced/rq1/instance
```

To evaluate saved models instead, omit `--generate` and select their directory with `--artifacts`. Use artifacts from the same input configuration: ordinary requests and accelerated requests are separate datasets. The current specialized CFGs in `data/storage/fs/` correspond to the accelerated requests. Offline-generated reports also include variable-value checks that are unavailable in the archived existing-artifact evaluation, so the two modes have different counting scopes.

The reports include per-process and per-category CSV metrics, detailed differences, and JSON summaries.

### RQ2 — Execution Fidelity

Reconstruct the reference execution using the archived experiment inputs:

```bash
python evaluation/RQ2/simulate.py \
  --runs evaluation/RQ2/results/runs.engine.json \
  --invocations evaluation/RQ2/results/invocations.snapshot.jsonl \
  --engine-events evaluation/RQ2/results/engine_events.jsonl \
  --output reproduced/rq2/expected.json
```

Compare it with the recorded execution using a one-second tolerance:

```bash
python evaluation/RQ2/evaluate.py \
  --expected reproduced/rq2/expected.json \
  --invocations evaluation/RQ2/results/invocations.snapshot.jsonl \
  --engine-events evaluation/RQ2/results/engine_events.jsonl \
  --tolerance-seconds 1 \
  --output reproduced/rq2/reports
```

These commands use the saved evidence for P01–P20 and do not query Camunda or start new process instances. Use the archived invocation snapshot rather than the workers' current operational log.

The outputs include process and category metrics, individual checks, errors, and a complete JSON report. To run the offline evaluation tests:

```bash
python -m unittest discover -s evaluation/RQ2 -p 'test_*.py' -v
```

---

## Citation

The methodology and implementation are described in the associated doctoral thesis and the SHIFT manuscript:

> Gallo, G. D., and Micucci, D. (2026). *SHIFT: From FHIR Workflow Definitions to Executable and Patient-Specific BPMN Processes*. Manuscript in preparation for submission to the Journal of Systems and Software.

```bibtex
@unpublished{Gallo2026SHIFT,
  author = {Gallo, Giovanni Donato and Micucci, Daniela},
  title = {{SHIFT}: From {FHIR} Workflow Definitions to Executable
           and Patient-Specific {BPMN} Processes},
  year = {2026},
  note = {Manuscript in preparation for submission to the Journal of Systems and Software}
}
```
