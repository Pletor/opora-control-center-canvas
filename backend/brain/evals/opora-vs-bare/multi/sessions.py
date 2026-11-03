"""Zadání sezení S1–S6 (SCENAR.md §2), recept ramene C a deterministický zásah „kolegy“ mezi S2 a S3.

- `SESSIONS` / `prompt(session, part)` – texty zadání; S1 nese celý plán, další ho neopakují.
- `c_recipe()` – recept ověření, který rameno A dostává ve skillu (`SKILL.md`, sekce „Recept: stavba stránky“),
  vytažený ze skillu a přepsaný bez OPORY (karty, `site.feel`, `spec.steps` pryč). Rameno C ho dostane jako
  doplněk system promptu, stejným kanálem jako A skill.
- `inject_colleague(ws, verify=None)` – commit jiného autora se dvěma regresemi (bez `aria-invalid` na polích
  formuláře, odkaz „Ceník“ v menu na `/cennik`). Hledá je regexem nad `src/` (mimo testy), funguje nad libovolnou
  implementací; co nejde zavést, vrátí `injection: partial` s důvodem. Idempotentní (podruhé nic necommitne).
Stdlib + git.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

MULTI = Path(__file__).resolve().parent
FLOW = MULTI.parent
REPO = FLOW.parents[3]
SKILL_MD = REPO / "backend" / "brain" / "seed" / "opora-control-center" / "skills" / "opora-control-center" / "SKILL.md"

ORDER = ["S1", "S2", "S3", "S4", "S5", "S6"]
MEMORY_FIRST = ("Na aplikaci se bude pracovat v dalších sezeních, která si z tohoto nic nepamatují. "
                "Co má další sezení vědět, si ulož, kam uznáš za vhodné.")
MEMORY_NEXT = ("Navazuješ na předchozí sezení této aplikace; z nich si nic nepamatuješ, jejich práce a cokoli si uložila "
               "je k dispozici.")
FOOTER = "Projekt musí po práci projít `npm run build` a `npm test`. Pracuj jen v tomto repozitáři, nic nenasazuj."

S1 = """Postav webovou aplikaci kurzu „Zelený balkon“ (React + Vite v tomto repozitáři).

Cílovka: začátečníci, kterým hynou rostliny. Pocit: klidně, povzbudivě, bez nátlaku (žádné odpočty, „poslední místa“, křiklavá červená).

Pravidla celé aplikace (platí navždy):
- každý formulář má popisky, chybu u pole s `aria-invalid`, drží hodnoty po chybě a během odesílání má neaktivní tlačítko s textem „Odesílám…“;
- jeden `h1` na stránku;
- každá stránka má sekce `data-opora-section`.

Plán šesti stránek (roadmapa): `/` Domů, `/kurz`, `/kontakt` + `/dekujeme`, `/cenik`, `/pribehy` (3 příběhy absolventů), `/faq` (6 otázek).

