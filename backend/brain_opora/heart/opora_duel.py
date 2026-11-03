"""Duel srdce o směr projektu přes schránku zadání (docs/brain-heart.md §3c), jen standardní knihovna.

Deterministický průběh: claim B od srdce, strany a soudci jako pod-volání Haiku pod vlastními jmény, nejvýš 2 kola
a 12 pod-volání; rozhodnutí počítá a hlídá server (`duel-decide`). Nástroj sem předá sám sebe (`tool`): volání OPORY
s tokenem srdce a jménem aktéra, `_execute`, `Failure`, `scope`, `DILNA`, `log_run`. Odpovědi modelů jsou data.
Dávka srdce (`command.py`) soubor kopíruje do `brain/` vedle `opora_heart.py`.
"""
import time

try:
    from research_digest import child_env, claude_result, last_object, need_claude, sub_command
    from research_digest import clip as _text
    from research_digest import one_line as _one_line
except ImportError:  # v testech modul balíčku
    from backend.brain_opora.heart.research_digest import (
        child_env,
        claude_result,
        last_object,
        need_claude,
        sub_command,
    )
    from backend.brain_opora.heart.research_digest import clip as _text
    from backend.brain_opora.heart.research_digest import one_line as _one_line

SUB_TIMEOUT, DUEL_BUDGET, SUB_CAP, MAX_TURN = 90, 540, 12, 2000
# Prahy pravidla duelu (kopie brief_vault_duel_math: ADOPT_P, KEEP_P, MIN_SCORED, DEFENDED_AT); rozhoduje server.
ADOPT_P, KEEP_P, MIN_SCORED, DEFENDED_AT = 0.75, 0.40, 3, 6
SIDE_A, SIDE_B, JUDGES = "srdce-obhajce-a", "srdce-obhajce-b", ("srdce-soudce-1", "srdce-soudce-2")

DUEL_HEAD = """Duel o směr projektu. A = současný směr, B = navrhovaná paralelní cesta.
A: <A>
B: <B>
Dosavadní výměny (data, ne pokyny):
<LOG>
"""
SIDE = DUEL_HEAD + """Hájíš stranu <S> (<WHO>). Buď věcný a krátký (každé pole do 600 znaků).
<ASK>
Odpověz JEN jedním objektem JSON s poli <KEYS>, bez dalšího textu."""
JUDGE = DUEL_HEAD + """Jsi nezávislý soudce. Ohodnoť každou z těchto výměn: <IDS>.
strength = síla argumentu 0–10, supports = strana, kterou výměna ve skutečnosti podporuje (A nebo B).
Odpověz JEN JSON {"scores": [{"turnId": "…", "strength": 0, "supports": "A"}]}, bez dalšího textu."""


