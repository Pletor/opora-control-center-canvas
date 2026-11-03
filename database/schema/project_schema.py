"""SQL schéma po tabulkách: registr projektů (registry.sqlite) a databáze jednoho projektu (project.sqlite).

Každá tabulka má jednoho vlastníka v backendu; ten ji čte a píše, ale nevytváří. Vytváření je jen zde.
"""
import sqlite3

from database.schema.brain_schema import SCHEMA as BRAIN_SCHEMA
from database.schema.flow_schema import SCHEMA as FLOW_SCHEMA
from database.schema.guard_experience_schema import SCHEMA as GUARD_EXPERIENCE_SCHEMA
from database.schema.guard_experience_schema import TABLES as GUARD_EXPERIENCE_TABLES
from database.schema.guard_findings_schema import SCHEMA as GUARD_FINDINGS_SCHEMA
from database.schema.guard_findings_schema import TABLES as GUARD_FINDINGS_TABLES
from database.schema.guard_trend_schema import SCHEMA as GUARD_TREND_SCHEMA
from database.schema.guard_trend_schema import TABLES as GUARD_TREND_TABLES
from database.schema.harness_learning_schema import SCHEMA as HARNESS_LEARNING_SCHEMA
from database.schema.harness_learning_schema import TABLES as HARNESS_LEARNING_TABLES
from database.schema.intake_schema import MILESTONES_INDEX, MILESTONES_TABLE
from database.schema.intake_schema import SCHEMA as INTAKE_SCHEMA
from database.schema.journey_run_schema import SCHEMA as JOURNEY_RUN_SCHEMA
from database.schema.journey_run_schema import TABLES as JOURNEY_RUN_TABLES
from database.schema.opora_auto_rebase_schema import SCHEMA as AUTO_REBASE_SCHEMA
from database.schema.opora_auto_rebase_schema import TABLES as AUTO_REBASE_TABLES
from database.schema.opora_content_schema import SCHEMA as CONTENT_SCHEMA
from database.schema.opora_content_schema import TABLES as CONTENT_TABLES
from database.schema.opora_context_binding_schema import SCHEMA as CONTEXT_BINDING_SCHEMA
from database.schema.opora_context_event_schema import SCHEMA as CONTEXT_SCHEMA
from database.schema.opora_context_event_schema import TABLES as CONTEXT_TABLES
from database.schema.opora_design_preview_schema import SCHEMA as DESIGN_PREVIEW_SCHEMA
from database.schema.opora_design_preview_schema import TABLES as DESIGN_PREVIEW_TABLES
from database.schema.opora_event_schema import SCHEMA as EVENT_SCHEMA
from database.schema.opora_execution_budget_schema import BUDGET_SCHEMA, BUDGET_TABLES
from database.schema.opora_execution_context_schema import SCHEMA as EXECUTION_CONTEXT_SCHEMA
from database.schema.opora_execution_context_schema import TABLES as EXECUTION_CONTEXT_TABLES
from database.schema.opora_execution_observer_schema import (
    REGISTRY_SCHEMA as OBSERVER_REGISTRY_SCHEMA,
)
from database.schema.opora_execution_observer_schema import SCHEMA as OBSERVER_SCHEMA
from database.schema.opora_execution_observer_schema import TABLES as OBSERVER_TABLES
from database.schema.opora_execution_pull_request_schema import SCHEMA as EXECUTION_PR_SCHEMA
from database.schema.opora_execution_pull_request_schema import TABLES as EXECUTION_PR_TABLES
from database.schema.opora_execution_schema import SCHEMA as EXECUTION_SCHEMA
from database.schema.opora_graph_schema import SCHEMA as OPORA_GRAPH_SCHEMA
from database.schema.opora_proposal_review_schema import SCHEMA as PROPOSAL_REVIEW_SCHEMA
from database.schema.opora_proposal_review_schema import TABLES as PROPOSAL_REVIEW_TABLES
from database.schema.opora_reconciliation_jobs import JOB_SCHEMA, JOB_TABLES
from database.schema.opora_reconciliation_schema import RECONCILIATION_SCHEMA, RECONCILIATION_TABLES
from database.schema.opora_review_gate_schema import SCHEMA as REVIEW_GATE_SCHEMA
from database.schema.opora_review_gate_schema import TABLES as REVIEW_GATE_TABLES
from database.schema.opora_review_insight_schema import SCHEMA as REVIEW_INSIGHT_SCHEMA
from database.schema.opora_review_insight_schema import TABLES as REVIEW_INSIGHT_TABLES
from database.schema.opora_review_job_schema import SCHEMA as REVIEW_JOB_SCHEMA
from database.schema.opora_review_job_schema import TABLES as REVIEW_JOB_TABLES
from database.schema.opora_review_policy_schema import SCHEMA as REVIEW_POLICY_SCHEMA
from database.schema.opora_verification_schema import SCHEMA as VERIFICATION_SCHEMA
from database.schema.opora_verification_schema import TABLES as VERIFICATION_TABLES
from database.schema.studio_model_schema import SCHEMA as STUDIO_MODEL_SCHEMA
from database.schema.studio_model_schema import TABLES as STUDIO_MODEL_TABLES
from database.schema.workspace_graph_authority_schema import SCHEMA as GRAPH_AUTHORITY_SCHEMA

