"""Je to srdce? (docs/brain-heart.md §5): odpověď na lístek a zápis plánu smí člověk, nebo srdce téhož projektu.

Srdce pozná jen middleware `boundary`: po ověření tokenu srdce zdí nastaví `request.state.heart_project`.
Hlavička ani tělo požadavku ho podvrhnout nemůže; bez ověřeného tokenu je hodnota prázdná.
"""


def heart_project(request):
    """Projekt, pro který zeď ověřila token srdce; jinak prázdný text."""
    value = getattr(request.state, "heart_project", "")
    return value if isinstance(value, str) else ""
