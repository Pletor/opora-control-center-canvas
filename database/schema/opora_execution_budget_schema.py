"""Additive permanent execution-budget enrollment and immutable family consumption."""

BUDGET_TABLES = (
    "opora_execution_budget_policies",
    "opora_execution_budget_refs",
    "opora_execution_budget_enrollment",
    "opora_execution_budget_ledger",
    "opora_execution_budget_requests",
    "opora_execution_budget_clock",
    "opora_execution_budget_cancels",
)
BUDGET_SCHEMA = """
CREATE TABLE IF NOT EXISTS opora_execution_budget_policies(
 project_id TEXT NOT NULL,workspace_id TEXT NOT NULL,node_id TEXT NOT NULL,id TEXT NOT NULL,content TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,node_id,id));
CREATE TABLE IF NOT EXISTS opora_execution_budget_refs(
 project_id TEXT NOT NULL,workspace_id TEXT NOT NULL,node_id TEXT NOT NULL,policy_id TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,node_id));
CREATE TABLE IF NOT EXISTS opora_execution_budget_enrollment(
 project_id TEXT NOT NULL,workspace_id TEXT NOT NULL,node_id TEXT NOT NULL,first_policy_id TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,node_id));
CREATE TABLE IF NOT EXISTS opora_execution_budget_ledger(
 project_id TEXT NOT NULL,workspace_id TEXT NOT NULL,node_id TEXT NOT NULL,accepted_revision TEXT NOT NULL,
 family_id TEXT NOT NULL,sequence INTEGER NOT NULL,id TEXT NOT NULL,kind TEXT NOT NULL,
 execution_id TEXT NOT NULL,content TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,family_id,sequence),UNIQUE(project_id,workspace_id,id),
 UNIQUE(project_id,workspace_id,execution_id));
CREATE TABLE IF NOT EXISTS opora_execution_budget_requests(
 project_id TEXT NOT NULL,workspace_id TEXT NOT NULL,request_id TEXT NOT NULL,digest TEXT NOT NULL,
 result TEXT NOT NULL,PRIMARY KEY(project_id,workspace_id,request_id));
CREATE TABLE IF NOT EXISTS opora_execution_budget_clock(
 id INTEGER PRIMARY KEY CHECK(id=1),high_water REAL NOT NULL,frozen INTEGER NOT NULL CHECK(frozen IN(0,1)),project_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS opora_execution_budget_cancels(
 project_id TEXT NOT NULL,workspace_id TEXT NOT NULL,id TEXT NOT NULL,execution_id TEXT NOT NULL,content TEXT NOT NULL,
 PRIMARY KEY(project_id,workspace_id,id));
"""
