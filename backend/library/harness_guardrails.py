"""Negative selected-kit associations from existing immutable review cases, never causal scores."""


def read(db, project, workspace, cohort, node=None):
    parameters = [project, workspace, cohort["resource"], cohort["versionDigest"], cohort["problem"]]
    where = " AND r.node_id=?" if node is not None else ""
    if node is not None:
        parameters.append(node)
    # A case must name the exact merged run identity and reviewed head, not just a PR number.
    # Incidents are reports (possibly from an agent); a merged revert is a separate recorded fact.
    query = ("SELECT COUNT(DISTINCT r.execution_id),"
             "COUNT(DISTINCT CASE WHEN c.kind='incident' THEN r.execution_id END),"
             "COUNT(DISTINCT CASE WHEN c.kind='revert' THEN r.execution_id END)"
             " FROM harness_learning_runs r"
             " JOIN harness_learning_resources v USING(project_id,workspace_id,execution_id)"
             " JOIN harness_learning_problems p USING(project_id,workspace_id,execution_id)"
             " JOIN opora_execution_pull_requests x USING(project_id,workspace_id,execution_id)"
             " JOIN opora_review_eval_cases c ON c.project_id=r.project_id AND c.workspace_id=r.workspace_id"
             " AND c.repository=x.repository AND c.number=x.number"
             " WHERE r.project_id=? AND r.workspace_id=? AND v.resource_id=? AND v.version_digest=?"
             " AND p.problem=? AND x.node_id=r.node_id AND x.accepted_revision=r.accepted_revision"
             " AND x.state='merged' AND x.merge_sha IS NOT NULL AND x.merge_sha<>''"
             " AND json_extract(c.content,'$.headSha')=x.head_sha"
             " AND json_extract(c.content,'$.mergeSha')=x.merge_sha"
             " AND ((c.kind='incident' AND EXISTS(SELECT 1 FROM opora_review_incidents i"
             " WHERE i.project_id=c.project_id AND i.workspace_id=c.workspace_id AND i.incident_id=c.source"
             " AND i.repository=c.repository AND i.number=c.number))"
             " OR (c.kind='revert' AND EXISTS(SELECT 1 FROM opora_review_reverts z"
             " WHERE z.project_id=c.project_id AND z.repository=c.repository AND z.number=c.number"
             " AND z.revert_number=json_extract(c.content,'$.revertNumber')"
             " AND z.revert_sha=json_extract(c.content,'$.revertSha'))))" + where)
    affected, incidents, reverts = db.execute(query, parameters).fetchone()
    return {"source": "native-review-eval-cases", "affectedExecutions": affected,
            "incidentReportExecutions": incidents, "revertedExecutions": reverts,
            "productionExposure": "unknown", "causalAttribution": False}
