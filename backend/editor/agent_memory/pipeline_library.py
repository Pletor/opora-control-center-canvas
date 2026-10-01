"""Knihovna pipeline pro blok Akce: verzovaný JSON v library/pipelines.json, jen ke čtení.

Položka je předloha, ne běh: výběr do bloku uzlu uloží jen `pipelineId` a popisek.
Nevalidní soubor se hlásí jako chyba, nikdy se nenahrazuje odhadem či demo daty.
"""
import json

from backend.paths import REPO_ROOT

LIBRARY_FILE = REPO_ROOT / "library" / "pipelines.json"
CATEGORY_KEYS = {"id", "label", "description", "pipelines"}
PIPELINE_KEYS = {"id", "label", "description"}
MAX_TEXT = 400


def _fail(message):
    raise ValueError("Knihovna pipeline je neplatná: " + message)


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT or "\0" in value:
        _fail(f"{label} musí být neprázdný text do {MAX_TEXT} znaků.")
    return value


def validate_library(value):
    if not isinstance(value, dict) or set(value) != {"categories"} or not isinstance(value["categories"], list):
        _fail("očekávám objekt s polem categories.")
    seen_categories, seen_pipelines = set(), set()
    for category in value["categories"]:
        if not isinstance(category, dict) or set(category) != CATEGORY_KEYS:
            _fail("kategorie má neplatná pole.")
        _text(category["id"], "id kategorie")
        _text(category["label"], "název kategorie")
        _text(category["description"], "popis kategorie")
        if category["id"] in seen_categories:
            _fail(f"duplicitní kategorie {category['id']}.")
        seen_categories.add(category["id"])
        if not isinstance(category["pipelines"], list) or not category["pipelines"]:
            _fail(f"kategorie {category['id']} nemá žádnou pipeline.")
        for item in category["pipelines"]:
            if not isinstance(item, dict) or set(item) != PIPELINE_KEYS:
                _fail("pipeline má neplatná pole.")
            for key in PIPELINE_KEYS:
                _text(item[key], f"{key} pipeline")
            if item["id"] in seen_pipelines:
                _fail(f"duplicitní pipeline {item['id']}.")
            seen_pipelines.add(item["id"])
    return value


def load(path=LIBRARY_FILE):
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Knihovna pipeline je neplatná: soubor {path.name} není platný JSON ({error.msg}).") from error
    return validate_library(raw)
