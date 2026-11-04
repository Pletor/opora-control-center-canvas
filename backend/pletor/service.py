"""Pletor: rozhovor člověka s Jarvisem nad srdcem (docs/navrhy/2026-11-04-pletor-jarvis.md, P1).

`message` uloží zprávu člověka, složí vstup modelu (podklady = `context.build_context`: stav srdce, snímek, tickety,
eskalace, rozhodnutí, monitoring a Schránka, čtené funkcemi, ne přes HTTP), spustí jeden tah (`session.turn`),
akce zkontroluje (`actions.validate`) a provede: `heart_message` stejnou cestou jako `POST /api/brain/heart/messages` (`heart.message`, jen se zapnutou
bránou), `vault_note` do `brain/pletor_decisions.jsonl` projektu. Pletor nikdy nezapisuje na plátno ani nevolá bránu.
"""
import threading
import time
from pathlib import Path

from backend.brain_opora.determinism import brain_files, gate, gate_setting
from backend.brain_opora.heart import command
from backend.brain_opora.heart.process import run_process
from backend.pletor import actions, brains, store
from backend.pletor.context import build_context, heart_line

FOLDER = "pletor"


def _iso(moment):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(moment))


VOICE = ("REŽIM: HLAS – odpověz nejvýš dvěma větami, prostým textem bez výčtů a markdownu, čitelným nahlas, česky. "
         "Čísla piš slovy, kde to jde, a nepiš zkratky, emoji, odkazy, ID ani znaky jako * # / _ `, syntéza je čte špatně.")


HISTORY = brains.HISTORY + 1  # + právě uložená zpráva člověka, ta jde modelu zvlášť


class Pletor:
    def __init__(self, service, heart, *, runner=run_process, find=command.find_claude, clock=time.time):
        self.service, self.heart, self.runner, self.find, self.clock = service, heart, runner, find, clock
        self.transport = brains.http  # Ollama (P2); testy vyměňují
        self.folder = Path(service.root) / FOLDER
        self.lock = threading.Lock()  # jedna relace na aplikaci: tahy jdou po jednom

    def _context(self, project, workspace):
        return heart_line(self.heart.status(project)), gate.escalations(self.service, project, workspace)

    def state(self, project, workspace):
        heart, escalations = self._context(project, workspace)
        return {"messages": store.messages(self.folder, project, workspace), "heart": heart,
                "escalations": escalations}

    def _run(self, project, workspace, action):
        if action["type"] == "heart_message":
            if not gate_setting.is_on(self.service, project):
                return False, "Srdce pracuje jen v projektu se zapnutou bránou."
            pending = self.heart.message(project, workspace, action["text"])
            return True, f"Ve frontě srdce: {pending}."
        # shortcut: rozhodnutí jde do brain/pletor_decisions.jsonl, ne do Schránky (README), dokud Schránka nemá druh rozhodnutí
        store.append_decision(brain_files.brain_dir(self.service, project), _iso(self.clock()), workspace,
                              action["text"])
        return True, f"Zapsáno do brain/{store.DECISIONS}."

    def message(self, project, workspace, text, voice=False, on_delta=None):
        """`{reply, actions: [{type, text, ok, detail?}]}`; selhání modelu je odpověď bez akcí, ne výjimka.
        `voice` (P3): odpověď se čte nahlas, vstup modelu dostane řádek `VOICE`.
        `on_delta(text)` (stream): kousky `reply` za běhu, složené = `reply`; přepnutí mozku ani odpověď, která
        neprodlužuje už poslané (chyba), kousek nedostane."""
        store.append_message(self.folder, _iso(self.clock()), project, workspace, "human", text)
        switch = brains.command(text)  # přepnutí mozku je věta bez modelu (P2), modelu se nepředá
        if switch:
            reply = brains.switch(self.folder, *switch, transport=self.transport)[1]
            store.append_message(self.folder, _iso(self.clock()), project, workspace, "pletor", reply)
            return {"reply": reply, "actions": []}
        sent = []

        def emit(piece):
            sent.append(piece)
            on_delta(piece)

        try:
            context = build_context(self.service, self.heart, project, workspace) + (f"\n\n{VOICE}" if voice else "")
            history = store.messages(self.folder, project, workspace, HISTORY)[:-1]
            with self.lock:
                reply, raw = brains.turn(self.folder, context, text, history, runner=self.runner, find=self.find,
                                         transport=self.transport, on_delta=emit if on_delta else None)
        except RuntimeError as error:
            reply, raw = str(error), []
        so_far = "".join(sent)
        if on_delta and reply.startswith(so_far) and reply != so_far:
            on_delta(reply[len(so_far):])  # prostý text, Ollama nebo zbytek po ořezu: složené kousky = reply
        done = []
        for action, problem in actions.validate(raw):
            if problem is None:
                try:
                    ok, detail = self._run(project, workspace, action)
                except OSError as error:
                    ok, detail = False, f"Zápis selhal: {error}"
            else:
                ok, detail = False, problem
            done.append({**action, "ok": ok, "detail": detail})
        store.append_message(self.folder, _iso(self.clock()), project, workspace, "pletor", reply)
        return {"reply": reply, "actions": done}
