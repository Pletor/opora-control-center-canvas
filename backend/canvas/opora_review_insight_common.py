"""Shared helpers of the review insight modules: project validation, locked transactions, errors."""
import re
from contextlib import contextmanager

from backend.canvas.graph import valid_id
from database.repositories.opora_review_insights import ReviewInsights

REPOSITORY = re.compile(r"[a-z0-9-]+/[a-z0-9_.-]+")


class InsightHumanRequired(PermissionError):
    """Only an identified human session may do this (HTTP 403 `human_required`)."""


class InsightMissing(LookupError):
    """Unknown identity or reviewed PR (HTTP 404)."""


def project_id(value):
    if not isinstance(value, str) or not valid_id(value) or len(value) > 64:
        raise ValueError("Neplatný projekt.")
    return value


def workspace_id(value, nullable=False):
    if nullable and value is None:
        return None
    return project_id(value)


def text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} musí být neprázdný text do {limit} znaků.")
    return value.strip()


def repository(value):
    value = value.casefold() if isinstance(value, str) else None
    if value is None or REPOSITORY.fullmatch(value) is None or ".." in value:
        raise ValueError("Neplatný repozitář.")
    return value


def number(value):
    if type(value) is not int or value < 1:
        raise ValueError("Neplatné číslo PR.")
    return value


def fields(payload, required, optional=()):
    if not isinstance(payload, dict) or not set(required) <= set(payload) <= {*required, *optional}:
        raise ValueError("Neplatná pole požadavku.")
    return payload


@contextmanager
def reading(canvas, project):
    with canvas.graph_lock_for(project), canvas.lock_for(project):
        db = canvas.db_for(project)
        yield db, ReviewInsights(db, project)


@contextmanager
def writing(canvas, project):
    """Graph → project lock order and BEGIN IMMEDIATE like the review job authority."""
    with canvas.graph_lock_for(project), canvas.lock_for(project):
        db = canvas.db_for(project)
        with db:
            db.execute("BEGIN IMMEDIATE")
            yield db, ReviewInsights(db, project)
