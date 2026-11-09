"""SQL byte preflight for native content capture before scene materialization."""


def preflight_source_bytes(db, project, workspace, node_ids, text_owners, limit, extra_bytes=0):
    source_bytes = extra_bytes
    for owner in sorted(set(text_owners.values())):
        placeholders = ",".join("?" for _ in node_ids)
        source_bytes += db.execute(
            f"""SELECT COALESCE(SUM(length(CAST(t.text AS BLOB))),0) FROM node_text_revisions t
                WHERE t.project_id=? AND t.workspace_id=? AND t.node_id IN ({placeholders})
                AND t.revision=(SELECT MAX(x.revision) FROM node_text_revisions x
                                WHERE x.project_id=t.project_id AND x.workspace_id=t.workspace_id
                                  AND x.node_id=t.node_id)""",
            (project, owner, *node_ids),
        ).fetchone()[0]
    drawing_ids = ["", *node_ids]
    placeholders = ",".join("?" for _ in node_ids)
    source_bytes += db.execute(
        f"""SELECT COALESCE(SUM(length(CAST(s.record AS BLOB))),0) FROM storyboard_revisions s
            WHERE s.project_id=? AND s.workspace_id=? AND s.node_id IN ({placeholders})
            AND s.revision=(SELECT MAX(x.revision) FROM storyboard_revisions x
                WHERE x.project_id=s.project_id AND x.workspace_id=s.workspace_id AND x.node_id=s.node_id)""",
        (project, workspace, *node_ids)).fetchone()[0]
    placeholders = ",".join("?" for _ in drawing_ids)
    source_bytes += db.execute(
        f"""SELECT COALESCE(SUM(length(CAST(d.scene AS BLOB))),0) FROM drawing_revisions d
            WHERE d.project_id=? AND d.workspace_id=? AND d.layer_id IN ({placeholders})
            AND d.revision=(SELECT MAX(x.revision) FROM drawing_revisions x
                            WHERE x.project_id=d.project_id AND x.workspace_id=d.workspace_id
                              AND x.layer_id=d.layer_id)""",
        (project, workspace, *drawing_ids),
    ).fetchone()[0]
    return source_bytes <= limit