# .data/<root>/registry.sqlite – jen to, co musí být vidět napříč projekty.
REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT, repo TEXT, url TEXT, branch TEXT);
CREATE TABLE IF NOT EXISTS project_sources(project_id TEXT PRIMARY KEY, source_kind TEXT NOT NULL, source_path TEXT);
CREATE TABLE IF NOT EXISTS builtin_project_metadata(project_id TEXT PRIMARY KEY, name TEXT NOT NULL);
-- backend/canvas/opora_folder_repository.py: GitHub repozitář a větev, které člověk připojil k projektu z lokální složky
CREATE TABLE IF NOT EXISTS project_repository_bindings(
  project_id TEXT PRIMARY KEY, repository TEXT NOT NULL, branch TEXT NOT NULL, bound_at TEXT NOT NULL, bound_by TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY, project_id TEXT, directory TEXT, branch TEXT, node_id TEXT, actor TEXT, base_sha TEXT);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, kind TEXT, status TEXT, message TEXT, project_id TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS archived_projects(project_id TEXT PRIMARY KEY, snapshot TEXT NOT NULL, archived_at TEXT NOT NULL);
-- backend/project/worktrees/workspace_archive.py: skladiště uzavřených worktree (docs/domeny-a-worktree.md §6, §13.3);
-- větev work/<id> zůstává v repu, řádek z workspaces se sem přesune a jde jen číst
CREATE TABLE IF NOT EXISTS archived_workspaces(
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, node_id TEXT, branch TEXT, actor TEXT, base_sha TEXT,
  directory TEXT, reason TEXT NOT NULL, archived_at TEXT NOT NULL);
-- backend/memory/memory_service.py: nastavení platné pro celou aplikaci (nikdy per projekt).
CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- backend/canvas/activity_log.py: záznam činnosti člověka a agentů (docs/zaznam-cinnosti.md).
CREATE TABLE IF NOT EXISTS activity_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL, agent TEXT NOT NULL,
  method TEXT NOT NULL, path TEXT NOT NULL, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
  node_ids TEXT NOT NULL, status INTEGER NOT NULL, summary TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS activity_log_scope ON activity_log(project_id, workspace_id, actor, id);
""" + CONTEXT_BINDING_SCHEMA + ";" + OBSERVER_REGISTRY_SCHEMA + FLOW_SCHEMA + BRAIN_SCHEMA  # backend/flow/, backend/brain/

# projects/<id>/project.sqlite – vše o jednom projektu; vlastník tabulky v komentáři.
PROJECT_SCHEMA = """
-- backend/canvas/canvas_service.py: graf plátna ne-git projektu
CREATE TABLE IF NOT EXISTS drafts(id TEXT PRIMARY KEY, graph TEXT);
-- backend/canvas/project_architecture.py: architektura projektu (domény, stránky, sektory mezi nimi), jedna nad všemi worktree;
-- removed = ID uzlů a hran, které architektura smazala (skryjí se i ve starých kopiích grafu)
CREATE TABLE IF NOT EXISTS project_architecture(
    project_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, graph TEXT NOT NULL,
    updated_at TEXT NOT NULL, actor TEXT NOT NULL, removed TEXT NOT NULL);