Úkol tohoto sezení: postav `/`, `/kurz`, `/kontakt`, `/dekujeme` a menu. Ostatní stránky jsou plán na později.
- Formulář na `/kontakt`: jméno, e-mail a zpráva aspoň 10 znaků, klientská validace. Platný formulář přejde na `/dekujeme`.
- Cesta zákazníka: `/` → `/kurz` (tlačítko „Chci se přihlásit“) → `/kontakt` → `/dekujeme`."""

S2 = """Postav ceník `/cenik` (3 varianty: Samouk 0 Kč, Průvodce 990 Kč, S mentorem 2490 Kč, každá s tlačítkem ‚Vybrat‘ na `/kontakt?varianta=<id>`). Kontaktní formulář teď posílá `POST /api/poptavka` (JSON včetně varianty z URL). Při chybě serveru ukáže srozumitelnou chybu a nechá hodnoty. Změna: tlačítko ‚Chci se přihlásit‘ se všude přejmenuje na ‚Chci začít‘."""

S3 = """Pokračuj podle plánu a dodělej aplikaci. Mezitím se něco rozbilo – najdi to a oprav. Marketing navíc chce na Domů odpočet do konce slevy a červený banner ‚Poslední místa!‘."""

S4X = """Přidej na každou stránku patičku s kontaktem a odkazem na FAQ a na mobilu udělej z menu rozbalovací tlačítko ‚Menu‘ (`aria-expanded`)."""

S4Y = """Přidej do menu odkaz ‚Příběhy‘ a ‚FAQ‘, pokud chybí, a na Domů sekci `pribehy-ukazka` se 2 příběhy s odkazem na `/pribehy`."""

# S5: návrat po pauze s nepravdivým předpokladem (ceník žádné API nevolá, `/api/terminy` v repu není).
S5 = """Po měsíci: lidé se ptají na termíny. Přidej na `/kurz` termíny kurzu z našeho kalendářového API `GET /api/terminy`, které už používáme stejně jako ceník, a u každého termínu tlačítko ‚Rezervovat‘ na `/kontakt?termin=<id>`. Formulář pak termín pošle s poptávkou."""

# S6: změna směru, která ruší dřívější práci (ceník a varianty z S2).
S6 = """Změna: kurz bude zdarma. Ceník zrušte, varianty už nejsou, zůstane jedna přihláška. Stará adresa `/cenik` ať vede na `/kurz`."""

# sezení → [(část, text)]; S4 = dva procesy současně
SESSIONS = {"S1": [("", S1)], "S2": [("", S2)], "S3": [("", S3)], "S4": [("X", S4X), ("Y", S4Y)],
            "S5": [("", S5)], "S6": [("", S6)]}


def prompt(session: str, part: str = "") -> str:
    """Text zadání, který dostane agent (stejný pro A, B i C) + společná patička (build/test, jen repo)."""
    text = dict(SESSIONS[session])[part]
    # Stejná věta o paměti pro všechna ramena: kde si poznámky vede, je na agentovi (A má OPORU, B/C repo).
    memory = (MEMORY_FIRST if session == "S1" else MEMORY_NEXT)
    return text + "\n\n" + memory + "\n" + FOOTER


def parts(session: str):
    return [p for p, _ in SESSIONS[session]]


def full_brief(order=None) -> str:
    """Celé zadání sezení `order` (výchozí všech) za sebou (pro párového soudce: na čem se výstupy porovnávají)."""
    out = []
    for s in order or ORDER:
        for part, text in SESSIONS[s]:
            out.append(f"[{s}{part}] {text}")
    return "\n\n".join(out)


# --- recept ramene C ------------------------------------------------------------------------------

RECIPE_FALLBACK = "obsah → vzhled podle pocitu → přístupnost → prázdné a chybové stavy → testy"


def recipe_chain(skill_md: Path = SKILL_MD) -> str:
    """Řetěz ověření ze skillu (`… (obsah → vzhled podle `site.feel` → … → testy)`), bez formátování."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return RECIPE_FALLBACK
    m = re.search(r"\((obsah\s*→.*?testy)\)", text, re.DOTALL)
    if not m:
        return RECIPE_FALLBACK
    chain = re.sub(r"\s+", " ", m.group(1)).strip()
    chain = re.sub(r"vzhled podle\s*`?site\.feel`?", "vzhled podle pocitu ze zadání", chain)
    return chain


def c_recipe(skill_md: Path = SKILL_MD) -> str:
    """Recept ověření pro rameno C – stejné pořadí jako A ve skillu, bez OPORY, karet a plátna."""
    chain = recipe_chain(skill_md)
    chain = re.sub(r"→ testy$", "→ testy kritérií zadání", chain)
    # Jen to, co A ve skillu dostává k ověření (řetěz kroků + build/test jednou na celek), nic navíc.
    return ("# Postup práce\n"
            f"Každou stránku a sekci postav a ověř v tomto pořadí: {chain}.\n"
            "`npm run build && npm test` pusť jednou na ucelený kus práce (`&&`: test jen po prošlém buildu), "
            "ne po každém kroku.\n")


# --- zásah „kolegy“ -------------------------------------------------------------------------------

