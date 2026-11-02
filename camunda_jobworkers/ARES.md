# Observation worker → ARES

Il worker `ad_request_observation` (ActivityDefinition 1058) invia i Task a
`POST /tasks` del data provisioning per i seguenti codici:

| SNOMED code | Capability | Variabili Camunda |
|---|---|---|
| 68130003 | getPhysicalActivity | physical_activity_result: HIGH / MEDIUM / LOW |
| 364075005 | getHeartRate | heart_rate: float |
| 258158006 | getSleepParameters | sleep_parameters: intero oggetto sonno |
| 75367002 | getBloodPressure | systolic, diastolic |
| 27113001 | getBodyWeight | body_weight: float in kg |

Gli altri codici e il caso senza codice mantengono la simulazione precedente.
I codici ARES non generano `vital_sign_result` casuali. Lo SDK completa il job
con le sole variabili previste dopo una ricezione e validazione riuscite.
Errori HTTP, indisponibilità o payload malformati si propagano allo SDK e non
producono un completamento con valori inventati.

La richiesta ha forma `{"capability":"getHeartRate","requiredKpi":{...}}`.
I requisiti tecnici del worker sono configurabili nel `.env` di SHIFT oppure
con le variabili d’ambiente (che hanno precedenza):

```dotenv
WORKERS_ARES_URL=http://127.0.0.1:8001/tasks
WORKERS_ARES_TIMEOUT_SECONDS=30
WORKERS_ARES_REQUIRED_KPI='{"latency":{"max":2.0},"reliability":{"min":0.9},"data_freshness":{"max":25.0}}'
```

Questi sono valori iniziali della demo, non requisiti estratti automaticamente
dal piano clinico. Riavviare i worker dopo modifiche alla configurazione.

ARES restituisce il solo `Result`, con `value` e `qos`. Il dato contenuto in
`Result.value` include un `timestamp` UTC e il valore acquisito. Per il sonno:

```json
{
  "duration": 25200.0,
  "end_timestamp": "2026-10-29T14:00:00+00:00",
  "quality": 0.88,
  "stages": {"deep": 5400.0, "light": 12600.0, "rem": 6300.0, "wake": 900.0}
}
```

Tutte le durate sono in secondi; duration include wake e coincide con la somma
degli stage. Il worker passa questo intero oggetto in `sleep_parameters`.
Timestamp e QoS degli altri parametri sono conservati nel Result completo
registrato nei log, senza aggiungere variabili Camunda non richieste.

Ogni risposta ricevuta viene registrata con istanza, attività, job, capability e
Result completo (inclusi QoS) tramite il logger operativo esistente:
`camunda_jobworkers/logs/workers.log`. I record delle variabili restituite
continuano in `camunda_jobworkers/data/invocations.jsonl`.

Il lease del job viene rinnovato prima e durante la chiamata HTTP, usando lo
stesso meccanismo già previsto dai worker; le attese di rete sono asincrone.
Non viene introdotto un retry HTTP nascosto: gli errori sono gestiti dal ciclo
job/retry di Camunda.

## Request correlation and outgoing Task logs

Each HTTP acquisition attempt gets a UUID sent through `X-Request-ID`.
The `ARES Task` log line includes the identifier, Camunda instance/activity/job
and the complete Task payload, including `requiredKpi`. The `ARES Result` and
failure log lines carry the same identifier. On the server, search for it as
`correlation_id` in the provisioning JSONL log. The header correlates traces;
it does not change the Task/Result schema or deduplicate requests.

The questionnaire worker selects exactly one of `0.4` or `0.6` using
`random.choice((0.4, 0.6))`. Choices are independent across occurrences;
intermediate scores are not generated.


## Publishing acquired observations

For the five San Gerardo codes, `ad_request_observation.build_observation`
constructs and validates a base FHIR R5 Observation with `fhir.resources`.
`publish_observation` sends it to the FHIR server before returning process variables.
The subject is taken from the process `subject` variable; it is never hard-coded.
A ServiceRequest reference is retained in `basedOn` when available.

Heart rate and weight use quantities; blood pressure uses systolic/diastolic
components; physical activity uses a categorical value; sleep preserves the
sleep interval, total duration, quality and stage durations. QoS is retained in
an annotation. These are base resources, not assertions of conformance to a
particular implementation-guide profile.

Configure `WORKERS_FHIR_BASE_URL`, `WORKERS_FHIR_API_KEY` and
`WORKERS_FHIR_TIMEOUT_SECONDS` in SHIFT's `.env`. The base URL defaults to
`http://localhost:8080/fhir`; the key is optional. `FHIR_BASE_URL` and
`FHIR_API_KEY` are accepted as fallback names.

Publication uses PUT to a deterministic Observation ID derived from process
instance, job and observation code. Retrying the same job updates the same
resource instead of creating another one. The HTTP request carries the same
`X-Request-ID` as the ARES acquisition. The job lease is renewed throughout
acquisition and publication. Publication failure propagates to the worker;
it does not complete with fabricated measurements. This does not make FHIR
publication and Camunda completion transactional.

The concluded CARE experiment predates this publication code. FHIR transfers
in that run are an explicit study assumption, not retrospective HTTP evidence.
Other observation codes keep their existing implementations.
