"""Dávka plánu `POST /api/canvas-plan` (`docs/davka-planu.md` §3): přidá na plátno uzly,
vazby, spec, text, bloky s porty, pravidla a rozhodnutí. Buď projde celá, nebo nic.

Postup: pod zámkem grafu se načte graf (podle `digest`) a stav Desktop v3 (jeho revize),
dávka se sestaví v paměti (`canvas_plan_build`) a projde stávajícími validátory — graf
(`validate_graph` + ověření zdrojů jako `save_graph`), stav (`validate_state`), spec
(`node_specs.validate_payload`) a text (`node_text.validate_payload`). Teprve pak se zapisuje.

Pořadí zápisů: spec, text i stav leží v SQLite projektu, a tak jdou do jedné transakce
(`BEGIN IMMEDIATE`). Graf se zapisuje poslední, stále uvnitř té transakce, stávajícím
`save_graph`: u lokálního projektu leží graf ve stejné databázi a jeho `commit` potvrdí všechno
naráz; u Git prostoru se soubor grafu přepíše atomicky (`os.replace`) a teprve potom se
transakce potvrdí. Když zápis grafu selže, transakce se vrátí a nic nezůstane. Zbývá jen
úzké okno mezi přepsáním souboru a `commit` — tehdy by na plátně byly karty bez obsahu,
nikdy obsah bez karet (nová UUID nikdo jiný nezná).
"""

import json

from backend.canvas.canvas_plan_build import build
from backend.canvas.canvas_plan_layout import layout
from backend.canvas.canvas_plan_summary import plan_summary
from backend.canvas.canvas_service import now
from backend.canvas.graph import validate_graph
from backend.editor.agent_memory.desktop_v3_state import DesktopV3State, validate_state
from backend.editor.node import node_specs, node_text

REQUEST_KEYS = {"project", "workspace", "digest", "dryRun", "plan"}


def _request(payload):
    if (
        not isinstance(payload, dict)
        or not set(payload) <= REQUEST_KEYS
        or not {"project", "workspace", "digest", "plan"} <= set(payload)
    ):
        raise ValueError("Neplatný formát dávky plánu (project, workspace, digest, plan, dryRun).")
    dry = payload.get("dryRun", False)
    if type(dry) is not bool:
        raise ValueError("dryRun musí být true/false.")
    return payload["project"], payload["workspace"], payload["digest"], dry, payload["plan"]


def _named(error, labels):
    """Chyba stávajícího validátoru s novými id přeloženými na jména položek dávky."""
    message = str(error)
    for item_id, label in labels.items():
        message = message.replace(item_id, label)
    return message


def _ordered(nodes):
    """Nové uzly tak, aby rodič z dávky šel před potomkem; cyklus zůstane na konci."""
    pending, done, ordered = list(nodes), set(), []
    new_ids = {node["id"] for node in nodes}
    while pending:
        ready = [n for n in pending if n["parentId"] not in new_ids or n["parentId"] in done]
        if not ready:
            return ordered + pending
        for node in ready:
            ordered.append(node)
            done.add(node["id"])
        pending = [n for n in pending if n["id"] not in done]
    return ordered


def _check_graph(service, project, workspace, current, built):
    """Celý nový graf projde validací grafu a zdrojů; při chybě najde první vadnou položku."""
    def check(graph):
        validate_graph(graph)
        service._verify_source_refs(project, workspace, current, graph)

    try:
        check(built.new_graph())
        return
    except ValueError as error:
        whole = error
    nodes, edges = list(current["nodes"]), list(current["edges"])
    for item, into in [*((n, nodes) for n in _ordered(built.nodes)), *((e, edges) for e in built.edges)]:
        into.append(item)
        try:
            check({"nodes": nodes, "edges": edges})
        except ValueError as error:
            raise ValueError(f"{built.labels[item['id']]}: {error}") from error
    raise ValueError(_named(whole, built.labels))


def _check_content(project, workspace, built):
    for node_id, fields in built.specs.items():
        try:
            node_specs.validate_payload({"project": project, "workspace": workspace, "node": node_id,
                                         "expected_revision": 0, "fields": fields})
        except ValueError as error:
            raise ValueError(f"{built.labels[node_id]}: {error}") from error
    for node_id, text in built.texts.items():
        try:
            node_text.validate_payload({"project": project, "workspace": workspace, "node": node_id,
                                        "expected_revision": 0, "text": text})
        except ValueError as error:
            raise ValueError(f"{built.labels[node_id]}: {error}") from error
    if built.state_changed:
        try:
            validate_state(built.state)
        except ValueError as error:
            raise ValueError(_named(error, built.labels)) from error


