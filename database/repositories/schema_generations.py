"""Řetězec generací schématu: proč pin SQL kontextu přežije vlastní DDL aplikace, ale ne cizí.

Pokrytí kontextu (`opora_context_coverage` v project.sqlite) i vazba registru
(`opora_context_bindings` v registry.sqlite) si při zápisu připnou `PRAGMA schema_version`.
SQLite tu verzi posune každým DDL, i nevinným novým indexem, a pin by pak padl, přestože
otisky schématu, triggerů i událostí sedí. Proto aplikace každé své DDL dosvědčí:
`witness` přečte verzi před a po a zapíše řádek `from → to` s autorem `app-migration`
a důvodem, který jmenuje konkrétní krok. Pin projde, když od jeho verze vede souvislý
řetězec zapsaných generací až k aktuální verzi. Cizí DDL (mimo svědka) nechá mezeru
a pin dál odmítne. Mezeru lze uznat jen vědomě přes `adopt` / `tools/schema_adopt.py`,
s pravdivým autorem a důvodem. Tabulka je append-only (triggery), nic se nepřepisuje
ani nemaže, a nevstupuje do otisků (`opora_context_%`, `opora_binding_%`).

Svědek není atomický s `executescript` (ten commituje): pád nebo výjimka mezi
potvrzeným DDL a zápisem nechá nezapsanou mezeru; to selže bezpečně (pin odmítne).
Kontrakt: docs/oporahub-sparse-context.md a docs/oporahub-content-changes.md
(„Upgrade projektu s dřívějším kontextem v2“).
"""
TABLE = "opora_schema_generations"
_GUARD = "SELECT RAISE(ABORT,'Permanent schema generation');"
STATEMENTS = (
    f"""CREATE TABLE IF NOT EXISTS {TABLE}(
 from_version INTEGER PRIMARY KEY, to_version INTEGER NOT NULL,
 author TEXT NOT NULL, reason TEXT NOT NULL, at TEXT NOT NULL,
 CHECK(to_version > from_version))""",
    f"CREATE TRIGGER IF NOT EXISTS {TABLE}_update BEFORE UPDATE ON {TABLE} BEGIN {_GUARD} END",
    f"CREATE TRIGGER IF NOT EXISTS {TABLE}_delete BEFORE DELETE ON {TABLE} BEGIN {_GUARD} END",
    # INSERT OR REPLACE would delete silently when recursive triggers are off.
    (f"CREATE TRIGGER IF NOT EXISTS {TABLE}_replace BEFORE INSERT ON {TABLE} "
     f"WHEN EXISTS(SELECT 1 FROM {TABLE} WHERE from_version=NEW.from_version) BEGIN {_GUARD} END"),
)
MAX_STEPS = 10000


def _version(db):
    return db.execute("PRAGMA schema_version").fetchone()[0]


def exists(db):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone() is not None


def rows(db):
    if not exists(db):
        return []
    return [tuple(row) for row in db.execute(f"SELECT from_version,to_version,author,reason,at FROM {TABLE} ORDER BY from_version")]


def _insert(db, start, end, author, reason):
    db.execute(f"INSERT INTO {TABLE}(from_version,to_version,author,reason,at) VALUES(?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
               (start, end, author, reason))


def witness(db, reason, ddl):
    """Run application DDL and record the generation it caused; never commits a caller transaction."""
    owns = not db.in_transaction
    start = _version(db)  # read before the table exists so the first install records itself
    for statement in STATEMENTS:
        db.execute(statement)
    result = ddl()
    end = _version(db)
    # A taken from_version (restored or copied DB) is skipped: the pin then refuses, which is safe.
    if end > start and not db.execute(f"SELECT 1 FROM {TABLE} WHERE from_version=?", (start,)).fetchone():
        _insert(db, start, end, "app-migration", reason)
    if owns and db.in_transaction:
        db.commit()
    return result


