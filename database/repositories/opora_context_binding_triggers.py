"""Fixed registry dependencies and guards, shared with exact coverage checks."""

SOURCES = {
    "projects": "id name repo url branch",
    "project_sources": "project_id source_kind source_path",
    "builtin_project_metadata": "project_id name",
    "workspaces": "id project_id directory branch node_id actor base_sha",
    "archived_projects": "project_id snapshot archived_at",
    "archived_workspaces": "id project_id node_id branch actor base_sha directory reason archived_at",
}
TABLE = "opora_context_bindings"


def statements():
    guards = {
        "delete": f"BEFORE DELETE ON {TABLE} BEGIN SELECT RAISE(ABORT,'Permanent registry binding'); END",
        "replace": f"BEFORE INSERT ON {TABLE} WHEN EXISTS(SELECT 1 FROM {TABLE} WHERE project_id=NEW.project_id AND workspace_id=NEW.workspace_id) BEGIN SELECT RAISE(ABORT,'Permanent registry binding'); END",
        "identity": f"BEFORE UPDATE ON {TABLE} WHEN NEW.project_id IS NOT OLD.project_id OR NEW.workspace_id IS NOT OLD.workspace_id OR NEW.identity IS NOT OLD.identity OR NEW.schema_digest IS NOT OLD.schema_digest OR NEW.trigger_digest IS NOT OLD.trigger_digest OR NEW.schema_version IS NOT OLD.schema_version OR NEW.generation NOT IN (OLD.generation,OLD.generation+1) OR typeof(NEW.generation)!='integer' OR (OLD.frozen IS NOT NULL AND NEW.frozen IS NOT OLD.frozen) BEGIN SELECT RAISE(ABORT,'Permanent registry binding'); END",
    }
    result = {"opora_binding_" + name: body for name, body in guards.items()}
    for table in SOURCES:
        for operation in ("INSERT", "UPDATE", "DELETE"):
            aliases = ("NEW",) if operation == "INSERT" else (("OLD",) if operation == "DELETE" else ("OLD", "NEW"))
            scopes = []
            for alias in aliases:
                project = f"{alias}." + ("id" if table == "projects" else "project_id")
                scope = f"project_id={project}"
                if table in ("workspaces", "archived_workspaces"):
                    scope += f" AND workspace_id={alias}.id"
                scopes.append("(" + scope + ")")
            where = " OR ".join(scopes)
            body = f"AFTER {operation} ON {table} BEGIN UPDATE {TABLE} SET generation=CASE WHEN generation<2147483647 THEN generation+1 ELSE generation END, frozen=CASE WHEN (SELECT recursive_triggers FROM pragma_recursive_triggers)=0 THEN 'recursive triggers disabled' WHEN generation>=2147483647 THEN 'generation exhausted' ELSE frozen END WHERE {where}; END"
            result[f"opora_binding_{table}_{operation.lower()}"] = body
    return {name: f"CREATE TRIGGER {name} {body}" for name, body in result.items()}


def verify(db):
    actual = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'opora_binding_%'"))
    if actual != statements():
        raise ValueError("Registry binding trigger coverage unavailable.")
    return actual