-- backend/canvas/project_architecture.py: historie a návrat architektury; jen přibývají revize
CREATE TABLE IF NOT EXISTS project_architecture_revisions(
    project_id TEXT NOT NULL, revision INTEGER NOT NULL, graph TEXT NOT NULL, actor TEXT NOT NULL,
    workspace TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(project_id, revision));
-- backend/canvas/migrate_architecture.py: stav jednorázové migrace architektury (fáze, záloha, report)
CREATE TABLE IF NOT EXISTS architecture_migrations(
    project_id TEXT PRIMARY KEY, phase TEXT NOT NULL, backup_id TEXT NOT NULL,
    started_at TEXT NOT NULL, finished_at TEXT, report TEXT NOT NULL);
-- backend/project_setup/project_hub.py: cíl a platforma projektu
CREATE TABLE IF NOT EXISTS project_settings(project_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, goal TEXT NOT NULL, platform TEXT NOT NULL);
-- backend/project_setup/project_hub.py: profil projektu (architektura, uživatelé); revizi nese project_settings
CREATE TABLE IF NOT EXISTS project_profile(project_id TEXT PRIMARY KEY, architecture TEXT NOT NULL, tenancy TEXT NOT NULL);
-- backend/editor/node/node_text.py
CREATE TABLE IF NOT EXISTS node_text_revisions(
    project_id TEXT, workspace_id TEXT, node_id TEXT, revision INTEGER,
    text TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id,workspace_id,node_id,revision));
-- backend/editor/brief_vault/brief_vault.py: schránka zadání; doslovné fragmenty, jen přibývají revize
CREATE TABLE IF NOT EXISTS brief_fragment_revisions(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, fragment_id TEXT NOT NULL, revision INTEGER NOT NULL,
    parent_id TEXT, scope_node_id TEXT, ord INTEGER NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
    text TEXT NOT NULL, stage TEXT NOT NULL, mvp TEXT NOT NULL, note TEXT NOT NULL, by TEXT NOT NULL,
    actor TEXT NOT NULL, deleted INTEGER NOT NULL, saved_at TEXT NOT NULL, track TEXT, discipline TEXT, gates TEXT,
    PRIMARY KEY(project_id, workspace_id, fragment_id, revision));
-- Sloupce track (historická stopa, kód ji už nečte ani nepíše), discipline (docs/schranka-neurony.md §2,
-- NULL = dědí) a gates (§3, JSON bran cyklu, NULL = žádná) starší databáze dostanou v ensure_brief_fragment_columns;
-- tam je i backfill track → discipline.
-- backend/editor/brief_vault/brief_vault_gates.py: návrhy payloadu bran (§9 bod 9), jen přibývají; platí pro otisk vstupů
CREATE TABLE IF NOT EXISTS brief_gate_proposals(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL, fragment_id TEXT NOT NULL,
    fragment_revision INTEGER NOT NULL, gate TEXT NOT NULL, input_hash TEXT NOT NULL, payload TEXT NOT NULL,
    note TEXT NOT NULL, by TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY(project_id, workspace_id, id));
CREATE INDEX IF NOT EXISTS brief_gate_proposals_fragment
    ON brief_gate_proposals(project_id, workspace_id, fragment_id, gate, seq);
-- backend/editor/brief_vault/brief_vault_proposals.py: zamítnutí návrhu brány (op reject-proposal), jen přibývají,
-- nejvýš jedno na návrh; zamítnutý návrh se pro potvrzení brány nikdy nepoužije
CREATE TABLE IF NOT EXISTS brief_gate_proposal_rejections(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL, proposal_id TEXT NOT NULL,
    fragment_id TEXT NOT NULL, fragment_revision INTEGER NOT NULL, gate TEXT NOT NULL, note TEXT NOT NULL,
    by TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, id));
CREATE UNIQUE INDEX IF NOT EXISTS brief_gate_proposal_rejections_proposal
    ON brief_gate_proposal_rejections(project_id, workspace_id, proposal_id);
