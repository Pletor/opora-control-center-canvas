"""Pletor: rozhovor člověka s Jarvisem nad srdcem (docs/navrhy/2026-11-04-pletor-jarvis.md, P1).

`message` uloží zprávu člověka, složí vstup modelu (podklady = `context.build_context`: stav srdce, snímek, tickety,
eskalace, rozhodnutí, monitoring a Schránka, čtené funkcemi, ne přes HTTP), spustí jeden tah (`session.turn`),
akce zkontroluje (`actions.validate`) a provede: `heart_message` stejnou cestou jako `POST /api/brain/heart/messages` (`heart.message`, jen se zapnutou
bránou), `vault_note` do `brain/pletor_decisions.jsonl` projektu, `heart_question` / `heart_question_close` otázku
srdci (`questions.py`, docs/navrhy/2026-11-08-pletor-otazky-srdci.md), `heart_escalation_answer` odpověď člověka na
eskalaci srdce stejnou cestou jako panel (`gate.answer` + `gate.wake_heart`). `present` je proaktivní tah po odpovědi
srdce, `escalation` po nové eskalaci srdce (hák brány): zapíše řádek role `heart` a krátkou zprávu Pletora, akce z něj
se nevykonají. Deník (M1c): otázka, upřesnění, odpověď a eskalace srdce jsou řádky `heart` v rozhovoru.
Pletor nikdy nezapisuje na plátno ani nevolá bránu dělníků.
"""
import threading
import time
from pathlib import Path

from backend.brain_opora.determinism import brain_files, gate, gate_setting
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.brain_opora.heart import command
from backend.brain_opora.heart.process import run_process
from backend.agi_pletor import actions, brains, questions, store
from backend.agi_pletor.context import build_context, cut, heart_line

FOLDER = "pletor"


def _iso(moment):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(moment))


VOICE = ("REŽIM: HLAS – odpověz nejvýš dvěma větami, prostým textem bez výčtů a markdownu, čitelným nahlas, česky. "
         "Čísla piš slovy, kde to jde, a nepiš zkratky, emoji, odkazy, ID ani znaky jako * # / _ `, syntéza je čte špatně.")


CONTEXT_TTL = 15  # s: podklady stojí ~1 s a v živém rozhovoru se mezi větami nemění; akce je zahodí
HISTORY = brains.HISTORY + 1  # + právě uložená zpráva člověka, ta jde modelu zvlášť


