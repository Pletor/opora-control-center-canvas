"""Podmíněné GET (karta P3): ETag z revize nebo digestu a projektu, `If-None-Match` → 304 bez těla.

ETag je otisk (sha256) identity obsahu, ne obsah: z hlavičky se nedá nic vyčíst a různé projekty
ani prostory nikdy nesdílí stejný ETag (projekt a prostor jsou v otisku). Tělo se staví až po
neshodě, takže 304 ušetří serializaci i přenos. `Cache-Control: no-store` z middleware platí dál:
prohlížeč si odpověď neukládá, klient (`frontend/shared/types/logic/types.ts` `api`) drží poslední
tělo sám a podmíněný dotaz posílá výslovně.
"""
import hashlib
import json

from fastapi.responses import JSONResponse, Response


def etag_of(*parts):
    """Silný ETag z JSON částí identity (revize, digest, projekt, prostor, parametry dotazu)."""
    raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=list)
    return '"' + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40] + '"'


def matches(header, tag):
    """Shoduje se `If-None-Match` s ETagem? Bere seznam, slabé `W/` i `*` (RFC 9110 §13.1.2)."""
    if not header:
        return False
    for candidate in header.split(","):
        value = candidate.strip()
        if value == "*" or value.removeprefix("W/") == tag:
            return True
    return False


def conditional(request, tag, body):
    """304 při shodě `If-None-Match`, jinak 200 s tělem z `body()` a hlavičkou ETag."""
    if matches(request.headers.get("if-none-match"), tag):
        return Response(status_code=304, headers={"ETag": tag})
    return JSONResponse(body(), headers={"ETag": tag})