-- backend/editor/brief_vault/brief_vault_lessons.py: poučení z brány learned (§5, §9 bod 12); stav poučení jako revize
-- (verze plátna je nese), lesson_id je otisk původu (fragment, cyklus) = unikátní původ
CREATE TABLE IF NOT EXISTS brief_lessons(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, lesson_id TEXT NOT NULL, revision INTEGER NOT NULL,
    fragment_id TEXT NOT NULL, cycle_revision INTEGER NOT NULL, discipline TEXT NOT NULL, kind TEXT NOT NULL,
    text TEXT NOT NULL, weight REAL NOT NULL, created_at TEXT NOT NULL, confirmed_at TEXT NOT NULL,
    dropped INTEGER NOT NULL, by TEXT NOT NULL, actor TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, lesson_id, revision));
-- backend/editor/brief_vault/brief_vault_lessons.py: potvrzení a vyřazení poučení (append-only události)
CREATE TABLE IF NOT EXISTS brief_lesson_events(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL, lesson_id TEXT NOT NULL,
    kind TEXT NOT NULL, note TEXT NOT NULL, by TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, id));
-- backend/editor/brief_vault/brief_vault_mirror.py: provozní log Zrcadla (docs/zrcadlo.md), append-only, mimo verze plátna;
-- event_id = sha256(projekt, workspace, fragment, cyklus, druh), takže opakované volání se nezapíše dvakrát
CREATE TABLE IF NOT EXISTS brief_mirror_events(
    event_id TEXT NOT NULL PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, fragment_id TEXT NOT NULL,
    revision INTEGER NOT NULL, cycle INTEGER NOT NULL, kind TEXT NOT NULL, request TEXT NOT NULL, result TEXT NOT NULL,
    created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS brief_mirror_events_scope
    ON brief_mirror_events(project_id, workspace_id, kind, created_at);
-- backend/editor/brief_vault/brief_vault_details.py: výzkum, otázka a odkazy na rozhodnutí fragmentu (JSON, jen přibývají revize)
CREATE TABLE IF NOT EXISTS brief_fragment_details(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, fragment_id TEXT NOT NULL, revision INTEGER NOT NULL,
    fields TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, fragment_id, revision));
-- backend/editor/brief_vault/brief_vault_details.py: zpětná vazba člověka k fragmentu (append-only)
CREATE TABLE IF NOT EXISTS brief_fragment_feedback(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL, fragment_id TEXT NOT NULL,
    fragment_revision INTEGER NOT NULL, verdict TEXT NOT NULL, text TEXT NOT NULL, by TEXT NOT NULL,
    actor TEXT NOT NULL, at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, id));
-- backend/editor/node/node_specs.py
CREATE TABLE IF NOT EXISTS node_spec_revisions(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    revision INTEGER NOT NULL, fields TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, node_id, revision));
-- backend/editor/node/node_journal.py
CREATE TABLE IF NOT EXISTS node_journal_revisions(
    project_id TEXT, workspace_id TEXT, node_id TEXT, day TEXT, revision INTEGER,
    text TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id,workspace_id,node_id,day,revision));
-- backend/editor/node/drawings.py
CREATE TABLE IF NOT EXISTS drawing_revisions(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, layer_id TEXT NOT NULL,
    revision INTEGER NOT NULL, scene TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, layer_id, revision));
-- backend/editor/node/drawing_files.py: obrázky kresby (scéna nese jen fileId), sdílené vrstvami projektu
CREATE TABLE IF NOT EXISTS drawing_files(
    project_id TEXT NOT NULL, file_id TEXT NOT NULL, mime_type TEXT NOT NULL,
    data BLOB NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(project_id, file_id));
-- backend/editor/node/removals.py
CREATE TABLE IF NOT EXISTS graph_recoveries(
    id TEXT PRIMARY KEY, project_id TEXT, workspace_id TEXT,
    graph TEXT NOT NULL, created_at TEXT NOT NULL);
-- backend/editor/node/removal_recovery.py: jednorázový záznam obnovy smazaného obsahu (id = graph_recoveries.id)
CREATE TABLE IF NOT EXISTS removal_restores(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    record TEXT NOT NULL, created_at TEXT NOT NULL, used_at TEXT);
-- backend/editor/canvas_versions/canvas_versions.py: uložené verze plátna (graf + stav Desktop v3)
CREATE TABLE IF NOT EXISTS canvas_versions(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    author TEXT NOT NULL, created_at TEXT NOT NULL, graph TEXT NOT NULL, state TEXT NOT NULL,
    graph_digest TEXT NOT NULL, state_digest TEXT NOT NULL,
    snapshot TEXT, content_digest TEXT);
