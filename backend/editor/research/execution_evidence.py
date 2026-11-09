"""Scoped research evidence for native immutable assignments; no new execution authority."""
import json

from backend.canvas.graph import digest


def _read(db, project, workspace, kind, identifier, revision=None):
    table = {"card": "research_card_revisions", "edge": "research_edge_revisions"}[kind]
    where, values = (" AND revision=?", (revision,)) if revision is not None else ("", ())
    row = db.execute(f"SELECT payload FROM {table} WHERE project_id=? AND workspace_id=? AND id=?"
                     + where + " ORDER BY revision DESC LIMIT 1", (project, workspace, identifier, *values)).fetchone()
    if row is None:
        raise ValueError("Referenced research evidence is missing from this workspace.")
    return json.loads(row[0])


def imported_pins(db, project, workspace, question, result, *, source_fragment=None):
    """Pin only this question's imported component; another question is a traversal boundary."""
    cards = {card["id"]: card for card in result["cards"]}
    rows = db.execute("SELECT payload FROM research_edge_revisions t WHERE project_id=? AND workspace_id=? "
                      "AND revision=(SELECT MAX(revision) FROM research_edge_revisions WHERE project_id=t.project_id "
                      "AND workspace_id=t.workspace_id AND id=t.id)", (project, workspace))
    edges = [json.loads(row[0]) for row in rows]

    def card(key):
        if key not in cards:
            cards[key] = _read(db, project, workspace, "card", key)
        return cards[key]
    selected = {question}
    selected.update(key for key, value in cards.items() if value["kind"] != "question"
                    and question in value["refs"]["questionIds"]
                    and (source_fragment is None or not value["refs"]["fragmentIds"]
                         or source_fragment in value["refs"]["fragmentIds"]))
    while True:
        before = set(selected)
        for edge in edges:
            ends = {edge["fromId"], edge["toId"]}
            if ends & selected and not edge["archived"]:
                if any(key != question and card(key)["kind"] == "question" for key in ends):
                    continue
                if source_fragment is not None and any(card(key)["refs"]["fragmentIds"]
                        and source_fragment not in card(key)["refs"]["fragmentIds"]
                        for key in ends | set(edge["evidenceIds"])):
                    continue  # An explicitly different original is a source boundary too.
                selected.update(key for key in ends | set(edge["evidenceIds"])
                                if key == question or card(key)["kind"] != "question")
        if before == selected:
            break
    wanted = [("card", key, cards[key]["revision"]) for key in sorted(selected)]
    wanted += [("edge", edge["id"], edge["revision"]) for edge in edges
               if not edge["archived"] and edge["fromId"] in selected and edge["toId"] in selected
               and (source_fragment is None or not any(card(key)["refs"]["fragmentIds"]
                    and source_fragment not in card(key)["refs"]["fragmentIds"]
                    for key in {edge["fromId"], edge["toId"]} | set(edge["evidenceIds"])))]
    return {"coverage": "scoped-question-component", "originalSourceCoverage": "reference-only",
            "items": [{"kind": kind, "id": key, "revision": revision,
                       "digest": digest(_read(db, project, workspace, kind, key, revision))}
                      for kind, key, revision in sorted(wanted)]}


INPUT_FIELDS = ("title", "text", "kind", "parent_id", "scope_node_id", "discipline", "deleted")


def original_input(db, project, workspace, identifier, revision):
    row = db.execute("SELECT * FROM brief_fragment_revisions WHERE project_id=? AND workspace_id=? "
                     "AND fragment_id=? AND revision=?", (project, workspace, identifier, revision)).fetchone()
    if row is None:
        raise ValueError("Original research input is unavailable.")
    details = db.execute("SELECT revision,fields FROM brief_fragment_details WHERE project_id=? AND workspace_id=? "
                         "AND fragment_id=? AND saved_at<=? ORDER BY revision DESC LIMIT 1",
                         (project, workspace, identifier, row["saved_at"])).fetchone()
    if details is None:
        raise ValueError("Original research input is unavailable.")
    pin = {"id": identifier, "fragmentRevision": row["revision"], "detailsRevision": details[0],
            "fragmentDigest": digest({key: row[key] for key in INPUT_FIELDS}),
            "questionDigest": digest(json.loads(details[1]).get("research", {}).get("question"))}
    validate_original(db, project, workspace, pin)
    return pin