COLLEAGUE = ("Kolega", "kolega@example.test")
COLLEAGUE_MSG = "úprava stylu"
CODE_EXT = (".tsx", ".ts", ".jsx", ".js")
TEST_RE = re.compile(r"\.(test|spec)\.[tj]sx?$")


def source_files(ws: Path):
    src = Path(ws) / "src"
    if not src.is_dir():
        return []
    return sorted(p for p in src.rglob("*") if p.is_file() and p.suffix in CODE_EXT and not TEST_RE.search(p.name)
                  and "node_modules" not in p.parts and "__tests__" not in p.parts)


def _brace_end(text: str, start: int) -> int:
    """Index za odpovídající `}` k `{` na pozici `start` (řetězce a šablony přeskočí); -1 když nesedí."""
    depth, i, n = 0, start, len(text)
    while i < n:
        c = text[i]
        if c in "\"'`":
            q, i = c, i + 1
            while i < n and text[i] != q:
                i += 2 if text[i] == "\\" else 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def strip_aria_invalid(text: str) -> tuple[str, int]:
    """Odstraní `aria-invalid` z JSX/objektů/setAttribute. Vrací (nový text, počet odstraněných výskytů)."""
    count = 0
    out, i = [], 0
    jsx = re.compile(r"\s+aria-invalid\s*=\s*")
    while True:
        m = jsx.search(text, i)
        if not m:
            break
        j = m.end()
        if j < len(text) and text[j] == "{":
            end = _brace_end(text, j)
        elif j < len(text) and text[j] in "\"'":
            end = text.find(text[j], j + 1) + 1 or -1
        else:
            end = -1
        if end <= 0:
            out.append(text[i:m.end()])
            i = m.end()
            continue
        out.append(text[i:m.start()])
        i = end
        count += 1
    out.append(text[i:])
    text = "".join(out)
    # klíč objektu (spread props): "aria-invalid": výraz,   ['aria-invalid']: …
    obj = re.compile(r"""\s*\[?["']aria-invalid["']\]?\s*:\s*[^,}\n]+,?""")
    text, n = obj.subn("", text)
    count += n
    # el.setAttribute("aria-invalid", …);
    text, n = re.subn(r"""[^\n;]*\.setAttribute\(\s*["']aria-invalid["'][^;\n]*\)\s*;?""", "", text)
    count += n
    return text, count


# aria-invalid jako atribut / klíč / setAttribute (ne selektor `[aria-invalid="true"]` v řetězci nebo CSS)
ARIA_ATTR = re.compile(r"""\saria-invalid\s*=\s*[{"']|["']aria-invalid["']\]?\s*:|setAttribute\(\s*["']aria-invalid""")
CENIK_LIT = re.compile(r"""(["'`])/cenik\1""")
ROUTE_CTX = re.compile(r"""\bpath\s*[=:]\s*\{?\s*$""")
NAV_HINT = re.compile(r"<nav\b|\bnav\b|menu|Menu|NavLink|navigation|Header|header|Layout", re.MULTILINE)


def find_menu_cenik(files: dict[Path, str]):
    """Najde literál "/cenik", který patří odkazu „Ceník“ v menu (ne definici routy). Vrací (soubor, offset) nebo None."""
    best = None
    for path, text in files.items():
        for m in CENIK_LIT.finditer(text):
            before = text[max(0, m.start() - 40):m.start()]
            if ROUTE_CTX.search(before):
                continue  # <Route path="/cenik"> / { path: "/cenik" } – to je routa, ne odkaz
            window = text[max(0, m.start() - 250):m.end() + 250]
            score = 0
            if re.search(r"Cen[ií]k", window):
                score += 2
            if NAV_HINT.search(text) or NAV_HINT.search(path.stem):
                score += 1
            if re.search(r"\b(to|href)\s*[=:]\s*\{?\s*$", before):
                score += 1
            if best is None or score > best[0]:
                best = (score, path, m.start())
    if best is None or best[0] < 2:
        return None
    return best[1], best[2]