def adopt(db, start, end, author, reason):
    """Explicitly record a gap the application did not witness; nothing is rewritten."""
    if not isinstance(author, str) or not author.strip() or not isinstance(reason, str) or not reason.strip():
        raise ValueError("Schema generation adoption requires author and reason.")
    if type(start) is not int or type(end) is not int or end <= start:
        raise ValueError("Schema generation must move forward.")
    witness(db, "schema_generations.adopt: založení tabulky generací před adopcí", lambda: None)
    if db.execute(f"SELECT 1 FROM {TABLE} WHERE from_version=?", (start,)).fetchone():
        raise ValueError("Schema generation is already recorded.")
    _insert(db, start, end, author.strip(), reason.strip())


def walk(db, pin):
    """Versions reachable from pin along recorded generations, stopping at the current version or a gap."""
    current, path = _version(db), [pin]
    if pin == current or not exists(db):
        return path
    while path[-1] != current and len(path) <= MAX_STEPS:
        row = db.execute(f"SELECT to_version FROM {TABLE} WHERE from_version=?", (path[-1],)).fetchone()
        if row is None:
            break
        path.append(row[0])
    return path


def chain(db, pin):
    """Recorded versions from pin to the current schema_version, or None on a gap or cycle."""
    path = walk(db, pin)
    return path if path[-1] == _version(db) else None


def gap(db, pin):
    """Nedosvědčená mezera `(od, do)`: od konce řetězce pinu po začátek dalšího zapsaného článku, jinak po teď."""
    current, end = _version(db), walk(db, pin)[-1]
    if end == current:
        return None
    later = db.execute(f"SELECT min(from_version) FROM {TABLE} WHERE from_version>? AND from_version<=?",
                       (end, current)).fetchone()[0] if exists(db) else None
    return end, later or current


def reaches(db, pin):
    return chain(db, pin) is not None


def explain(db, pin):
    """Readable reason why pin does not reach the current version, with the exact adoption command."""
    current = _version(db)
    end, until = gap(db, pin) or (current, current)
    path = db.execute("PRAGMA database_list").fetchone()[2] or "<cesta k sqlite>"
    return (f" Pin je na verzi schématu {pin}, databáze je teď na {current}, zapsaný řetězec generací"
            f" končí na {end} a chybí článek {end} -> ?: schéma změnilo DDL mimo aplikaci, nebo aplikace"
            f" svůj krok nedosvědčila. Změnu schématu mimo aplikaci uznej jen vědomě:"
            f' python tools/schema_adopt.py --db "{path}" --from {end} --to {until}'
            f' --author "<kdo>" --reason "<proč>" (bez --write jen ukáže stav).')


_BROKEN = set()  # (projekt, předmět) s nepropustným pinem v deníku chyb; uzavírá se jen tehdy, levně


def pin_broken(db, pin, project, subject):
    """`explain` a k tomu záznam `integrity` do deníku chyb (frontou: checkpoint běží pod zámky); páka = příkaz."""
    from backend.app import error_log

    text = explain(db, pin)
    if (project, subject) in _BROKEN:
        return text  # checkpoint se volá při čtení: jeden záznam na rozbití, ne na každé čtení
    command = text[text.index("python tools/schema_adopt.py"):] if "schema_adopt" in text else None
    error_log.submit("integrity", "integrity", f"Pin SQL kontextu ({subject}) neprošel: schéma se změnilo mimo "
                     "zapsaný řetězec generací.", project=project, subject=subject, cause=text.strip(),
                     lever=command, data={"pin": pin, "current": _version(db)})
    _BROKEN.add((project, subject))
    return text


def pin_ok(project, subject):
    """Checkpoint prošel: dřív zapsaný záznam pinu se uzavře (bez dotazu, když žádný nebyl)."""
    if (project, subject) in _BROKEN:
        from backend.app import error_log

        _BROKEN.discard((project, subject))
        error_log.resolve(source="integrity", project=project, subject=subject)