CREATE INDEX IF NOT EXISTS canvas_versions_scope
    ON canvas_versions(project_id, workspace_id, created_at DESC);
-- Index canvas_versions_content (dotaz „je obsah už uložený“) vzniká v ensure_canvas_version_columns:
-- starší tabulka sloupec content_digest v tuto chvíli ještě nemá.
-- backend/editor/agent_memory/desktop_v3_state.py
CREATE TABLE IF NOT EXISTS desktop_v3_state(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, revision INTEGER NOT NULL,
    state TEXT NOT NULL, saved_at TEXT NOT NULL, PRIMARY KEY(project_id, workspace_id));
-- backend/editor/agent_memory/agent_workspace.py
CREATE TABLE IF NOT EXISTS agent_workspace_revisions(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    revision INTEGER NOT NULL, sections TEXT NOT NULL, by TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, node_id, revision));
-- backend/editor/agent_packet/desktop_v3_packets.py
CREATE TABLE IF NOT EXISTS desktop_v3_snapshots(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    node_id TEXT NOT NULL, digest TEXT NOT NULL, request TEXT NOT NULL,
    packet TEXT NOT NULL, created_at TEXT NOT NULL);
-- backend/editor/agent_memory/agent_results.py: immutable original outputs and their specification
CREATE TABLE IF NOT EXISTS assignment_snapshots(
    sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    record TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS card_leases(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    owner TEXT NOT NULL, token TEXT NOT NULL, expires_at REAL NOT NULL,
    PRIMARY KEY(project_id, workspace_id, node_id));
CREATE TABLE IF NOT EXISTS card_work_activity(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    agent TEXT NOT NULL, started_at TEXT, updated_at TEXT NOT NULL, touched TEXT,
    PRIMARY KEY(project_id, workspace_id, node_id));
CREATE TABLE IF NOT EXISTS port_spawns(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    block_id TEXT NOT NULL, port_id TEXT NOT NULL, target_id TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, node_id, block_id, port_id));
-- zrušená kola karty (rozhodnutí vlastníka 23. 10.): nic do ní nepíše, zůstává do migrace DROP
CREATE TABLE IF NOT EXISTS card_rounds(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL, round INTEGER NOT NULL,
    revision INTEGER NOT NULL, record TEXT NOT NULL, saved_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, node_id, round, revision));
CREATE INDEX IF NOT EXISTS assignment_snapshots_scope
    ON assignment_snapshots(project_id, workspace_id, node_id, sequence DESC);
CREATE TABLE IF NOT EXISTS agent_result_records(
    sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, node_id TEXT NOT NULL,
    record TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS agent_results_scope
    ON agent_result_records(project_id, workspace_id, node_id, sequence DESC);
-- backend/project/workspace/workspace_documents.py
CREATE TABLE IF NOT EXISTS workspace_documents(
    project TEXT NOT NULL, workspace TEXT NOT NULL, path TEXT NOT NULL,
    revision INTEGER NOT NULL, fields TEXT NOT NULL, node_id TEXT,
    source_version TEXT, saved_at TEXT NOT NULL,
    PRIMARY KEY(project, workspace, path));
-- backend/editor/agent_handoff/message_store.py: neměnné adresované zprávy a jedno potvrzení adresáta.
CREATE TABLE IF NOT EXISTS agent_messages(
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    source_node_id TEXT NOT NULL, target_node_id TEXT NOT NULL,
    kind TEXT NOT NULL, body TEXT NOT NULL, reply_to_message_id TEXT,
    idempotency_key TEXT NOT NULL, sender_label TEXT NOT NULL, created_at TEXT NOT NULL,
    digest TEXT NOT NULL, content_digest TEXT NOT NULL,
    UNIQUE(project_id, workspace_id, source_node_id, idempotency_key));
CREATE INDEX IF NOT EXISTS agent_messages_scope_incoming
    ON agent_messages(project_id, workspace_id, target_node_id, sequence DESC);
CREATE INDEX IF NOT EXISTS agent_messages_scope_outgoing
    ON agent_messages(project_id, workspace_id, source_node_id, sequence DESC);
CREATE TABLE IF NOT EXISTS agent_message_receipts(
    message_id TEXT PRIMARY KEY, disposition TEXT NOT NULL, note TEXT NOT NULL,
    recipient_label TEXT NOT NULL, created_at TEXT NOT NULL);
-- backend/canvas/check_runs.py: zaznamenaný výsledek kontrol k jednomu commitu; aplikace testy nespouští
CREATE TABLE IF NOT EXISTS check_runs(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, scope_id TEXT NOT NULL,
    sha TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL, recorded_at TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, scope_id, sha, recorded_at));
