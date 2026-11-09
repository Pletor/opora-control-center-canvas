"""Explicit bridge to original research fragments; never rewrite their history or status."""
import hashlib
import json

from backend.editor.research import model, service as research
from backend.editor.brief_vault.brief_vault import BriefVault


def read(service, project, workspace, identifier, revision=None):
    research._scope(service, project, workspace)
    model.identifier(identifier)
    if revision is not None and (type(revision) is not int or revision < 1):
        model.fail("revision must be a positive integer.")
    with service.reading(project):
        db = service.db_for(project)
        row = db.execute("SELECT kind FROM brief_fragment_revisions WHERE project_id=? AND workspace_id=? "
                         "AND fragment_id=? ORDER BY revision DESC LIMIT 1", (project, workspace, identifier)).fetchone()
        if row is None or row[0] != "research":
            model.fail("Original research fragment not found in this workspace.", 404, "research_original_not_found")
        value = BriefVault(service).fragment(project, workspace, identifier, revision)
        histories = {}
        for table in ("brief_fragment_revisions", "brief_fragment_details", "brief_fragment_feedback"):
            cursor = db.execute(f"SELECT * FROM {table} WHERE project_id=? AND workspace_id=? AND fragment_id=?",
                                (project, workspace, identifier))
            names = [column[0] for column in cursor.description]
            histories[table] = [dict(zip(names, record)) for record in cursor.fetchall()]
    # Current details have an independent revision series; return that identity explicitly.
    details_revision = max((row["revision"] for row in histories["brief_fragment_details"]), default=0)
    from backend.brain_opora.determinism.brain_files import brain_dir
    artifact = brain_dir(service, project) / "dilna" / "out" / "research" / (identifier + ".json")
    output = None
    if artifact.is_file():
        try:
            raw = artifact.read_bytes()
            data = json.loads(raw.decode("utf-8-sig"))
            recorded_scope = data.get("scope")
            if recorded_scope is not None and recorded_scope != {"project": project, "workspace": workspace}:
                output = {"error": "Original output declares a different scope; content omitted."}
            else:
                output = {"sha256": hashlib.sha256(raw).hexdigest(), "scopeRecorded": recorded_scope is not None,
                          "content": data, "relation": "original output; may precede current research round"}
        except (OSError, ValueError, AttributeError):
            output = {"error": "Original output could not be read; native fragment history remains available."}
    return {"origin": "brief-vault", "type": "original-research", "project": project, "workspace": workspace,
            "sourceId": identifier, "sourceRevision": value["fragment"]["revision"],
            "detailsRevision": details_revision, "original": value, "sourceHistory": histories, "originalOutput": output,
            "mappedCards": [c for c in research.listing(service, project, workspace, True)["cards"]
                            if identifier in c.get("refs", {}).get("fragmentIds", [])]}


def materialize(service, project, workspace, identifier, revision, details_revision, actor, agent):
    with service.graph_lock_for(project):
        source = read(service, project, workspace, identifier, revision)
        if source["detailsRevision"] != details_revision or revision != source["original"]["latestRevision"]:
            model.fail("Original details revision changed; read it again.", 409, "research_conflict")
        key = hashlib.sha256(json.dumps([project, workspace, identifier, revision, details_revision]).encode()).hexdigest()
        with service.reading(project):
            prior = service.db_for(project).execute("SELECT response FROM research_batches WHERE project_id=? "
                "AND workspace_id=? AND key=?", (project, workspace, "original:" + key)).fetchone()
        if prior:
            return json.loads(prior[0])
        original = source["original"]
        # Preserve evidence verbatim inside full source content. A historic feasible verdict
        # is not verification of present-day claims, and assigned/done is only a run status.
        refs = {name: [] for name in model.REFS}
        refs["fragmentIds"] = [identifier]
        stable = hashlib.sha256(json.dumps([project, workspace, identifier]).encode()).hexdigest()
        card_id = "rc_" + stable[:32]
        mapped = [card for card in source["mappedCards"] if card["kind"] == "question"]
        if len(mapped) > 1:
            model.fail("Original research has multiple mapped questions; reconcile their identities explicitly.",
                       409, "research_mapping_conflict")
        if mapped:
            card_id = mapped[0]["id"]
        with service.reading(project):
            row = service.db_for(project).execute("SELECT payload FROM research_card_revisions WHERE project_id=? "
                "AND workspace_id=? AND id=? ORDER BY revision DESC LIMIT 1", (project, workspace, card_id)).fetchone()
        old = json.loads(row[0]) if row else None
        if old:
            refs = old["refs"]
            refs["fragmentIds"] = list(dict.fromkeys([*refs["fragmentIds"], identifier]))
        detail = original["details"].get("research", {})
        # Full history/evidence stays at the authoritative original endpoint. Copying every
        # round into each map revision grows quadratically and eventually exceeds card limits.
        pointer = {key: source[key] for key in ("origin", "type", "sourceId", "sourceRevision", "detailsRevision")}
        pointer.update(sourceEndpoint="/api/research/originals/" + identifier,
                       sourceScope={"project": project, "workspace": workspace},
                       originalRunStatus=detail.get("status"), originalVerdict=detail.get("verdict"),
                       originalRound=detail.get("round"), evidenceEndpoint="/api/research/originals/" + identifier)
        card = {"op": "card", "id": card_id, "expectedRevision": old["revision"] if old else 0, "kind": "question",
                "title": original["fragment"]["title"], "summary": "Original research; inspect its source revisions and evidence.",
                "content": json.dumps(pointer, ensure_ascii=False),
                "topicPath": old["topicPath"] if old else [original["fragment"]["title"]],
                "status": old["status"] if old else "open",
                "verification": {"status": "unverified", "method": "original research preserved; not reverified", "at": ""},
                "sources": old["sources"] if old else [], "refs": refs}
        return research.apply(service, {"project": project, "workspace": workspace, "key": "original:" + key,
                                        "operations": [card]}, actor, agent)
