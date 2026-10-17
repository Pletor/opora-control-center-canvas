"""Vložení Opory do <iframe> cizí lokální aplikace (opora.toml `[app] embed_origins`).

Výchozí stav je prázdný seznam: `X-Frame-Options: DENY` a `frame-ancestors 'none'`, tedy dnešní
ochrana proti clickjackingu. Neprázdný seznam povolí rámování jen přesně vyjmenovaným původům;
všechny ostatní hranice (Host, Origin pro zápisy, cookie člověka, lease) zůstávají beze změny.
"""

from urllib.parse import urlsplit

ENV_NAME = "OPORA_CANVAS_EMBED_ORIGINS"


def _invalid(entry, why: str) -> ValueError:
    return ValueError(
        f"Neplatný původ v [app] embed_origins: {entry!r} – {why}. "
        "Očekává se přesný původ jako \"http://localhost:4600\" (schéma http/https, host, "
        "volitelně port; bez cesty, hvězdičky a 'null')."
    )


def validate_origin(entry) -> str:
    """Vrátí původ v kanonickém tvaru, nebo vyhodí ValueError s českou hláškou."""
    if not isinstance(entry, str) or not entry.strip():
        raise _invalid(entry, "není neprázdný text")
    text = entry.strip()
    if "*" in text:
        raise _invalid(entry, "hvězdička není dovolená")
    if text.lower() == "null":
        raise _invalid(entry, "'null' není dovolený")
    if any(ch.isspace() for ch in text) or any(ch in text for ch in ";,'\""):
        raise _invalid(entry, "obsahuje mezeru nebo oddělovač")
    parts = urlsplit(text)
    if parts.scheme not in ("http", "https"):
        raise _invalid(entry, "schéma musí být http nebo https")
    if parts.username is not None or parts.password is not None:
        raise _invalid(entry, "přihlašovací údaje v adrese nejsou dovolené")
    if not parts.hostname:
        raise _invalid(entry, "chybí host")
    if parts.path not in ("", "/") or parts.query or parts.fragment or text.endswith("?") or "#" in text:
        raise _invalid(entry, "původ nesmí mít cestu, dotaz ani fragment")
    try:
        port = parts.port
    except ValueError:
        raise _invalid(entry, "port není číslo 1–65535") from None
    if port is not None and not 1 <= port <= 65535:
        raise _invalid(entry, "port není číslo 1–65535")
    return f"{parts.scheme}://{parts.netloc.lower()}"


def parse_embed_origins(value) -> tuple[str, ...]:
    """Seznam z TOML nebo text z proměnné prostředí (oddělený mezerami) → ověřené původy."""
    if value is None:
        return ()
    if isinstance(value, str):
        items = value.split()
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        # ValueError, protože ho tools/opora.py hlásí jako chybu konfigurace.
        raise ValueError(  # noqa: TRY004
            "[app] embed_origins musí být seznam původů, např. [\"http://localhost:4600\"].")
    origins: list[str] = []
    for item in items:
        origin = validate_origin(item)
        if origin not in origins:
            origins.append(origin)
    return tuple(origins)


def frame_policy(origins: tuple[str, ...]) -> tuple[str | None, str]:
    """(hodnota X-Frame-Options nebo None, direktiva frame-ancestors) pro baseline CSP."""
    if not origins:
        return "DENY", "frame-ancestors 'none'"
    return None, "frame-ancestors 'self' " + " ".join(origins)