-- backend/canvas/opora_hub.py: index commitů OporaHubu; pravda leží v souborech oporahub/<id>.json
CREATE TABLE IF NOT EXISTS opora_commits(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, scope_id TEXT NOT NULL,
    id TEXT NOT NULL, parent TEXT, scope_kind TEXT NOT NULL, spec_revision INTEGER NOT NULL,
    subject TEXT NOT NULL, author_kind TEXT NOT NULL, author_name TEXT NOT NULL,
    created_at TEXT NOT NULL, in_main INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(project_id, workspace_id, id));
CREATE INDEX IF NOT EXISTS opora_commits_scope
    ON opora_commits(project_id, workspace_id, scope_id, created_at);
-- Specifications-only changesets: immutable SQLite content and transactional accepted reference.
CREATE TABLE IF NOT EXISTS opora_spec_proposals(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL,
    parent_id TEXT NOT NULL, created_at TEXT NOT NULL, content TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, id));
CREATE TABLE IF NOT EXISTS opora_spec_revisions(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL,
    parent_id TEXT, proposal_id TEXT, created_at TEXT NOT NULL, content TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, id), UNIQUE(project_id, workspace_id, proposal_id));
CREATE TABLE IF NOT EXISTS opora_spec_refs(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, accepted_id TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id));
-- GitHub observations are immutable evidence, never accepted-plan pointers or merge authority.
CREATE TABLE IF NOT EXISTS opora_review_evidence(
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, id TEXT NOT NULL,
    pr_number INTEGER NOT NULL, observed_at TEXT NOT NULL, content TEXT NOT NULL,
    PRIMARY KEY(project_id, workspace_id, id));
CREATE INDEX IF NOT EXISTS opora_review_evidence_history
    ON opora_review_evidence(project_id, workspace_id, pr_number, observed_at);
"""
PROJECT_SCHEMA += (EXECUTION_SCHEMA + GRAPH_AUTHORITY_SCHEMA + OPORA_GRAPH_SCHEMA + REVIEW_POLICY_SCHEMA
                   + RECONCILIATION_SCHEMA + JOB_SCHEMA + BUDGET_SCHEMA + VERIFICATION_SCHEMA + CONTEXT_SCHEMA
                   + EXECUTION_CONTEXT_SCHEMA + CONTENT_SCHEMA + PROPOSAL_REVIEW_SCHEMA + OBSERVER_SCHEMA
                   + EXECUTION_PR_SCHEMA + REVIEW_JOB_SCHEMA + REVIEW_GATE_SCHEMA
                   + REVIEW_INSIGHT_SCHEMA + AUTO_REBASE_SCHEMA + EVENT_SCHEMA
                   + DESIGN_PREVIEW_SCHEMA + HARNESS_LEARNING_SCHEMA + JOURNEY_RUN_SCHEMA
                   + STUDIO_MODEL_SCHEMA + GUARD_FINDINGS_SCHEMA + GUARD_TREND_SCHEMA
                   + GUARD_EXPERIENCE_SCHEMA + INTAKE_SCHEMA)

# Brána mozku (docs/brain-gate.md §5, H1b): relace pracovníků a srdce, lístky s odpověďmi a tickety práce.
# `tickets` + `ticket_feedback` = ticket jako jednotka práce (docs/navrhy/2026-11-03-novy-zaklad.md §3.3); otázkové
# lístky zůstávají v `gate_tickets` (druh otázka), aby migrace byla jen aditivní. Stav ticketu nemá CHECK: přechody
# hlídá `determinism/ticket_model.advance` a nový stav pak nevyžaduje přestavbu tabulky (CHECK `gate_tickets` ji vyžaduje).
GATE_TABLES = ("gate_sessions", "gate_tickets", "tickets", "ticket_feedback")
GATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS gate_sessions(
    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('heart','worker')), worker_name TEXT NOT NULL, worker_meta TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, expires_at TEXT, revoked_at TEXT);
CREATE TABLE IF NOT EXISTS gate_tickets(
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, session_id TEXT NOT NULL,
    kind TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('queued','answered')),
    answer TEXT, answered_by TEXT, created_at TEXT NOT NULL, answered_at TEXT, answered_seq INTEGER);
CREATE INDEX IF NOT EXISTS gate_tickets_session ON gate_tickets(session_id, seq);
CREATE INDEX IF NOT EXISTS gate_tickets_inbox ON gate_tickets(session_id, answered_seq);
CREATE INDEX IF NOT EXISTS gate_tickets_queue ON gate_tickets(project_id, workspace_id, status, seq);
CREATE TABLE IF NOT EXISTS tickets(
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL, workspace_id TEXT NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL,
    card_id TEXT, execution_id TEXT, card_version INTEGER, session_id TEXT, delivery TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, department TEXT, profile TEXT, pins TEXT);
CREATE INDEX IF NOT EXISTS tickets_queue ON tickets(project_id, workspace_id, status, seq);
CREATE INDEX IF NOT EXISTS tickets_holder ON tickets(session_id, status);
CREATE INDEX IF NOT EXISTS tickets_execution ON tickets(execution_id);
CREATE TABLE IF NOT EXISTS ticket_feedback(
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE,
    project_id TEXT NOT NULL, ticket_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('bug','idea','improvement','question')), text TEXT NOT NULL,
    session_id TEXT NOT NULL, answer TEXT, answered_at TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ticket_feedback_ticket ON ticket_feedback(ticket_id, seq);
"""
PROJECT_SCHEMA += GATE_SCHEMA

