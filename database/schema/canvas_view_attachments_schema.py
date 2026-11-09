"""Private browser attachment leases; no agent token or browser secret is stored."""
TABLES = ("canvas_view_attachments",)
SCHEMA = """
CREATE TABLE IF NOT EXISTS canvas_view_attachments (
 project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, session_id TEXT NOT NULL,
 attachment_id TEXT NOT NULL, secret_hash TEXT NOT NULL, expires_at REAL NOT NULL,
 acknowledged_revision INTEGER, acknowledged_view TEXT,
 render_epoch INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(project_id,workspace_id,session_id)
);
"""
