"""Load ActivityDefinition JSON files into existing database tables.

Dependencies: pip install "sqlalchemy[asyncio]" asyncpg
"""
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Union

from sqlalchemy import MetaData, insert, select
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine


BASEPATH = Path("evaluation/dataset/activitydefinition")
FILENAME = "*.json"

DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "shift"
DB_USER = "admin"
DB_PASSWORD = "admin"

VALIDATE_ONLY = False

FHIR_TYPES = {
    "priority": "code",
    "payload[0].contentAttachment": "Attachment",
    "requester": "Reference",
    "recipient[]": "Reference",
    "informationProvider[]": "Reference",
    "code.concept": "CodeableConcept",
    "bodySite.concept": "CodeableConcept",
    "supportingInfo[0].reference": "Reference",
    "oralDiet.instruction": "string",
    "supplement[0].instruction": "string",
    "enteralFormula.administrationInstruction": "markdown",
    "patientInstruction[0].instructionReference": "Reference",
    "medication.concept": "CodeableConcept",
    "dosageInstruction[0].doseAndRate[0]": "DosageDoseAndRate",
}


def read_definitions(basepath: Path, filename: str) -> List[Dict[str, Any]]:
    """Read selected ActivityDefinitions and build parent and attribute rows.

    :param basepath: Directory containing the JSON files.
    :type basepath: pathlib.Path
    :param filename: Filename or glob pattern such as *.json.
    :type filename: str
    :return: Database rows, including the nested attribute rows.
    :rtype: List[Dict[str, Any]]
    """
    files = sorted(basepath.glob(filename))
    if not files:
        raise ValueError(f"Nessun file trovato: {basepath / filename}")
    definitions = []
    seen_ids = set()
    for file in files:
        resource = json.loads(file.read_text(encoding="utf-8"))
        if resource.get("resourceType") != "ActivityDefinition":
            raise ValueError(f"{file.name}: non è una ActivityDefinition")
        if not all(resource.get(key) for key in ("id", "name", "title", "kind")):
            raise ValueError(f"{file.name}: mancano id, name, title o kind")
        identifier = resource["id"]
        if identifier in seen_ids:
            raise ValueError(f"ID duplicato nei file: {identifier}")
        seen_ids.add(identifier)
        attributes = []
        seen_paths, seen_attributes = set(), set()
        for dynamic in resource.get("dynamicValue") or []:
            path = dynamic["path"]
            expression = dynamic["expression"]["expression"]
            parameter = expression.replace("%", "")
            if not parameter:
                raise ValueError(f"{file.name}: nome attributo vuoto")
            if path not in FHIR_TYPES:
                raise ValueError(f"Aggiungi il tipo di '{path}' alla variabile FHIR_TYPES")
            attribute_id = f"{identifier}_{parameter}"
            if path in seen_paths or attribute_id in seen_attributes:
                raise ValueError(f"{file.name}: attributo duplicato: {path}")
            seen_paths.add(path)
            seen_attributes.add(attribute_id)
            attributes.append(dict(id=attribute_id, action_definition_id=identifier,
                path=path, expression=expression, fhir_type=FHIR_TYPES[path], active=True))
        definitions.append(dict(id=identifier, name=resource["name"], title=resource["title"],
            description=resource.get("description") or "", request_kind=resource["kind"],
            active=True, attributes=attributes))
    return definitions


async def load_database(definitions: List[Dict[str, Any]], url: Union[str, URL]) -> Dict[str, int]:
    """Insert missing definitions atomically using reflected database tables.

    :param definitions: Validated parent/attribute rows.
    :type definitions: List[Dict[str, Any]]
    :param url: SQLAlchemy async PostgreSQL URL.
    :type url: Union[str, URL]
    :return: Inserted definitions, inserted attributes and skipped definitions.
    :rtype: Dict[str, int]
    """
    engine = create_async_engine(url)
    counts = {'inserted': 0, 'attributes': 0, 'skipped': 0}
    try:
        async with engine.begin() as connection:
            metadata = MetaData()
            await connection.run_sync(lambda sync: metadata.reflect(bind=sync, only=[
                'action_definition', 'action_definition_attribute']))
            parent = metadata.tables['action_definition']
            attribute = metadata.tables['action_definition_attribute']
            for definition in definitions:
                exists = await connection.scalar(select(parent.c.id).where(parent.c.id == definition['id']))
                if exists is not None:
                    counts['skipped'] += 1
                    continue
                row = {k: v for k, v in definition.items() if k != 'attributes'}
                await connection.execute(insert(parent).values(**row))
                if definition['attributes']:
                    await connection.execute(insert(attribute), definition['attributes'])
                counts['inserted'] += 1
                counts['attributes'] += len(definition['attributes'])
        return counts
    finally:
        await engine.dispose()


async def main() -> None:
    """Load the configured files and insert missing definitions in one transaction.

    :return: None.
    :rtype: None
    """
    definitions = read_definitions(BASEPATH, FILENAME)
    if VALIDATE_ONLY:
        print(f"Validati {len(definitions)} file e "
              f"{sum(len(d['attributes']) for d in definitions)} attributi. Nessun accesso al database.")
        return
    url = URL.create("postgresql+asyncpg", host=DB_HOST, port=DB_PORT,
                     database=DB_NAME, username=DB_USER, password=DB_PASSWORD)
    counts = await load_database(definitions, url)
    print(f"Inserite: {counts['inserted']}; attributi: {counts['attributes']}; "
          f"già presenti: {counts['skipped']}")


if __name__ == "__main__":
    asyncio.run(main())
