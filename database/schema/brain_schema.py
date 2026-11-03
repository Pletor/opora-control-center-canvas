"""Registr Brainu (`backend/brain/registry.py`, kontrakt `docs/navrhy/2026-11-03-novy-zaklad.md` §3.4) v registry.sqlite.

Artefakt je dovednost sdílená napříč projekty (proto registr, ne projekt). Obsah leží v gitu Brainu
(`<datový kořen>/brain/`), verze je SHA commitu a `content_ref` cesta souboru v pluginu. Na artefakt je
nejvýš jedna `active` verze (unikátní index).
"""

TABLES = ("brain_artifacts", "brain_artifact_versions", "brain_links")

SCHEMA = """
CREATE TABLE IF NOT EXISTS brain_artifacts(
  id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('skill','tool','workflow','subagent','connector')),
  plugin TEXT NOT NULL, name TEXT NOT NULL, project_types TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL,
  UNIQUE(plugin, name));
CREATE TABLE IF NOT EXISTS brain_artifact_versions(
  id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES brain_artifacts(id), version TEXT NOT NULL,
  content_ref TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('candidate','active','retired')),
  eval_score REAL, baseline_version_id TEXT REFERENCES brain_artifact_versions(id), created_at TEXT NOT NULL,
  UNIQUE(artifact_id, version));
CREATE UNIQUE INDEX IF NOT EXISTS brain_one_active_version
  ON brain_artifact_versions(artifact_id) WHERE status='active';
CREATE TABLE IF NOT EXISTS brain_links(
  id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES brain_artifact_versions(id),
  target_kind TEXT NOT NULL CHECK(target_kind IN ('log_event','eval_run','canvas_node')),
  target_ref TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS brain_links_version ON brain_links(version_id);
"""