def apply_plan(service, payload, *, actor="system"):
    project, workspace, expected_digest, dry, plan = _request(payload)
    store = getattr(service, "desktop_v3_state", None) or DesktopV3State(service)
    with service.graph_lock:
        view = service.view(project, workspace)
        if view["readOnly"]:
            raise ValueError("Čistý main je pouze pro čtení. Vytvořte pracovní prostor.")
        if view["digest"] != expected_digest:
            raise ValueError("Plátno se změnilo v jiném okně. Obnovte ho.")
        with service.lock:
            stored = store.current(project, workspace)
        built = build(plan, view["graph"], stored["state"])
        if actor not in ("human", "system"):
            # Pravidla z dávky agenta jsou návrhy, dokud je neschválí člověk (upgrade-opora #37).
            from backend.editor.agent_memory.desktop_v3_state import stamp_agent_rules
            stamp_agent_rules(actor, stored["state"]["rules"], built.state["rules"])
        if any(revision != stored["revision"] for revision in built.extend_revisions):
            raise ValueError("Rozšíření má zastaralou expectedRevision stavu.")
        # `fragmentRef` míří na živý fragment schránky téhož projektu a prostoru (bez revize = poslední).
        from backend.editor.brief_vault.brief_vault_refs import resolve_plan_refs
        with service.lock:
            resolve_plan_refs(service.db_for(project), project, workspace, built)
        for node_id, kind, expected, value in built.documents:
            if kind == "spec":
                current = service.node_spec(project, workspace, node_id)
                if not isinstance(value, dict):
                    raise ValueError("Rozšíření spec.fields musí být objekt.")
                built.specs[node_id] = {**current["fields"], **value}
                built.spec_revisions[node_id] = expected
            else:
                current = service.texts.read((project, workspace, node_id))
                built.texts[node_id] = value
                built.text_revisions[node_id] = expected
            if current["revision"] != expected:
                raise ValueError(f"{node_id}: zastaralá revize {kind}.")
        _check_graph(service, project, workspace, view["graph"], built)
        _check_content(project, workspace, built)
        missing = layout(built.nodes, built.graph["nodes"], built.inside, built.positions)
        if missing is not None:
            raise ValueError(f"{built.labels[missing]}: karta se nevejde do oblasti; zvětšete její size.")
        # Placement may shift a requested point; validate the actual graph before persistence.
        _check_graph(service, project, workspace, view["graph"], built)
        if actor not in ("human", "system"):
            # Rozšíření existující karty nesmí měnit bránu, kontroly ani vazby sektorů (upgrade-opora #30);
            # hlídá se i v dryRun, aby agent chybu viděl dřív, než dávku pošle.
            from backend.canvas.activity_log import HumanRequired
            from backend.canvas.protected_fields import protected_changes
            changes = protected_changes(view["graph"], built.new_graph())
            if changes:
                raise HumanRequired(actor, "Tato pole mění jen člověk v UI: " + ", ".join(changes[:10]))
        result = {"ok": True, "dryRun": dry, "refs": built.refs, "blocks": built.blocks,
                  "summary": plan_summary(plan)}
        if dry:
            return {**result, "digest": view["digest"], "revision": stored["revision"]}
        revision = _write(service, store, project, workspace, expected_digest, stored["revision"], built)
        return {**result, "digest": service.view(project, workspace)["digest"], "revision": revision}


def _write(service, store, project, workspace, expected_digest, revision, built):
    """Spec, text a stav v jedné transakci, graf poslední (viz docstring modulu)."""
    db = service.db_for(project)
    saved_at = now()
    with service.lock, db:
        db.execute("BEGIN IMMEDIATE")
        if store.current(project, workspace)["revision"] != revision:
            raise ValueError("Stav se změnil v jiném okně (revize nesouhlasí). Obnovte jej.")
        for node_id, fields in built.specs.items():
            expected = built.spec_revisions.get(node_id, 0)
            actual = db.execute("SELECT COALESCE(MAX(revision),0) FROM node_spec_revisions WHERE project_id=? AND workspace_id=? AND node_id=?", (project, workspace, node_id)).fetchone()[0]
            if actual != expected:
                raise ValueError("Specifikace se během dávky změnila.")
            db.execute("INSERT INTO node_spec_revisions VALUES(?,?,?,?,?,?)",
                       (project, workspace, node_id, expected + 1, json.dumps(fields, ensure_ascii=False), saved_at))
        for node_id, text in built.texts.items():
            expected = built.text_revisions.get(node_id, 0)
            actual = db.execute("SELECT COALESCE(MAX(revision),0) FROM node_text_revisions WHERE project_id=? AND workspace_id=? AND node_id=?", (project, workspace, node_id)).fetchone()[0]
            if actual != expected:
                raise ValueError("Text se během dávky změnil.")
            db.execute("INSERT INTO node_text_revisions VALUES(?,?,?,?,?,?)",
                       (project, workspace, node_id, expected + 1, text, saved_at))
        if built.state_changed:
            revision += 1
            db.execute("INSERT OR REPLACE INTO desktop_v3_state VALUES(?,?,?,?,?)",
                       (project, workspace, revision, json.dumps(built.state, ensure_ascii=False), saved_at))
        service.save_graph(project, workspace, built.new_graph(), expected_digest)
    return revision
