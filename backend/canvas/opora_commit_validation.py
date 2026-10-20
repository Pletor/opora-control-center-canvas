"""Validation shared by legacy commits and guarded proposal snapshots."""
import json
import re

from backend.canvas.graph import digest as graph_digest

AUTHORS = ("human", "orchestrator", "agent")
WRITERS = ("human", "orchestrator")
SCOPE_KINDS = ("area", "sector", "node")
SUBJECT_LIMIT = 200


def _author(by, *, allow_agent=False):
    """Kdo smí psát historii. Zámek proti omylu agenta, ne proti člověku."""
    if not isinstance(by, dict):
        raise ValueError("Autor commitu musí být objekt s druhem a jménem.")  # noqa: TRY004
    kind, name = by.get("kind"), by.get("name")
    if kind == "agent" and not allow_agent:
        raise ValueError(
            "Agent do OporaHubu nezapisuje; commit a merge dělá orchestrátor nebo člověk.")
    if kind not in (AUTHORS if allow_agent else WRITERS):
        raise ValueError("Druh autora je jen člověk (human), nebo orchestrátor (orchestrator).")
    if not isinstance(name, str) or not name.strip() or len(name) > 120 or "\0" in name:
        raise ValueError("Jméno autora musí mít 1 až 120 znaků.")
    return {"kind": kind, "name": name.strip()}


def _content(payload, *, allow_agent=False):
    """Ověřený obsah commitu bez rodiče a času; co projde, to se otiskne a uloží."""
    if not isinstance(payload, dict):
        raise ValueError("Obsah commitu musí být objekt.")  # noqa: TRY004
    kind, revision = payload.get("kind"), payload.get("specRevision")
    digest, subject, pair = payload.get("graphDigest"), payload.get("subject"), payload.get("pair")
    if kind not in SCOPE_KINDS:
        raise ValueError("Commit patří oblasti (area), sektoru (sector), nebo uzlu (node).")
    if type(revision) is not int or revision < 0:
        raise ValueError("Revize zadání musí být nezáporné celé číslo.")
    if not isinstance(digest, str) or not 8 <= len(digest) <= 128:
        raise ValueError("Digest grafu musí mít 8 až 128 znaků.")
    if not isinstance(subject, str) or not subject.strip() or "\0" in subject:
        raise ValueError("Předmět commitu je text 1 až 200 znaků bez nulového bajtu.")
    if len(subject) > SUBJECT_LIMIT:
        raise ValueError("Předmět commitu smí mít nejvýše 200 znaků.")
    if pair is not None and not isinstance(pair, dict):
        raise ValueError("Pár commitu je objekt s vazbou na git, nebo nic.")
    fields = {"kind": kind, "specRevision": revision, "graphDigest": digest,
              "subject": subject.strip(), "by": _author(payload.get("by"), allow_agent=allow_agent), "pair": pair}
    if "specificationSnapshot" in payload:
        snapshot = payload["specificationSnapshot"]
        if (not isinstance(snapshot, dict) or set(snapshot) != {"contextVersion", "specification"}
                or not isinstance(snapshot["contextVersion"], str)
                or not re.fullmatch(r"[a-f0-9]{64}", snapshot["contextVersion"])
                or not isinstance(snapshot["specification"], dict)
                or snapshot["specification"].get("schema") != "opora.specification-context/1"
                or graph_digest(snapshot["specification"]) != snapshot["contextVersion"]):
            raise ValueError("Snímek zadání neodpovídá své verzi kontextu.")
        # Detached JSON content: subsequent edits to a caller's dict cannot alter the commit.
        fields["specificationSnapshot"] = json.loads(json.dumps(snapshot, ensure_ascii=False))
    return fields