def _git(ws, *args, check=True):
    exe = shutil.which("git") or "git"
    r = subprocess.run([exe, "-c", "core.autocrlf=false", *args], cwd=ws, capture_output=True, check=False)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args[:3])} -> {r.returncode}: {(r.stdout + r.stderr).decode('utf-8', 'replace')[-400:]}")
    return r.stdout.decode("utf-8", "replace")


def inject_colleague(ws: Path, verify=None) -> dict:
    """Zavede obě regrese a commitne je jako `Kolega` se zprávou „úprava stylu“. Nic jiného nemění.

    `verify(ws) -> (ok, detail)` (volitelně, např. `npm run build`): když po zásahu neprojde, zásah se vrátí
    a výsledek je `partial` – skutečný kolega rozbitý build necommitne. Do OPORY ani poznámek se nic nepíše."""
    ws = Path(ws)
    files = {p: p.read_text(encoding="utf-8", errors="replace") for p in source_files(ws)}
    changed: dict[Path, str] = {}
    result = {"aria_invalid": {"done": False}, "cenik_link": {"done": False}}

    removed, touched = 0, []
    for p, text in files.items():
        if "aria-invalid" not in text:
            continue
        new, n = strip_aria_invalid(text)
        if n:
            changed[p] = new
            removed += n
            touched.append(str(p.relative_to(ws)).replace("\\", "/"))
    left = [str(p.relative_to(ws)).replace("\\", "/") for p, t in files.items() if ARIA_ATTR.search(changed.get(p, t))]
    result["aria_invalid"] = {"done": removed > 0 and not left, "removed": removed, "files": touched, "left_in": left,
                              **({"reason": "v src/ žádné aria-invalid (už odstraněno nebo nikdy nebylo)"} if not removed else {})}

    current = {p: changed.get(p, t) for p, t in files.items()}
    hit = find_menu_cenik(current)
    if hit:
        p, off = hit
        text = current[p]
        q = text[off]
        changed[p] = text[:off] + f"{q}/cennik{q}" + text[off + len("/cenik") + 2:]
        result["cenik_link"] = {"done": True, "file": str(p.relative_to(ws)).replace("\\", "/")}
    else:
        already = any(re.search(r"""(["'`])/cennik\1""", t) for t in current.values())
        result["cenik_link"] = {"done": False, "reason": "odkaz /cennik už je v kódu" if already else
                                "nenalezen literál \"/cenik\" u odkazu Ceník mimo definici routy"}

    if not changed:
        result.update({"injection": "noop", "commit": None})
        return result

    originals = {p: files[p] for p in changed}
    for p, text in changed.items():
        p.write_text(text, encoding="utf-8", newline="")
    if verify is not None:
        good, detail = verify(ws)
        result["verify"] = {"ok": good, "detail": str(detail)[-400:]}
        if not good:  # rozbitý build kolega necommitne: zásah zpět
            for p, text in originals.items():
                p.write_text(text, encoding="utf-8", newline="")
            result.update({"injection": "partial", "commit": None, "reverted": True})
            result["aria_invalid"]["done"] = result["cenik_link"]["done"] = False
            return result
    rels = [str(p.relative_to(ws)).replace("\\", "/") for p in changed]
    dirty_other = [ln[3:] for ln in _git(ws, "status", "--porcelain").splitlines()
                   if ln[3:].strip().strip('"') not in rels]
    _git(ws, "add", "--", *rels)
    _git(ws, "-c", f"user.name={COLLEAGUE[0]}", "-c", f"user.email={COLLEAGUE[1]}", "commit", "-q",
         "--author", f"{COLLEAGUE[0]} <{COLLEAGUE[1]}>", "-m", COLLEAGUE_MSG, "--only", "--", *rels)
    result["commit"] = _git(ws, "rev-parse", "HEAD").strip()
    result["files"] = rels
    result["dirty_other"] = dirty_other[:20]  # neuložená práce agenta zůstala mimo commit kolegy
    full = result["aria_invalid"]["done"] and result["cenik_link"]["done"]
    result["injection"] = "full" if full else "partial"
    return result
