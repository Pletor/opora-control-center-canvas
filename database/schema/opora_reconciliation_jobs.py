"""Durable polling jobs and attempt audit; project DB owns transaction boundaries."""
JOB_TABLES = ('opora_reconciliation_jobs', 'opora_reconciliation_attempts')
JOB_SCHEMA = '''
CREATE TABLE IF NOT EXISTS opora_reconciliation_jobs (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, binding_id TEXT NOT NULL,
 generation INTEGER NOT NULL, enabled INTEGER NOT NULL, state TEXT NOT NULL,
 next_attempt_at REAL, claim_epoch INTEGER NOT NULL DEFAULT 0, owner TEXT,
 lease_until REAL, failures INTEGER NOT NULL DEFAULT 0, last_attempt_id TEXT,
 last_observation_id TEXT, last_event_id TEXT, error_code TEXT, provider_retry_until REAL,
 PRIMARY KEY(project_id,workspace_id,binding_id));
CREATE INDEX IF NOT EXISTS opora_reconciliation_due ON opora_reconciliation_jobs(enabled,next_attempt_at);
CREATE TABLE IF NOT EXISTS opora_reconciliation_attempts (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
 binding_id TEXT NOT NULL, epoch INTEGER NOT NULL, generation INTEGER NOT NULL,
 status TEXT NOT NULL, started_at REAL NOT NULL, finished_at REAL,
 error_code TEXT, observation_id TEXT, finish_digest TEXT, receipt TEXT);
'''
