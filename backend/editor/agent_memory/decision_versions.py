"""Linked corrections preserve the superseded decision and its owning card."""


def validate_versions(decisions):
    by_id = {item["id"]: item for item in decisions}
    replaced = set()
    for item in decisions:
        if "supersedes" not in item:
            continue
        previous_id = item["supersedes"]
        if not isinstance(previous_id, str) or previous_id not in by_id or previous_id == item["id"]:
            raise ValueError("Oprava musí odkazovat na existující původní rozhodnutí.")
        previous = by_id[previous_id]
        if previous["nodeId"] != item["nodeId"] or previous["path"] != item["path"]:
            raise ValueError("Oprava musí zůstat u stejné karty a cesty.")
        if previous_id in replaced:
            raise ValueError("Rozhodnutí již má opravu; opravte jeho poslední verzi.")
        replaced.add(previous_id)
        seen = {item["id"]}
        cursor = previous
        while True:
            if cursor["id"] in seen:
                raise ValueError("Řetězec oprav rozhodnutí nesmí obsahovat cyklus.")
            seen.add(cursor["id"])
            parent = cursor.get("supersedes")
            if parent is None:
                break
            if not isinstance(parent, str) or parent not in by_id:
                raise ValueError("Původní rozhodnutí opravy neexistuje.")
            cursor = by_id[parent]


def preserve_versions(previous, current):
    current_ids = {item["id"] for item in current}
    for item in previous:
        if "supersedes" in item and ((item["id"] in current_ids) != (item["supersedes"] in current_ids)):
            raise ValueError("Historii oprav nelze odstranit částečně.")
    protected = {item["supersedes"] for item in current if "supersedes" in item}
    protected.update(item["id"] for item in current if "supersedes" in item)
    protected.update(item["id"] for item in previous if "supersedes" in item)
    protected.update(item["supersedes"] for item in previous if "supersedes" in item)
    before = {item["id"]: item for item in previous}
    for item in current:
        old = before.get(item["id"])
        if (old and item["id"] in protected
                and {k: v for k, v in old.items() if k != "pinned"} != {k: v for k, v in item.items() if k != "pinned"}):
            raise ValueError("Verzované rozhodnutí nelze přepsat; vytvořte další opravu.")
