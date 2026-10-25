"""Derived Harness outcomes: source outbox and projection commit together; no outbox FK.

Outbox retention must not erase lifetime aggregates. Additive tables can remain in place
when rolling back to a reader that does not know this feature.
"""
TABLES = ("harness_learning_runs", "harness_learning_resources", "harness_learning_problems",
          "harness_learning_outcomes", "harness_learning_sources", "harness_memory_deliveries")
SCHEMA = """
CREATE TABLE IF NOT EXISTS harness_learning_runs(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, execution_id TEXT NOT NULL,
 node_id TEXT NOT NULL, assignment_digest TEXT NOT NULL, accepted_revision TEXT NOT NULL,
 kit_digest TEXT NOT NULL, enrolled_at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,execution_id));
CREATE TABLE IF NOT EXISTS harness_learning_resources(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, execution_id TEXT NOT NULL,
 resource_id TEXT NOT NULL, content_digest TEXT NOT NULL, version_digest TEXT NOT NULL,
 category TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,execution_id,resource_id));
CREATE INDEX IF NOT EXISTS harness_learning_resource_version
 ON harness_learning_resources(project_id,workspace_id,resource_id,version_digest);
CREATE TABLE IF NOT EXISTS harness_learning_problems(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, execution_id TEXT NOT NULL,
 problem TEXT NOT NULL, PRIMARY KEY(project_id,workspace_id,execution_id,problem));
CREATE TABLE IF NOT EXISTS harness_learning_outcomes(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, execution_id TEXT NOT NULL,
 tier TEXT NOT NULL CHECK(tier IN ('reported','verified')),
 outcome TEXT NOT NULL CHECK(outcome IN ('pass','fail','unknown')),
 source_event INTEGER NOT NULL, reason TEXT NOT NULL, at TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,execution_id,tier));
CREATE TABLE IF NOT EXISTS harness_learning_sources(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, event_id INTEGER NOT NULL,
 kind TEXT NOT NULL, PRIMARY KEY(project_id,workspace_id,event_id));
CREATE TABLE IF NOT EXISTS harness_memory_deliveries(
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, execution_id TEXT NOT NULL,
 source_event INTEGER NOT NULL, resource_id TEXT NOT NULL, node_id TEXT NOT NULL, payload TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('pending','retry','waiting-role','working','submitted','superseded')),
 attempts INTEGER NOT NULL CHECK(attempts>=0), next_attempt REAL NOT NULL,
 lease_owner TEXT NOT NULL, lease_until REAL NOT NULL, role_id TEXT NOT NULL, uri TEXT NOT NULL, error TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,execution_id,source_event,resource_id));
CREATE INDEX IF NOT EXISTS harness_memory_pending ON harness_memory_deliveries(project_id,state,next_attempt);
"""
