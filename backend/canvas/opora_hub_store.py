"""Soubory OporaHubu: místo, kde commit opravdu leží. Index se z nich kdykoli přepočítá.

Krok 9 kontraktu `docs/synchronizace-pravdy.md`, část 3 „OporaHub: commity, větve, main“.
Složka `<složka projektu>/oporahub/` drží jeden soubor na commit (`<id>.json`, zapsaný
atomicky a nikdy nepřepsaný) a append-only `main.log` se seznamem `id`, která jsou v mainu.
Tenhle modul nezná SQLite; druhou půlku (index a pravidla) má `opora_hub.py`.
"""

import hashlib
import json
import os
import re
import secrets

MAIN_LOG = "main.log"
ID_LENGTH = 40


def canonical(content):
    """Kanonický JSON obsahu: setříděné klíče, oddělovače bez mezer, diakritika beze změny."""
    return json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def content_id(content):
    """`id` commitu: prvních 40 znaků SHA-256 kanonického obsahu. Stejný obsah, stejné `id`."""
    return hashlib.sha256(canonical(content).encode("utf-8")).hexdigest()[:ID_LENGTH]


class OporaHubStore:
    """Jediný vlastník složky `oporahub/`: commity jako soubory a main jako seznam `id`."""

    def __init__(self, canvas):
        self.canvas = canvas

    def folder(self, pid):
        """Složka OporaHubu projektu; u starších projektů vznikne při prvním commitu."""
        folder = self.canvas.folder(pid).oporahub
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def write(self, pid, record):
        """Atomický zápis commitu (tmp + os.replace); hotový soubor se nikdy nepřepisuje."""
        path = self.folder(pid) / f"{record['id']}.json"
        if path.exists():
            raise ValueError("Commit s tímto obsahem už v OporaHubu leží; commit se nepřepisuje.")
        tmp = path.with_name(f"{path.name}.{secrets.token_hex(12)}.tmp")
        try:
            tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)

    def records(self, pid, wid):
        """Všechny commity jednoho pracovního prostoru, tak jak leží na disku."""
        records = []
        for path in sorted(self.folder(pid).glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("project") == pid and record.get("workspace") == wid:
                records.append(record)
        return records

    def read(self, pid, commit_id):
        """Načte obsah podle bezpečného ID a ověří otisk, nikoli jen index SQLite."""
        if not isinstance(commit_id, str) or not re.fullmatch(r"[a-f0-9]{40}", commit_id):
            raise ValueError("Neplatné ID commitu OporaHubu.")
        try:
            record = json.loads((self.folder(pid) / f"{commit_id}.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ValueError("Commit v OporaHubu neexistuje.") from None
        if (not isinstance(record, dict) or record.get("id") != commit_id
                or content_id({key: value for key, value in record.items() if key != "id"}) != commit_id):
            raise ValueError("Obsah commitu OporaHubu neodpovídá jeho otisku.")
        return record

    def main_ids(self, pid):
        """`id` commitů v mainu. Opakovaný zápis téhož `id` nevadí, čte se jako množina."""
        path = self.folder(pid) / MAIN_LOG
        if not path.is_file():
            return set()
        lines = path.read_text(encoding="utf-8").splitlines()
        return {line.strip() for line in lines if line.strip()}

    def mark_main(self, pid, commit_id):
        """Main je append-only seznam `id`, aby ho šlo obnovit stejně jako commity."""
        with (self.folder(pid) / MAIN_LOG).open("a", encoding="utf-8") as log:
            log.write(commit_id + "\n")