def validate_original(db, project, workspace, pin):
    # Inspect every semantic input since capture, so a changed-then-restored question is still stale.
    rows = db.execute("SELECT * FROM brief_fragment_revisions WHERE project_id=? AND workspace_id=? "
                      "AND fragment_id=? AND revision>=?", (project, workspace, pin["id"], pin["fragmentRevision"])).fetchall()
    details = db.execute("SELECT fields FROM brief_fragment_details WHERE project_id=? AND workspace_id=? "
                         "AND fragment_id=? AND revision>=?", (project, workspace, pin["id"], pin["detailsRevision"])).fetchall()
    if (not rows or not details or any(digest({key: row[key] for key in INPUT_FIELDS}) != pin["fragmentDigest"] for row in rows)
            or any(digest(json.loads(row[0]).get("research", {}).get("question")) != pin["questionDigest"] for row in details)):
        raise ValueError("Original research input changed; affected work needs reassessment.")


def collect(db, project, workspace, head, card_ids, *, canvas=None):
    """Follow accepted history; only latest provenance for the same source and target supersedes it."""
    from backend.editor.research.accepted_history import read as accepted_history
    history, drafts = accepted_history(db, project, workspace, head, canvas)
    records, covered = [], set()
    legacy_fragments = []

    def add(source, targets, proposal_id=None, operation_id=None):
        targets = {key for key in targets if (key, source["researchId"]) not in covered
                   and (key, "original:" + source["sourceFragmentId"]) not in covered}
        if not targets:
            return
        row = db.execute("SELECT payload FROM research_continuations WHERE project_id=? AND workspace_id=? AND id=?",
                         (project, workspace, source["continuationId"])).fetchone()
        if row is None:
            raise ValueError("Accepted research continuation is missing.")
        receipt = json.loads(row[0])
        from backend.editor.research.planning_source import pins
        if source != pins(receipt) or (operation_id is not None and operation_id != receipt["operationId"]):
            raise ValueError("Accepted research provenance conflicts with its continuation.")
        evidence = receipt.get("evidence")
        if evidence is None:
            card = _read(db, project, workspace, "card", source["researchId"], source["researchRevision"])
            evidence = {"coverage": "legacy-question-only", "originalSourceCoverage": "reference-only",
                        "items": [{"kind": "card", "id": card["id"], "revision": card["revision"], "digest": digest(card)}]}
        records.append({"proposalId": proposal_id, "operationId": operation_id, "nodeIds": sorted(targets),
                        "source": source, "evidence": evidence})
        covered.update((key, source["researchId"]) for key in targets)
        covered.update((key, "original:" + source["sourceFragmentId"]) for key in targets)

    for proposal in history:
        source = proposal["source"]
        observed = proposal["observed"]
        if observed is not None:
            for node in set(observed) & set(card_ids):
                for pin in observed[node]:
                    key = (node, "original:" + pin["sourceId"])
                    if key in covered:
                        continue
                    records.append({"proposalId": proposal["id"], "operationId": None, "nodeIds": [node],
                                    "source": {name: value for name, value in pin.items() if name != "evidence"},
                                    "evidence": pin["evidence"]})
                    covered.add(key)
                    covered.update((node, question["id"]) for question in pin["evidence"].get("mappedQuestions", []))
        else:
            # Old accepted proposals are not silently assigned a newly observed source baseline.
            for node in set(proposal["fragments"]) & set(card_ids):
                legacy_fragments.append({"proposalId": proposal["id"], "nodeId": node,
                                         "coverage": "legacy-fragment-reference-untracked"})
        if source and "continuationId" in source:
            add(source, proposal["touched"] & set(card_ids), proposal_id=proposal["id"])
    for source, touched, operation in drafts:
        add(source, touched & set(card_ids), operation_id=operation)
    result = {"coverage": "accepted-scoped-research", "records": records}
    from backend.editor.research.scope_evidence import collect as scope_pins
    canonical = scope_pins(db, project, workspace, card_ids)
    result["canonicalScopes"] = canonical
    if legacy_fragments:
        result["legacyFragments"] = legacy_fragments
    validate(db, project, workspace, result)
    return result


def validate(db, project, workspace, evidence):
    """Revision equality catches edit/restore and archive/unarchive, not merely current content."""
    if "canonicalScopes" in evidence:
        from backend.editor.research.scope_evidence import validate as validate_scopes
        validate_scopes(db, project, workspace, evidence["canonicalScopes"])
    for record in evidence["records"]:
        if record["evidence"].get("originalOutput"):
            from backend.editor.research.finalization import validate_output
            validate_output(db, project, workspace, record["evidence"]["originalOutput"])
        if record["evidence"].get("originalInput"):
            validate_original(db, project, workspace, record["evidence"]["originalInput"])
        for pin in record["evidence"]["items"]:
            current = _read(db, project, workspace, pin["kind"], pin["id"])
            if current["revision"] != pin["revision"] or digest(current) != pin["digest"]:
                raise ValueError("Research evidence changed; affected work needs reassessment.")


def validate_assignment(db, project, workspace, record):
    evidence = record["assignment"].get("researchEvidence")
    if evidence is not None:
        validate(db, project, workspace, evidence)
