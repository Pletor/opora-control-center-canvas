"""Zadání sezení, recept ramene C a zásah kolegy (bez modelu, bez npm)."""
import shutil
import subprocess
from pathlib import Path

import pytest

import sessions

MULTI = Path(__file__).resolve().parent
T0 = MULTI.parent / "templates" / "T0"
GIT = ["git", "-c", "user.name=eval", "-c", "user.email=eval@local", "-c", "core.autocrlf=false"]


def git(ws, *args):
    return subprocess.run([*GIT, *args], cwd=ws, capture_output=True, check=True, text=True, encoding="utf-8").stdout


@pytest.fixture
def oracle_s2(tmp_path):
    ws = tmp_path / "w"
    shutil.copytree(T0, ws, ignore=shutil.ignore_patterns("node_modules", "dist"))
    git(ws, "init", "-q", "-b", "main")
    git(ws, "add", "-A")
    git(ws, "commit", "-qm", "T0")
    for s in ("S1", "S2"):
        git(ws, "apply", "--whitespace=nowarn", str(MULTI / "oracles" / s / "oracle.patch"))
        git(ws, "add", "-A")
        git(ws, "commit", "-qm", s)
    return ws


def test_zasah_nad_oracle_s2_zavede_obe_regrese(oracle_s2):
    ws = oracle_s2
    res = sessions.inject_colleague(ws)
    assert res["injection"] == "full", res
    kontakt = (ws / "src" / "pages" / "Kontakt.tsx").read_text(encoding="utf-8")
    assert "aria-invalid" not in kontakt
    assert "aria-describedby" in kontakt  # validace a zbytek pole zůstaly
    assert '"/cennik"' in (ws / "src" / "nav.ts").read_text(encoding="utf-8")
    assert 'path="/cenik"' in (ws / "src" / "App.tsx").read_text(encoding="utf-8")  # routa zůstala
    assert git(ws, "log", "-1", "--format=%an <%ae>|%cn|%s").strip() == "Kolega <kolega@example.test>|Kolega|úprava stylu"
    changed = set(git(ws, "show", "--name-only", "--format=", "HEAD").split())
    assert changed == {"src/pages/Kontakt.tsx", "src/nav.ts"}


def test_zasah_je_idempotentni(oracle_s2):
    ws = oracle_s2
    sessions.inject_colleague(ws)
    head = git(ws, "rev-parse", "HEAD").strip()
    tree = git(ws, "rev-parse", "HEAD^{tree}").strip()
    again = sessions.inject_colleague(ws)
    assert again["injection"] == "noop" and again["commit"] is None
    assert git(ws, "rev-parse", "HEAD").strip() == head
    assert git(ws, "rev-parse", "HEAD^{tree}").strip() == tree
    assert git(ws, "status", "--porcelain").strip() == ""


def test_zasah_necommitne_neulozenou_praci_agenta(oracle_s2):
    ws = oracle_s2
    (ws / "src" / "pages" / "Domu.tsx").write_text("// rozpracováno agentem\n", encoding="utf-8")
    res = sessions.inject_colleague(ws)
    assert res["injection"] == "full"
    assert "src/pages/Domu.tsx" in " ".join(res["dirty_other"])
    assert "src/pages/Domu.tsx" not in git(ws, "show", "--name-only", "--format=", "HEAD")
    assert "Domu.tsx" in git(ws, "status", "--porcelain")


def test_neprojde_overeni_zasah_se_vrati(oracle_s2):
    ws = oracle_s2
    head = git(ws, "rev-parse", "HEAD").strip()
    res = sessions.inject_colleague(ws, verify=lambda _ws: (False, "build selhal"))
    assert res["injection"] == "partial" and res["reverted"] and res["commit"] is None
    assert git(ws, "rev-parse", "HEAD").strip() == head
    assert git(ws, "status", "--porcelain").strip() == ""


def test_zasah_bez_formulare_a_ceniku_je_partial(tmp_path):
    ws = tmp_path / "w"
    (ws / "src").mkdir(parents=True)
    (ws / "src" / "App.tsx").write_text('export const x = <a href="/kurz">Kurz</a>;\n', encoding="utf-8")
    git(ws, "init", "-q", "-b", "main")
    git(ws, "add", "-A")
    git(ws, "commit", "-qm", "x")
    res = sessions.inject_colleague(ws)
    assert res["injection"] == "noop"
    assert res["aria_invalid"]["done"] is False and "reason" in res["aria_invalid"]
    assert res["cenik_link"]["done"] is False


def test_strip_aria_invalid_tvary():
    src = ('<input aria-invalid={errors.a ? "true" : undefined} id="a" />\n'
           "<input id='b' aria-invalid='true' />\n"
           '<input {...{ "aria-invalid": bad, id: "c" }} />\n'
           'el.setAttribute("aria-invalid", "true");\n'
           "const css = '[aria-invalid=\"true\"] { color: x }';\n"
           "<input aria-invalid={fn({a: {b: 1}})} />\n")
    out, n = sessions.strip_aria_invalid(src)
    assert n == 5
    assert not sessions.ARIA_ATTR.search(out)
    assert '[aria-invalid="true"]' in out  # selektor ve stylu zůstává
    assert 'id="a"' in out and "id='b'" in out and 'id: "c"' in out


def test_ceniku_v_menu_najde_odkaz_ne_routu():
    files = {Path("src/App.tsx"): '<Route path="/cenik" element={<Cenik />} />',
             Path("src/Header.tsx"): '<nav><NavLink to="/cenik">Ceník</NavLink></nav>'}
    hit = sessions.find_menu_cenik(files)
    assert hit and hit[0] == Path("src/Header.tsx")
    only_routes = {Path("src/routes.ts"): 'export const R = [{ path: "/cenik", label: "Ceník" }];'}
    assert sessions.find_menu_cenik(only_routes) is None  # odkaz z routy by rozbil i routu → partial


def test_recept_c_je_recept_a_bez_opory():
    chain = sessions.recipe_chain()
    assert chain.startswith("obsah →") and "testy" in chain
    text = sessions.c_recipe()
    assert "vzhled podle pocitu ze zadání" in text
    for word in ("OPOR", "opora", "site.feel", "spec.steps", "kart"):
        assert word not in text


def test_zadani_neopakuji_plan():
    assert "/faq" in sessions.prompt("S1") and "/pribehy" in sessions.prompt("S1")
    for s in ("S2", "S3"):
        assert "/faq" not in sessions.prompt(s) and "/pribehy" not in sessions.prompt(s)
    assert sessions.parts("S4") == ["X", "Y"]
    assert "aria-expanded" in sessions.prompt("S4", "X") and "pribehy-ukazka" in sessions.prompt("S4", "Y")