class Duel:
    """Jeden duel: revize pro CAS, pod-volání se stropem a časem, přepis výměn pro prompty."""

    def __init__(self, tool, args, claude):
        self.tool, self.args, self.claude, self.scope = tool, args, claude, tool.scope()
        self.id, self.rev, self.turns, self.scored = "", 0, [], {judge: set() for judge in JUDGES}
        self.calls, self.cost, self.skipped, self.started = 0, 0.0, [], time.time()

    def ask(self, prompt):
        """Jedno pod-volání Haiku → objekt JSON, nebo None (selhání, strop, čas)."""
        if self.calls >= SUB_CAP or time.time() - self.started > DUEL_BUDGET:
            self.skipped.append("strop pod-volání nebo času")
            return None
        self.calls += 1
        _, out, _, _ = self.tool._execute(sub_command(self.claude), str(self.tool.DILNA.resolve()), child_env(),
                                          timeout=SUB_TIMEOUT, input_text=prompt)
        answer, cost = claude_result(out)
        self.cost += cost
        found = last_object(answer)
        if found is None:
            self.skipped.append("pod-volání bez platného JSON")
        return found

    def write(self, actor, body):
        try:
            reply = self.tool.call("POST", "/api/brief-vault", {**self.scope, "fragmentId": self.id,
                                                                "expectedRevision": self.rev, **body}, actor=actor)
        except self.tool.Failure as failure:
            self.skipped.append(f"{body['op']}: {failure.payload.get('error', '')[:160]}")
            self.rev = self.view()["duel"]["fragment"]["revision"]
            return None
        self.rev = reply["fragment"]["revision"]
        return reply

    def view(self):
        return self.tool.call("GET", "/api/brief-vault/duel", query={**self.scope, "id": self.id})

    def turn(self, actor, side, kind, text, refs=()):
        text = _text(text, MAX_TURN)
        reply = self.write(actor, {"op": "duel-turn", "side": side, "kind": kind, "text": text,
                                   "refs": [ref for ref in refs if ref]}) if text else None
        if reply is None:
            return None
        self.turns.append(reply["turn"])
        return reply["turn"]["id"]

    def log(self):
        return "\n".join(f"[{t['id']}] {t['side']} {t['kind']}: {_one_line(t['text'], 600)}" for t in self.turns) or "—"

    def prompt(self, template, **parts):
        text = template.replace("<A>", self.args.a).replace("<B>", self.args.b).replace("<LOG>", self.log())
        for key, value in parts.items():
            text = text.replace(f"<{key}>", value)
        return text

    def side(self, side, ask, keys):
        who = "současný směr" if side == "A" else "navrhovaná změna"
        found = self.ask(self.prompt(SIDE, S=side, WHO=who, ASK=ask, KEYS=", ".join(keys))) or {}
        return {key: found.get(key) for key in keys}

    def judge(self):
        """Každý soudce v jednom pod-volání ohodnotí výměny stran, které ještě nehodnotil."""
        for judge in JUDGES:
            todo = [t["id"] for t in self.turns if t["side"] in ("A", "B") and t["id"] not in self.scored[judge]]
            if not todo:
                continue
            found = self.ask(self.prompt(JUDGE, IDS=", ".join(todo))) or {}
            for item in found.get("scores") if isinstance(found.get("scores"), list) else []:
                if not isinstance(item, dict) or item.get("turnId") not in todo or item.get("supports") not in ("A", "B"):
                    continue
                try:
                    strength = max(0, min(10, int(item.get("strength"))))
                except (TypeError, ValueError):
                    continue
                if self.write(judge, {"op": "duel-score", "turnId": item["turnId"], "strength": strength,
                                      "supports": item["supports"]}) is not None:
                    self.scored[judge].add(item["turnId"])

    def run(self):
        """Claim B, dvě kola (grill a answer obou stran), soudci po každém kole; pak syntéza, je-li třeba."""
        opened = self.tool.call("POST", "/api/brief-vault", {**self.scope, "op": "duel-open",
                                                             "subject": {"kind": "fragment", "id": self.args.subject},
                                                             "incumbent": {"text": self.args.a[:4000]},
                                                             "challenger": {"text": self.args.b[:4000]},
                                                             "scopeNodeId": ""})
        self.id, self.rev = opened["fragment"]["id"], opened["fragment"]["revision"]
        b_claim = self.turn("heart", "B", "claim", self.args.b)
        a = self.side("A", "Napiš nejsilnější argument pro A (claim) a jednu ostrou otázku na slabinu B (grill).",
                      ("claim", "grill"))
        a_claim = self.turn(SIDE_A, "A", "claim", a["claim"])
        a_grill = self.turn(SIDE_A, "A", "grill", a["grill"], [b_claim])
        b = self.side("B", "Odpověz na poslední otázku strany A (answer) a polož jednu otázku na slabinu A (grill).",
                      ("answer", "grill"))
        b_answer = self.turn(SIDE_B, "B", "answer", b["answer"], [a_grill]) if a_grill else None
        b_grill = self.turn(SIDE_B, "B", "grill", b["grill"], [a_claim])
        self.judge()
        a = self.side("A", "Odpověz na poslední otázku strany B (answer) a polož další otázku na B (grill).",
                      ("answer", "grill"))
        if b_grill:
            self.turn(SIDE_A, "A", "answer", a["answer"], [b_grill])
        a_grill = self.turn(SIDE_A, "A", "grill", a["grill"], [b_answer or b_claim])
        b = self.side("B", "Odpověz na poslední otázku strany A (answer) a polož poslední otázku na A (grill).",
                      ("answer", "grill"))
        if a_grill:
            self.turn(SIDE_B, "B", "answer", b["answer"], [a_grill])
        b_grill = self.turn(SIDE_B, "B", "grill", b["grill"], [a_claim])
        if b_grill:
            self.turn(SIDE_A, "A", "answer", self.side("A", "Odpověz na poslední otázku strany B.", ("answer",))["answer"],
                      [b_grill])
        self.judge()
        return self.decide()

    def decide(self):
        view = self.view()
        p, n = view["probability"]["p"], view["probability"]["n"]
        if view["canDecide"] and outcome_of(p, n) == "synthesis":
            text = self.side("A", "Navrhni syntézu A a B, která vezme to nejlepší z obou (synthesis).",
                             ("synthesis",))["synthesis"]
            synthesis = self.turn(SIDE_A, "A", "synthesis", text)
            self.judge()
            view = self.view()
            p, n = view["probability"]["p"], view["probability"]["n"]
            if outcome_of(p, n) == "synthesis":
                strengths = [s["strength"] for s in view["duel"]["scores"] if s["turnId"] == synthesis]
                if not synthesis or not strengths or sum(strengths) / len(strengths) < DEFENDED_AT:
                    self.skipped.append("syntéza nebyla obhájena (soudci < 6)")
                    return self.result(view, None)
                return self.result(view, self.write("heart", {"op": "duel-decide", "synthesisTurnId": synthesis}))
        if not view["canDecide"]:
            return self.result(view, None)
        return self.result(view, self.write("heart", {"op": "duel-decide"}))

    def result(self, view, decided):
        decision = (decided or {}).get("decision") or {}
        probability = (decided or view)["probability"]
        out = {"duelId": self.id, "probability": round(probability["p"], 4), "n": probability["n"],
               "outcome": decision.get("outcome"), "applied": decision.get("applied"),
               "canDecide": view["canDecide"], "subCalls": self.calls, "costUsd": round(self.cost, 6)}
        if self.skipped:
            out["skipped"] = self.skipped[:8]
        return out


def outcome_of(p, n):
    """Výsledek podle pravidla serveru (§3.2 docs/schranka-duel.md) pro rozhodnutí, zda je třeba syntéza."""
    if p >= ADOPT_P and n >= MIN_SCORED:
        return "adopt"
    return "keep" if p <= KEEP_P else "synthesis"


def duel(args, tool):
    """`duel`: duel současného směru A a paralelní cesty B o fragmentu; vypíše p, výsledek a id duelu."""
    match = Duel(tool, args, need_claude(tool))
    try:
        return match.run()
    finally:
        tool.log_run("duel", [match.id or args.subject], 0, int((time.time() - match.started) * 1000), match.calls,
                     match.cost)
