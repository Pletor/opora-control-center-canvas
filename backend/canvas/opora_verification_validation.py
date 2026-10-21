"""Strict, bounded imported formal evidence; hashes bind exact uploaded bytes."""
import base64
import binascii
import hashlib
import json
import math
import re

FILE_LIMIT = 2 * 1024 * 1024
RUN_LIMIT = 8 * 1024 * 1024
PROJECT_LIMIT = 64 * 1024 * 1024
SHA = re.compile(r"[a-f0-9]{64}")
IDENTITY = re.compile(r"[A-Za-z0-9_-]{1,80}")


def exact(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise ValueError("Invalid verification fields.")


def text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000 or "\0" in value:
        raise ValueError("Verification text must contain 1 to 4000 characters.")
    return value


def identity(value):
    if not isinstance(value, str) or not IDENTITY.fullmatch(value):
        raise ValueError("Invalid verification identity.")
    return value


def sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError("Invalid verification SHA256.")
    return value


def canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise ValueError("Verification must be finite JSON.") from exc


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def configuration(value, depth=0):
    if depth > 8:
        raise ValueError("Verification configuration exceeds depth 8.")
    if isinstance(value, dict):
        for key, item in value.items():
            text(key)
            configuration(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            configuration(item, depth + 1)
    elif isinstance(value, str):
        text(value)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Verification configuration must be finite.")
    elif value is not None and type(value) not in (bool, int, float):
        raise ValueError("Invalid verification configuration.")
    if depth == 0 and len(canonical(value)) > 16 * 1024:
        raise ValueError("Verification configuration exceeds 16 KiB.")


def artifacts(values, roles):
    if not isinstance(values, list) or len(values) > 32:
        raise ValueError("Verification allows at most 32 artifacts.")
    manifest, blobs, paths, total = [], {}, set(), 0
    for item in values:
        exact(item, "path role sha256 dataBase64")
        path = text(item["path"])
        if (len(path) > 240 or path in paths or "\\" in path or ":" in path or any(ord(c) < 32 for c in path)
                or any(part in ("", ".", "..") for part in path.split("/"))):
            raise ValueError("Invalid or duplicate artifact path.")
        paths.add(path)
        if item["role"] not in roles:
            raise ValueError("Invalid verification artifact role.")
        fingerprint = sha(item["sha256"])
        encoded = item["dataBase64"]
        if not isinstance(encoded, str) or len(encoded) > 4 * ((FILE_LIMIT + 2) // 3):
            raise ValueError("Artifact exceeds 2 MiB.")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Invalid artifact base64.") from exc
        if len(data) > FILE_LIMIT or hashlib.sha256(data).hexdigest() != fingerprint:
            raise ValueError("Artifact bytes or SHA256 do not match.")
        total += len(data)
        if total > RUN_LIMIT:
            raise ValueError("Verification artifacts exceed 8 MiB.")
        blobs[fingerprint] = data
        manifest.append({"path": path, "role": item["role"], "sha256": fingerprint, "bytes": len(data)})
    return sorted(manifest, key=lambda item: item["path"]), blobs


def verification(value):
    exact(value, "tool source claims assumptions configuration artifacts")
    tool, source = value["tool"], value["source"]
    exact(tool, "name version distributionSha256")
    if tool["name"] not in ("tlc", "lean"):
        raise ValueError("Verification tool must be tlc or lean.")
    text(tool["version"])
    sha(tool["distributionSha256"])
    exact(source, "repository commitSha")
    if (not isinstance(source["repository"], str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}", source["repository"])
            or any(part in (".", "..") for part in source["repository"].split("/"))
            or not isinstance(source["commitSha"], str) or not re.fullmatch(r"[a-f0-9]{40}", source["commitSha"])):
        raise ValueError("Invalid reported repository or commit SHA.")
    claims = value["claims"]
    if not isinstance(claims, list) or not 1 <= len(claims) <= 32:
        raise ValueError("Verification requires 1 to 32 claims.")
    checked, ids = [], set()
    for claim in claims:
        exact(claim, "id kind statement")
        identifier = identity(claim["id"])
        kinds = ("theorem",) if tool["name"] == "lean" else ("invariant", "temporal-property")
        if identifier in ids or claim["kind"] not in kinds:
            raise ValueError("Invalid or duplicate verification claim.")
        ids.add(identifier)
        statement = text(claim["statement"])
        checked.append({**claim, "statementDigest": hashlib.sha256(statement.encode("utf-8")).hexdigest()})
    assumptions = value["assumptions"]
    if not isinstance(assumptions, list) or len(assumptions) > 32:
        raise ValueError("Verification allows at most 32 assumptions.")
    for assumption in assumptions:
        text(assumption)
    if not isinstance(value["configuration"], dict):
        raise ValueError("Verification configuration must be an object.")  # noqa: TRY004 - domain/API conflicts are ValueError
    configuration(value["configuration"])
    manifest, blobs = artifacts(value["artifacts"], ("model", "configuration", "dependency", "proof", "source", "lockfile"))
    roles = {item["role"] for item in manifest}
    if (not manifest or (tool["name"] == "tlc" and not {"model", "configuration"} <= roles)
            or (tool["name"] == "lean" and not roles.intersection(("proof", "source")))):
        raise ValueError("Verification is missing required tool input artifacts.")
    return {**value, "claims": checked, "artifacts": manifest}, blobs


def report(value, claims):
    exact(value, "outcome checkedClaims summary artifacts")
    if value["outcome"] not in ("passed", "counterexample", "failed", "inconclusive", "cancelled"):
        raise ValueError("Invalid verification outcome.")
    text(value["summary"])
    checked = value["checkedClaims"]
    allowed = {item["id"] for item in claims}
    if not isinstance(checked, list) or len(checked) > 32:
        raise ValueError("Invalid checked claims.")
    for item in checked:
        identity(item)
    if len(set(checked)) != len(checked) or not set(checked) <= allowed:
        raise ValueError("Invalid checked claims.")
    if value["outcome"] == "passed" and set(checked) != allowed:
        raise ValueError("Passed report must check every claim.")
    manifest, blobs = artifacts(value["artifacts"], ("stdout", "stderr", "counterexample", "proof", "run-metadata"))
    if value["outcome"] == "passed" and not manifest:
        raise ValueError("Passed report requires output evidence.")
    if value["outcome"] == "counterexample" and not any(item["role"] == "counterexample" for item in manifest):
        raise ValueError("Counterexample report requires a counterexample artifact.")
    return {**value, "artifacts": manifest}, blobs