# Tabulky staré centrální canvas.sqlite, které patří jednomu projektu, a sloupec s jeho ID.
PROJECT_TABLES = {
    "opora_graph_proposals": "project_id",
    "opora_graph_manifests": "project_id",
    "workspace_graph_authority": "project_id",
    "drafts": "id",
    "project_settings": "project_id",
    "project_profile": "project_id",
    "project_architecture": "project_id",
    "project_architecture_revisions": "project_id",
    "node_text_revisions": "project_id",
    "brief_fragment_revisions": "project_id",
    "brief_fragment_details": "project_id",
    "brief_fragment_feedback": "project_id",
    "node_spec_revisions": "project_id",
    "node_journal_revisions": "project_id",
    "drawing_revisions": "project_id",
    "drawing_files": "project_id",
    "graph_recoveries": "project_id",
    "canvas_versions": "project_id",
    "desktop_v3_state": "project_id",
    "desktop_v3_snapshots": "project_id",
    "workspace_documents": "project",
    "check_runs": "project_id",
    "opora_commits": "project_id",
    "opora_spec_proposals": "project_id",
    "opora_spec_revisions": "project_id",
    "opora_spec_refs": "project_id",
    "opora_review_evidence": "project_id",
    "opora_review_policies": "project_id",
    "opora_review_policy_refs": "project_id",
    "opora_review_attempts": "project_id",
    "opora_execution_epochs": "project_id",
    "opora_executions": "project_id",
    "opora_execution_results": "project_id",
    "opora_execution_steps": "project_id",
}
REGISTRY_TABLES = ("projects", "project_sources", "builtin_project_metadata", "workspaces", "jobs", "archived_projects", "opora_context_bindings", "opora_execution_observer_sessions")
PROJECT_TABLES.update({table: "project_id" for table in (*RECONCILIATION_TABLES, *JOB_TABLES)})
PROJECT_TABLES.update({table: "project_id" for table in BUDGET_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in VERIFICATION_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in CONTEXT_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in EXECUTION_CONTEXT_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in CONTENT_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in PROPOSAL_REVIEW_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in OBSERVER_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in EXECUTION_PR_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in AUTO_REBASE_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in REVIEW_JOB_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in REVIEW_GATE_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in REVIEW_INSIGHT_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in DESIGN_PREVIEW_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in HARNESS_LEARNING_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in JOURNEY_RUN_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in STUDIO_MODEL_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in GUARD_FINDINGS_TABLES})
PROJECT_TABLES.update({table: "project_id" for table in (*GUARD_TREND_TABLES, *GUARD_EXPERIENCE_TABLES)})
PROJECT_TABLES.update({table: "project_id" for table in GATE_TABLES})


