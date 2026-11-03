"""Piny Brainu v ticketu (docs/navrhy/2026-11-03-novy-zaklad.md §3.4): co dělník dostane jako `--plugin-dir`.

Srdce v `ticket.issue` jmenuje artefakty (`opora:brain:skill:<name>` = aktivní verze, `…@<sha12>` = ta verze).
Server je přeloží a seskupí po pluginech: jeden plugin = jeden zip (`Store.export`), i když z něj ticket chce víc
skillů. Výchozí pin pluginu `ponytail` (aktivní verze `opora:brain:skill:ponytail`) přibude, když ho srdce samo
nepinulo a v registru je. Nic tu nevolá model ani git; zip vzniká až při stažení.
"""

from backend.brain import registry

DEFAULT = "opora:brain:skill:ponytail"
ZIP = "/api/brain-registry/pins/{plugin}@{short}.zip"


def entry(found):
    return {"pin": found["pin"], "plugin": found["plugin"], "version": found["version"],
            "zip": ZIP.format(plugin=found["plugin"], short=found["version"][:12])}


def for_ticket(db, requested):
    """`[{pin, plugin, version, zip}]` po pluginech (výchozí ponytail první). Neznámé ID je `LookupError`,
    dvě verze téhož pluginu `ValueError`."""
    plugins = {}
    for ref in requested:
        found = registry.resolve(db, ref)
        if found is None:
            raise LookupError(f"Artefakt Brainu {ref} v registru není.")
        known = plugins.setdefault(found["plugin"], entry(found))
        if known["version"] != found["version"]:
            raise ValueError(f"Plugin {found['plugin']} je v pinech ve dvou verzích.")
    default = registry.active(db, DEFAULT)
    if default and default["plugin"] not in plugins:
        plugins = {default["plugin"]: entry(default), **plugins}
    return list(plugins.values())
