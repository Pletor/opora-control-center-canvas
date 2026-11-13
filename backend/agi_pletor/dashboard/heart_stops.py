"""Kde se srdce může zastavit (docs/navrhy/2026-11-13-pruhled-srdce.md §3): úplný seznam zarážek, u každé zda právě
platí, co ji způsobuje a čím ji uvolnit. Seznam je pevný, aby agent i člověk viděli i zarážky, které teď neplatí.
"""
from backend.brain_opora.determinism import gate_setting

SLOW_WRITE_SHARE = 0.5  # víc než polovina dávky čekala na zápis do OPORY


def _failures(last, *needles):
    """Selhání jen z poslední dávky: zarážka říká, co platí teď, starší dávky jsou v rozpadu dávek."""
    return [f"{last.get('at')}: {item['tool']} → {str(item['error'])[:80]}" for item in last.get("failures") or []
            if any(needle in str(item.get("error")) for needle in needles)]


def stops(service, heart, project, view):
    status = heart.status(project)
    now = view.get("now") if isinstance(view.get("now"), dict) else {}
    last = view["batches"][-1] if isinstance(view.get("batches"), list) and view["batches"] else {}
    write_share = next((phase["share"] for phase in last.get("phases") or [] if phase["id"] == "opora_write"), 0)
    pipeline = view.get("pipeline") if isinstance(view.get("pipeline"), list) else []
    done = next((run for run in pipeline if run["status"] == "succeeded"), {"nodes": []})  # poslední dokončený běh
    snapshot_ms = max((node["ms"] or 0 for node in done["nodes"] if node["node"] == "snimek"), default=0)
    timeouts = _failures(last, "server_unreachable", "timed out")
    unknown = _failures(last, "usage:")
    human = _failures(last, "http_409", "human must", "Člověk")
    caps = view.get("caps") if isinstance(view.get("caps"), dict) else {}
    return [
        {"id": "off", "label": "Srdce vypnuté", "active": not status["enabled"],
         "detail": "OPORA_HEART=off nebo server mimo loopback.", "lever": "Spustit OPORU bez OPORA_HEART=off na 127.0.0.1."},
        {"id": "gate", "label": "Brána projektu vypnutá", "active": not gate_setting.is_on(service, project),
         "detail": "Tok srdce vstupy zahodí (port empty).", "lever": "Velín → Autonomie: zapnout bránu projektu."},
        {"id": "hour_cap", "label": "Strop dávek za hodinu", "active": now.get("state") == "hour_cap",
         "detail": f"Nejvýš {caps.get('per_hour', '?')} automatických dávek za hodinu.",
         "lever": "Velín → Srdce → Stropy (per_hour), nebo zpráva člověka strop obejde."},
        {"id": "sleeping", "label": "Spánek po limitu předplatného", "active": status["sleeping"],
         "detail": f"Do {status.get('sleepingUntil') or '—'} (rate_sleep_seconds {caps.get('rate_sleep_seconds', '?')}).",
         "lever": "Počkat, nebo zkrátit rate_sleep_seconds ve Velínu → Srdce → Stropy."},
        {"id": "error", "label": "Chyba toku nebo dávky", "active": bool(status.get("error")),
         "detail": status.get("error") or "—", "lever": "Opravit příčinu z textu chyby; vstupy počkají a pustí se znovu."},
        {"id": "git", "label": "Chyba čtení gitu", "active": bool(status.get("gitError")),
         "detail": status.get("gitError") or "—", "lever": "Opravit repozitář projektu (git status v jeho složce)."},
        {"id": "lock", "label": "Zápisy srdce čekají na server", "active": write_share >= SLOW_WRITE_SHARE
            or snapshot_ms > 30000,
         "detail": f"Dávka {last.get('at') or '—'} čekala na zápis {round(write_share * 100)} % času; poslední "
                   f"dokončený snímek trval {round(snapshot_ms / 1000)} s.",
         "lever": "Server zdržel zámek projektu (dlouhé čtení pod zámkem) nebo jiná práce; kdo to byl, ukazují "
                  "pomalé požadavky serveru. Zrychlit ten požadavek, ne zvyšovat timeout."},
        {"id": "timeout", "label": "Zápis srdce vypršel (60 s)", "active": bool(timeouts), "detail": "; ".join(timeouts[:3]) or "—",
         "lever": "Srdce zápis zopakuje; trvalé řešení je rychlý server (viz zápisy čekají na server)."},
        {"id": "unknown_command", "label": "Srdce volá neexistující příkaz", "active": bool(unknown),
         "detail": "; ".join(unknown[:3]) or "—", "lever": "Skill srdce v Brainu je jiný než nástroj opora_heart.py; srovnat verze."},
        {"id": "human_only", "label": "Krok patří člověku", "active": bool(human) or now.get("state") == "idle"
            and status.get("idleReason") == "waiting_human",
         "detail": "; ".join(human[:3]) or "—", "lever": "Velín → Autonomie: co čeká na člověka."},
    ]
