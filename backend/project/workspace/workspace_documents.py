"""Revizovaná dokumentace nad cestami; zdrojový kód zůstává nedotčený."""

import json
from datetime import UTC, datetime

FIELDS = {"purpose", "goal", "architecture", "technologies", "notes", "requirements"}

# Zdroj (soubor nebo celý kořen) chybí: liší se od "verze neznámá" (None) i od
# porušení hranice (ValueError). Už uložená dokumentace zůstává čitelná, jen bez
# detekce změn; k nikdy neexistující cestě ale dokumentaci vytvořit nelze.
MISSING = object()


class WorkspaceDocuments:
    def __init__(self, service, sources):
        self.service = service
        self.sources = sources

    def _source_version(self, project, workspace, path):
        from backend.project.workspace.workspace_sources import SourceMissing

        try:
            root = self.sources.root(project, workspace)
        except SourceMissing:
            return MISSING
        if root is None:
            if path:
                raise ValueError("Projekt nemá připojený zdroj.")
            return None
        try:
            target = self.sources.target(root, path)
            info = target.stat()
        except FileNotFoundError:
            # Jen skutečně chybějící cesta; kontroly traversalu a reparse bodů
            # v `target` dál vyhazují ValueError a nejsou tímto oslabeny.
            return MISSING
        # Metadata souboru jsou indikátor změny, nikoli důkaz obsahu či splnění.
        return json.dumps([info.st_mtime_ns, info.st_size, info.st_ino]) if target.is_file() else None

    def _row(self, scope):
        return self.service.db_for(scope[0]).execute(
            "SELECT * FROM workspace_documents WHERE project=? AND workspace=? AND path=?", scope
        ).fetchone()

    def _response(self, scope, row, version):
        if version is MISSING and row is None:
            raise ValueError("Tato cesta ve zdroji neexistuje; dokumentovat lze jen existující cestu.")
        fields = json.loads(row["fields"]) if row else dict.fromkeys(sorted(FIELDS), "")
        settings = self.service.project_hub.settings(scope[0]) if scope[2] == "" else None
        if settings:
            fields["goal"] = settings["settings"]["goal"]
        return {
            "project": scope[0], "workspace": scope[1], "path": scope[2],
            "revision": row["revision"] if row else 0,
            "fields": fields,
            "settingsRevision": settings["revision"] if settings else None,
            "nodeId": row["node_id"] if row else None,
            "savedAt": row["saved_at"] if row else None,
            "status": (
                "source_missing" if version is MISSING
                else "missing" if row is None
                else "stale" if row["source_version"] != version
                else "documented"
            ),
            "source": "Dokumentace v databázi Canvasu; není důkazem splnění požadavků.",
            "changeDetection": (
                "source_missing" if version is MISSING else "file-metadata" if version else "unavailable"
            ),
        }

    def read(self, project, workspace, path):
        from backend.project.workspace.workspace_sources import relative_path

        path = relative_path(path)
        version = self._source_version(project, workspace, path)
        scope = (project, workspace, path)
        with self.service.reading(project):
            return self._response(scope, self._row(scope), version)

    def save(self, payload):
        from backend.project.workspace.workspace_sources import relative_path

        keys = {"project", "workspace", "path", "expectedRevision", "fields", "nodeId"}
        if payload.get("path") == "":
            keys.add("expectedSettingsRevision")
        if set(payload) != keys:
            raise ValueError("Neplatný formát dokumentace.")
        path = relative_path(payload["path"])
        fields = payload["fields"]
        if (not isinstance(fields, dict) or set(fields) != FIELDS
                or any(not isinstance(value, str) or len(value) > 16000 for value in fields.values())):
            raise ValueError("Neplatná pole dokumentace (nejvýše 16000 znaků na pole).")
        if type(payload["expectedRevision"]) is not int or payload["expectedRevision"] < 0:
            raise ValueError("Neplatná revize dokumentace.")
        node = payload["nodeId"]
        if node is not None:
            from backend.canvas.graph import valid_id

            if not valid_id(node):
                raise ValueError("Neplatný uzel dokumentace.")
            view = self.service.view(payload["project"], payload["workspace"])
            if not any(item["id"] == node for item in view["graph"]["nodes"]):
                raise ValueError("Uzel není součástí tohoto pracovního prostoru.")
        version = self._source_version(payload["project"], payload["workspace"], path)
        scope = (payload["project"], payload["workspace"], path)
        db = self.service.db_for(scope[0])
        with self.service.lock_for(scope[0]), db:
            db.execute("BEGIN IMMEDIATE")
            row = self._row(scope)
            if version is MISSING and row is None:
                raise ValueError("Tato cesta ve zdroji neexistuje; dokumentovat lze jen existující cestu.")
            revision = row["revision"] if row else 0
            if revision != payload["expectedRevision"]:
                raise ValueError("Dokumentace se změnila v jiném okně. Rozepsaný text zachovejte.")
            if path == "":
                settings = self.service.project_hub.settings(scope[0])
                if type(payload["expectedSettingsRevision"]) is not int or payload["expectedSettingsRevision"] != settings["revision"]:
                    raise ValueError("Cíl nebo nastavení projektu se změnilo. Rozepsaný text zachovejte.")
                if len(fields["goal"]) > 4000:
                    raise ValueError("Cíl projektu může mít nejvýše 4000 znaků.")
                values = settings["settings"]
                if fields["goal"] != values["goal"]:
                    self.service.project_hub.write_settings(
                        scope[0], settings["revision"] + 1, fields["goal"], values["platform"])
            stored_fields = {**fields, "goal": ""} if path == "" else fields
            db.execute(
                "INSERT OR REPLACE INTO workspace_documents VALUES(?,?,?,?,?,?,?,?)",
                # Chybějící zdroj se ukládá jako neznámá verze; až se soubor vrátí,
                # dokumentace se poctivě označí jako "stale", ne jako aktuální.
                (*scope, revision + 1, json.dumps(stored_fields, ensure_ascii=False), node,
                 None if version is MISSING else version, datetime.now(UTC).isoformat()),
            )
            result = self._response(scope, self._row(scope), version)
        return result
