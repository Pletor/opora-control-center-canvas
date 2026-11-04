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
from backend.pletor import actions, session, store
from backend.pletor.context import build_context, heart_line

FOLDER = "pletor"


def _iso(moment):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(moment))


def prompt(context, text):
    return f"{context}\n\nZPRÁVA ČLOVĚKA:\n{text}"


class Pletor:
    def __init__(self, service, heart, *, runner=run_process, find=command.find_claude, clock=time.time):
        self.service, self.heart, self.runner, self.find, self.clock = service, heart, runner, find, clock
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

    def message(self, project, workspace, text):
        """`{reply, actions: [{type, text, ok, detail?}]}`; selhání modelu je odpověď bez akcí, ne výjimka."""
        store.append_message(self.folder, _iso(self.clock()), project, workspace, "human", text)
        try:
            with self.lock:
                reply, raw = session.turn(self.folder, prompt(build_context(self.service, self.heart, project, workspace),
                                                              text), runner=self.runner, find=self.find)
        except RuntimeError as error:
            reply, raw = str(error), []
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
