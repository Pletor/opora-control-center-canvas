import uuid
from pathlib import Path

from backend.canvas.graph import EMPTY, encode, valid_id

PLATFORMS = {"web", "app", "component"}
# Profil projektu (docs/suplik-a-profil.md): "" = nenastaveno, podle pole se pak nic nefiltruje.
ARCHITECTURES = {"", "monolith", "modular", "microservices", "serverless"}
TENANCIES = {"", "single", "multi"}
DEFAULT_PROFILE = {"architecture": "", "tenancy": ""}
DEFAULT_SETTINGS = {"goal": "", "platform": "web", **DEFAULT_PROFILE}


class ProjectHub:
    """Registry metadata for non-Git projects; source folders are never read or changed."""

    def __init__(self, canvas):
        self.canvas = canvas
        canvas.db.execute("INSERT OR IGNORE INTO builtin_project_metadata VALUES('draft',?)", ("Lokální návrh",))
        canvas.db.commit()

    def write_settings(self, pid, revision, goal, platform):
        """Jediný zápis project_settings; leží v databázi projektu."""
        self.canvas.db_for(pid).execute(
            "INSERT OR REPLACE INTO project_settings(project_id,revision,goal,platform) VALUES(?,?,?,?)",
            (pid, revision, goal, platform),
        )

    def write_profile(self, pid, architecture, tenancy):
        """Profil leží ve vlastní tabulce, aby starší project_settings zůstala beze změny schématu."""
        self.canvas.db_for(pid).execute(
            "INSERT OR REPLACE INTO project_profile(project_id,architecture,tenancy) VALUES(?,?,?)",
            (pid, architecture, tenancy),
        )

    def _profile(self, pid):
        row = self.canvas.db_for(pid).execute(
            "SELECT architecture,tenancy FROM project_profile WHERE project_id=?", (pid,)
        ).fetchone()
        if row is None:
            return dict(DEFAULT_PROFILE)
        # Hodnota, kterou dnešní verze nezná, se čte jako nenastaveno: profil pak nic neskrývá.
        return {
            "architecture": row["architecture"] if row["architecture"] in ARCHITECTURES else "",
            "tenancy": row["tenancy"] if row["tenancy"] in TENANCIES else "",
        }

    def source_info(self, project):
        if isinstance(project, str):
            project = self.canvas.row("projects", project)
        row = self.canvas.db.execute(
            "SELECT source_kind,source_path FROM project_sources WHERE project_id=?", (project["id"],)
        ).fetchone()
        if row is None:
            return {"sourceKind": "git", "sourcePath": project["repo"]}
        return {"sourceKind": row["source_kind"], "sourcePath": row["source_path"]}

    def _project(self, pid):
        if pid == "draft":
            name = self.canvas.db.execute(
                "SELECT name FROM builtin_project_metadata WHERE project_id='draft'"
            ).fetchone()[0]
            return {"id": "draft", "name": name, "url": None, "branch": None, "sourceKind": "builtin", "sourcePath": None}
        project = self.canvas.row("projects", pid)
        return {key: project.get(key) for key in ("id", "name", "url", "branch")} | self.source_info(project)

    def _settings(self, pid):
        row = self.canvas.db_for(pid).execute(
            "SELECT revision,goal,platform FROM project_settings WHERE project_id=?", (pid,)
        ).fetchone()
        profile = self._profile(pid)
        if row is None:
            return 0, {**DEFAULT_SETTINGS, **profile}
        return row["revision"], {"goal": row["goal"], "platform": row["platform"], **profile}

    def settings(self, project):
        if not isinstance(project, str) or (project != "draft" and not valid_id(project)):
            raise ValueError("Neplatný identifikátor projektu.")
        with self.canvas.lock:
            item = self._project(project)
            revision, values = self._settings(project)
            return {"project": item, "revision": revision, "settings": values}

    def _validate_name(self, name):
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            raise ValueError("Název projektu je povinný a může mít nejvýše 120 znaků.")
        return name.strip()

    def _validate_settings(self, values):
        if not isinstance(values, dict) or set(values) != set(DEFAULT_SETTINGS):
            raise ValueError("Neplatný formát nastavení projektu.")
        goal = values["goal"]
        if not isinstance(goal, str) or len(goal) > 4000:
            raise ValueError("Neplatný cíl projektu.")
        if not isinstance(values["platform"], str) or values["platform"] not in PLATFORMS:
            raise ValueError("Neplatná platforma projektu.")
        if not isinstance(values["architecture"], str) or values["architecture"] not in ARCHITECTURES:
            raise ValueError("Neplatná architektura projektu.")
        if not isinstance(values["tenancy"], str) or values["tenancy"] not in TENANCIES:
            raise ValueError("Neplatné rozdělení uživatelů projektu.")

    def save_settings(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"project", "expected_revision", "name", "settings"}:
            raise ValueError("Neplatný formát uložení nastavení projektu.")
        pid = payload["project"]
        if not isinstance(pid, str) or (pid != "draft" and not valid_id(pid)) or type(payload["expected_revision"]) is not int or payload["expected_revision"] < 0:
            raise ValueError("Neplatná očekávaná revize nastavení.")
        name = self._validate_name(payload["name"])
        self._validate_settings(payload["settings"])
        with self.canvas.lock:
            self._project(pid)  # verifies registry and archive state
            db = self.canvas.db_for(pid)
            with db:
                db.execute("BEGIN IMMEDIATE")
                revision, _ = self._settings(pid)
                if revision != payload["expected_revision"]:
                    raise ValueError("Nastavení se změnilo v jiném okně. Obnovte je.")
                values = payload["settings"]
                self.write_settings(pid, revision + 1, values["goal"], values["platform"])
                self.write_profile(pid, values["architecture"], values["tenancy"])
            with self.canvas.db:
                if pid == "draft":
                    self.canvas.db.execute("UPDATE builtin_project_metadata SET name=? WHERE project_id='draft'", (name,))
                else:
                    self.canvas.db.execute("UPDATE projects SET name=? WHERE id=?", (name, pid))
            folder = self.canvas.folder(pid)
            if folder.exists():
                folder.update(name=name, settings={**{key: values[key] for key in DEFAULT_SETTINGS}, "revision": revision + 1})
        return self.settings(pid)

    def _new(self, name, kind, path=None):
        pid = uuid.uuid4().hex
        folder = self.canvas.folder(pid)
        if kind == "empty":
            # Prázdný projekt má zdroj přímo ve své složce: projects/<id>/main
            path = str(folder.main.resolve())
        with self.canvas.lock:
            folder.create(name, kind, path or "")
            with self.canvas.db:
                self.canvas.db.execute("INSERT INTO projects VALUES(?,?,?,?,?)", (pid, name, "", "", ""))
                self.canvas.db.execute("INSERT INTO project_sources VALUES(?,?,?)", (pid, kind, path))
            db = self.canvas.db_for(pid)
            with db:
                db.execute("INSERT INTO drafts VALUES(?,?)", (pid, encode(EMPTY)))
        return self._project(pid)

    def local_project(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"name", "path", "confirmed"} or payload["confirmed"] is not True:
            raise ValueError("Připojení lokální složky vyžaduje potvrzení.")
        name = self._validate_name(payload["name"])
        path = payload["path"]
        if not isinstance(path, str) or not path or not Path(path).is_absolute():
            raise ValueError("Lokální složka musí mít explicitní absolutní cestu.")
        resolved = Path(path).resolve()
        if not resolved.is_dir():
            raise ValueError("Lokální složka neexistuje nebo není adresář.")
        canonical = str(resolved)
        with self.canvas.lock, self.canvas.db:
            self.canvas.db.execute("BEGIN IMMEDIATE")
            existing = self.canvas.db.execute(
                """SELECT p.* FROM projects p JOIN project_sources s ON s.project_id=p.id
                   WHERE s.source_kind='local' AND s.source_path=? COLLATE NOCASE
                   AND p.id NOT IN (SELECT project_id FROM archived_projects)""", (canonical,)
            ).fetchone()
            if existing is not None:
                return self._project(existing["id"])
            return self._new(name, "local", canonical)

    def empty_project(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"name", "confirmed"} or payload["confirmed"] is not True:
            raise ValueError("Vytvoření prázdného projektu vyžaduje potvrzení.")
        return self._new(self._validate_name(payload["name"]), "empty")
