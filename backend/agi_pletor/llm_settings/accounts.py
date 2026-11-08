"""Účty Claude Code z UI: přidání dalšího přihlášením a přepnutí (`cswap switch N`).

`start()` zazálohuje dnešní účet (`cswap add`), spustí `claude auth login` a vrátí jeho adresu. Na tomto počítači se
otevře prohlížeč; po přihlášení jiným účtem proces obvykle skončí sám (zpětné volání na localhost). Když stránka ukáže
kód, předá ho `finish(code)` procesu na stdin. `finish()` pak `cswap add` uloží nový účet jako další slot. Bez běžícího
přihlášení `finish()` jen uloží právě přihlášený účet (náprava po přihlášení mimo OPORU). Výstup procesu ven nejde.
"""
import re
import shutil
import subprocess
import threading

from backend.agi_pletor.llm_settings import cswap
from backend.brain_opora.heart import command

URL = re.compile(r"https://\S+")
CODE = re.compile(r"[A-Za-z0-9#_\-]{8,400}")
FINISH_TIMEOUT = 60
SELF_WAIT = 10  # přihlášení bez kódu: chvíle na doběhnutí procesu po zpětném volání
_lock = threading.Lock()
_process = None  # běžící `claude auth login`


def _cswap(which, run, *args):
    binary = which("cswap")
    if not binary:
        raise ValueError(f"claude-swap není nainstalovaný ({cswap.INSTALL_HINT}).")
    done = run([binary, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=cswap.TIMEOUT)
    if done.returncode != 0:
        raise ValueError(f"cswap {args[0]} skončil kódem {done.returncode}.")


def cancel():
    global _process
    if _process is not None and _process.poll() is None:
        _process.kill()
    _process = None


def start(*, find=command.find_claude, popen=subprocess.Popen, run=subprocess.run, which=shutil.which):
    """Spustí přihlášení a vrátí `{url}`; ValueError s českou zprávou, když chybí `claude`/`cswap` nebo adresa nepřišla."""
    global _process
    claude = find()
    if not claude:
        raise ValueError("Claude Code (`claude`) na tomto počítači chybí.")
    with _lock:
        cancel()
        _cswap(which, run, "add")
        _process = popen([claude, "auth", "login"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in _process.stdout:  # shortcut: čeká bez limitu na řádek s adresou, upgrade až když claude někdy zmlkne
            if found := URL.search(line):
                return {"url": found.group(0)}
        cancel()
        raise ValueError("`claude auth login` nevypsal adresu k přihlášení.")


def finish(code="", *, run=subprocess.run, which=shutil.which):
    """Dokončí přihlášení (kód na stdin, nebo počká na samo-dokončené) a `cswap add`; vrací sekci účtů jako `cswap.read()`."""
    global _process
    code = (code or "").strip()
    if code and not CODE.fullmatch(code):
        raise ValueError("Kód je text, který prohlížeč ukáže po přihlášení.")
    with _lock:
        if _process is not None:
            try:
                if code and _process.poll() is None:
                    _process.communicate(code + "\n", timeout=FINISH_TIMEOUT)
                else:
                    _process.wait(timeout=SELF_WAIT)
            except subprocess.TimeoutExpired:
                if code:
                    cancel()
                    raise ValueError(f"Claude Code přihlášení nedokončil do {FINISH_TIMEOUT} s.")
                raise ValueError("Přihlášení ještě neskončilo: dokonči ho v prohlížeči, nebo vlož kód ze stránky.")
            failed, _process = _process.returncode != 0, None
            if failed:
                raise ValueError("Přihlášení se nezdařilo (kód odmítnut nebo přerušeno).")
        _cswap(which, run, "add")
    return cswap.read(which=which, run=run)


def switch_to(slot, *, run=subprocess.run, which=shutil.which):
    """Přepne na účet `slot` (1…); vrací sekci účtů."""
    if not isinstance(slot, int) or slot < 1:
        raise ValueError("slot je číslo účtu od 1.")
    _cswap(which, run, "switch", str(slot))
    return cswap.read(which=which, run=run)