# CanvasVersions._dirty hledá verzi se stejným obsahem; bez indexu prochází všechny ~5MB řádky (karta P1).
CANVAS_VERSIONS_CONTENT_INDEX = """
CREATE INDEX IF NOT EXISTS canvas_versions_content
    ON canvas_versions(project_id, workspace_id, content_digest);
"""


def _columns(db, table):
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})")}


def add_column(db, table, name):
    """Idempotentní `ADD COLUMN … TEXT`: když sloupec mezitím přidal souběžný proces („duplicate column“),
    ověří ho PRAGMA a chybu spolkne; jakákoli jiná chyba projde dál."""
    try:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {name} TEXT")
    except sqlite3.OperationalError:
        if name not in _columns(db, table):
            raise


def ensure_canvas_version_columns(db):
    """Add full snapshot columns; existing graph/state versions remain explicitly partial."""
    columns = _columns(db, "canvas_versions")
    for name in ("snapshot", "content_digest"):
        if name not in columns:
            add_column(db, "canvas_versions", name)
    if {"project_id", "workspace_id"} <= columns:
        db.execute(CANVAS_VERSIONS_CONTENT_INDEX)


def ensure_ticket_columns(db):
    """Oddělení a profil kanceláře a piny Brainu ve strojové vrstvě ticketu (docs/navrhy/2026-11-03-novy-zaklad.md
    §3.3, §3.4)."""
    columns = _columns(db, "tickets")
    for name in ("department", "profile", "pins"):
        if columns and name not in columns:
            add_column(db, "tickets", name)


def ensure_brief_fragment_columns(db):
    """Doplní historickou stopu, disciplínu a brány fragmentu (docs/schranka-neurony.md §2 „Migrace“, §3, §9 bod 5).

    Backfill je doplnění schématu, ne nová revize: jen řádky s `track IS NOT NULL AND discipline IS NULL`
    (`ux` → `ux`, `logic` → `be`). Nový kód `track` nepíše, takže záměrné NULL z `set-discipline` se
    opakovaným otevřením nepřepíše. Řádky bez stopy zůstanou NULL = dědí / nezařazené."""
    columns = _columns(db, "brief_fragment_revisions")
    if not columns:
        return
    for name in ("track", "discipline", "gates"):
        if name not in columns:
            add_column(db, "brief_fragment_revisions", name)
    db.execute("UPDATE brief_fragment_revisions SET discipline=CASE track WHEN 'ux' THEN 'ux' WHEN 'logic' THEN 'be' END"
               " WHERE track IN ('ux','logic') AND discipline IS NULL")


MILESTONE_COLUMNS = "id, workspace_id, area_id, title, criteria, status, created_at"


def ensure_milestone_proposed(db):
    """Jednorázová přestavba `intake_milestones` na CHECK se stavem `proposed`
    (docs/navrhy/2026-10-30-metriky-a-spoustece.md §5): SQLite CHECK nezmění, proto rename → create → copy → drop
    → index `intake_milestones_one_active`, celé pod savepointem (chyba vrátí původní tabulku i řádky).
    Idempotentní: tabulka, jejíž CHECK už `proposed` zná, nebo chybějící tabulka = nic."""
    row = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='intake_milestones'").fetchone()
    if row is None or "'proposed'" in row[0]:
        return
    db.execute("SAVEPOINT intake_milestones_rebuild")
    try:
        db.execute("ALTER TABLE intake_milestones RENAME TO intake_milestones_old")
        db.execute(MILESTONES_TABLE)
        db.execute(f"INSERT INTO intake_milestones({MILESTONE_COLUMNS})"
                   f" SELECT {MILESTONE_COLUMNS} FROM intake_milestones_old")
        db.execute("DROP TABLE intake_milestones_old")  # smaže i starý index, nový vznikne nad novou tabulkou
        db.execute(MILESTONES_INDEX)
    except BaseException:
        db.execute("ROLLBACK TO intake_milestones_rebuild")
        db.execute("RELEASE intake_milestones_rebuild")
        raise
    db.execute("RELEASE intake_milestones_rebuild")