class Pletor:
    def __init__(self, service, heart, *, runner=run_process, find=command.find_claude, clock=time.time):
        self.service, self.heart, self.runner, self.find, self.clock = service, heart, runner, find, clock
        self.transport = brains.http  # Ollama (P2); testy vyměňují
        self.folder = Path(service.root) / FOLDER
        self.lock = threading.Lock()  # jedna relace na aplikaci: tahy jdou po jednom
        self.contexts = {}  # (projekt, prostor) → (čas, podklady)
        self.announced = set()  # ID eskalací, které už Pletor oznámil (jedna eskalace = jedno oznámení)

    def _context(self, project, workspace):
        return heart_line(self.heart.status(project)), gate.escalations(self.service, project, workspace)

    def state(self, project, workspace):
        heart, escalations = self._context(project, workspace)
        return {"messages": store.messages(self.folder, project, workspace), "heart": heart,
                "escalations": escalations}

    def _podklady(self, project, workspace):
        now = self.clock()
        cached = self.contexts.get((project, workspace))
        if cached and now - cached[0] < CONTEXT_TTL:
            return cached[1]
        built = build_context(self.service, self.heart, project, workspace)
        self.contexts[(project, workspace)] = (now, built)
        return built

    def _journal(self, project, workspace, text):
        store.append_message(self.folder, _iso(self.clock()), project, workspace, "heart", text)

    def _run(self, project, workspace, action):
        if action["type"] == "heart_escalation_answer":
            # Odpovídá člověk: akce projde jen v tahu zahájeném jeho zprávou, Pletor předává jeho slova.
            if not gate_setting.is_on(self.service, project):
                return False, "Srdce pracuje jen v projektu se zapnutou bránou."
            ticket_id = action["ticketId"]
            # jen otázka srdce z prostoru tohoto rozhovoru (jiné Pletor v podkladech nevidí), ne lístek dělníka
            if gate.heart_escalation_workspace(self.service, project, ticket_id) != workspace:
                return False, f"Otázka srdce {ticket_id} v tomto prostoru není."
            try:
                ticket = gate.answer(self.service, project, ticket_id, {"answer": {"text": action["text"]}}, "human")
            except GateError as error:
                return False, str(error)
            # OP-FB0522.c3: stejná cesta jako odpověď v panelu „Čeká na vás“, srdce se vzbudí stejně
            gate.wake_heart(self.service, self.heart, project, ticket)
            self._journal(project, workspace, f"Odpověď člověka na {ticket_id} předána srdci.")
            return True, f"Odpověď na {ticket_id} je u srdce."
        if action["type"] == "heart_question":
            if not gate_setting.is_on(self.service, project):
                return False, "Srdce pracuje jen v projektu se zapnutou bránou."
            question, refined = questions.ask(self.service, project, workspace, action["text"], _iso(self.clock()))
            label = "UPŘESNĚNÍ OTÁZKY PLETORA" if refined else "OTÁZKA PLETORA"
            # OP-FB0522.c1: deník – člověk i Pletor vidí v rozhovoru, na co se srdce ptá a kde to leží
            self._journal(project, workspace, f"{'Upřesnění' if refined else 'Pletor se ptá srdce'} {question['id']}: "
                                              f"{cut(action['text'], 200)}")
            # Otázka Pletora není zadání: bez vstupu brány, jinak ji srdce vyslýchá jako záměr a eskaluje člověku
            self.heart.message(project, workspace, f"{label} {question['id']}: {action['text']}", record_intake=False)
            return True, f"Otázka {question['id']} je ve frontě srdce."
        if action["type"] == "heart_question_close":
            # Uzavírá člověk: akce projde jen tady, v tahu zahájeném jeho zprávou (`present` akce zahazuje).
            if not gate_setting.is_on(self.service, project):
                return False, "Srdce pracuje jen v projektu se zapnutou bránou."
            question = questions.close(self.service, project, action["text"], _iso(self.clock()))
            if question is None:
                return False, "Žádná otevřená otázka pro srdce."
            # OP-FB0522.5: uzavření = schválená varianta; srdce ji rozpracuje na plátno
            last = (question["answers"] or [{"text": "(bez odpovědi)"}])[-1]["text"]
            def end(text):  # věta bez zdvojené tečky
                return text if text.endswith((".", "?", "!")) else text + "."
            self.heart.message(project, workspace, f"SCHVÁLENO {question['id']}: {end(action['text'])} "
                                                   f"Původní otázka: {end(question['text'])} Poslední odpověď: {cut(last, 600)}",
                               record_intake=False)
            return True, f"Otázka {question['id']} je uzavřená, srdce rozpracuje schválenou cestu."
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
            context = self._podklady(project, workspace) + (f"\n\n{VOICE}" if voice else "")
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
        if done:
            self.contexts.clear()  # akce změnila stav srdce nebo rozhodnutí, příští podklady se přečtou znovu
        store.append_message(self.folder, _iso(self.clock()), project, workspace, "pletor", reply)
        return {"reply": reply, "actions": done}

    def _proactive(self, project, workspace, prompt, failure):
        """Tah bez zprávy člověka: vstup se neukládá jako zpráva člověka, akce z odpovědi se zahodí (žádná smyčka);
        chyba modelu je odpověď `failure: chyba`."""
        try:
            history = store.messages(self.folder, project, workspace, HISTORY)
            with self.lock:
                reply, _ = brains.turn(self.folder, self._podklady(project, workspace), prompt, history,
                                       runner=self.runner, find=self.find, transport=self.transport)
        except Exception as error:  # noqa: BLE001 – tah běží na pozadí po události srdce, výpadek modelu je jen věta
            reply = f"{failure}: {error}"
        store.append_message(self.folder, _iso(self.clock()), project, workspace, "pletor", reply)
        return reply

    def present(self, project, workspace, question):
        """Proaktivní tah po odpovědi srdce: deterministické oznámení role `heart` (ukazatel do podkladů, ne celá
        odpověď) a krátká zpráva Pletora, zda je člověk připravený. Odpověď se vykládá až v dalším tahu člověka."""
        # OP-FB0522.3: Pletor promluví sám, když srdce odpoví; jen oznámí, bez akcí, uzavírá jen člověk
        last = question["answers"][-1]
        self._journal(project, workspace,
                      f"Srdce odpovědělo na {question['id']} (téma: {cut(question['text'], 80)}) · uloženo: otázky "
                      f"Pletora ({question['id']}), v podkladech sekce OTÁZKA PRO SRDCE"
                      + (f"; odkazy: {', '.join(last['refs'])}" if last["refs"] else "")
                      + (f"; nevím: {last['reason']}" if last.get("unknown") else "") + ".")
        return self._proactive(project, workspace,
                               f"(Systém, ne člověk.) Srdce má hotovou odpověď na {question['id']}. Odpověď zatím "
                               "NEprezentuj. Krátce zjisti, jestli je člověk připravený a dává pozor, a řekni, čeho "
                               "se to týká. Akce v této odpovědi se nevykonají.", "Pletor odpověď srdce nevyložil")

    def escalation(self, project, workspace, ticket_id, text, withdrawn=False):
        """Hák brány (`gate._announce`, registruje `factory.py`): nová eskalace srdce = řádek deníku a proaktivní tah
        na pozadí (vrátí jeho vlákno), stažená = jen řádek s důvodem (`text`). Opakované oznámení téže eskalace nic."""
        self.contexts.clear()  # sekce eskalací v podkladech se změnila
        if withdrawn:
            self._journal(project, workspace, f"Srdce stáhlo otázku {ticket_id}: {cut(text, 200)}")
            return None
        if ticket_id in self.announced:
            return None
        self.announced.add(ticket_id)
        # OP-FB0522.c2: člověk nepřebíhá do panelu „Čeká na vás“, otázku srdce mu přinese Pletor
        self._journal(project, workspace,
                      f"Srdce se ptá člověka {ticket_id}: {cut(text, 200)} · uloženo: eskalace {ticket_id}")
        prompt = (f"(Systém, ne člověk.) Srdce má na člověka otázku {ticket_id}. Zatím ji NEprezentuj. Řekni, čeho "
                  "se týká, a zjisti, jestli je člověk připravený. Akce v této odpovědi se nevykonají.")
        thread = threading.Thread(target=self._proactive, args=(project, workspace, prompt,
                                                                "Pletor otázku srdce neoznámil"), daemon=True)
        thread.start()
        return thread
