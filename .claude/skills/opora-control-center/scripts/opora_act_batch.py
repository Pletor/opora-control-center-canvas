"""Hromadné `act`: víc akcí z agent-state jedním příkazem, bez shellové smyčky a bez 409 ze zastaralých ID.

`opora_hub.py act --action-id A --action-id B …` nebo `act --all-ready --verb V [--verb V2] [--target N]…`.

ID akce je otisk (sloveso, cíl, hlava stavu), takže se po každé provedené akci přepočítá. Dávka proto akce
drží podle stabilního klíče `(verb, targetId)`: po každém kroku načte čerstvý stav a najde akci se stejným klíčem.
Akce, která už není potřeba (např. `accept` pokryl i další), jde do `skipped` s důvodem, ne do chyby.
`--all-ready` po každém kroku přibere i nově vzniklé ready akce zadaných sloves (propose_graph → accept).

Idempotence: provedená akce ze stavu zmizí, takže opakovaná dávka ji přeskočí; claim a review.claim nesou
deterministické `requestId` odvozené z ID akce (otisk slovesa, cíle a hlavy), takže je server přehraje, nezdvojí.
Skutečný konflikt (409 při akci z právě načteného stavu = cizí změna mezi čtením a zápisem) dávku zastaví:
`{error, code, changed, hint, done, skipped}` a kód 3.

Výstup: `{done:[{id, verb, targetId, status}], skipped:[{id, verb?, targetId?, reason}], next}`.
"""
import opora_hub

MAX_STEPS = 50


BatchConflict = opora_hub.BatchConflictError  # cizí změna mezi krokem dávky a zápisem


def key(action):
    return action.get('verb'), action.get('targetId')


def request_id(action):
    """Deterministický klíč zápisu: ID akce už je otisk (verb, targetId, hlava stavu)."""
    return 'act-' + ''.join(ch for ch in str(action['id']) if ch.isalnum() or ch in '_-')[-40:]


def _index(state):
    return {key(action): action for action in state.get('actions', [])}


def changed(before, after):
    """Pole a uzly, kterými se dva snímky agent-state liší: hlavy, cíle akcí a karty."""
    out = []
    heads_before, heads_after = before.get('heads') or {}, after.get('heads') or {}
    out += [f'heads.{name}' for name in sorted(set(heads_before) | set(heads_after))
            if heads_before.get(name) != heads_after.get(name)]
    old, new = _index(before), _index(after)
    targets = {item[1] for item in set(old) ^ set(new)}
    targets |= {item[1] for item in set(old) & set(new) if old[item].get('status') != new[item].get('status')}
    out += [f'action:{target}' for target in sorted(t for t in targets if t is not None)]
    if None in targets:
        out.append('action:-')
    cards_before = {item.get('nodeId'): item for item in before.get('cards', [])}
    cards_after = {item.get('nodeId'): item for item in after.get('cards', [])}
    out += [f'card:{node}' for node in sorted(set(cards_before) | set(cards_after), key=str)
            if cards_before.get(node) != cards_after.get(node)]
    return out


def _skip(original, verb, target, reason):
    return {'id': original, 'verb': verb, 'targetId': target, 'reason': reason}


def _why_gone(state, target):
    """Důvod, proč akce s klíčem ve stavu už není: jiné sloveso na témž cíli, nebo prostě hotovo."""
    other = [action['verb'] for action in state.get('actions', [])
             if target is not None and action.get('targetId') == target and action.get('status') == 'ready']
    return 'no_longer_needed' + (f' (cíl teď nabízí {other[0]})' if other else '')


def _conflict(base, project, workspace, state, action, error, done, skipped):
    """409 při akci z právě načteného stavu: cizí změna. Vrátí, co se změnilo, a co dávka stihla."""
    after, _ = opora_hub.agent_state(base, project, workspace, fresh=True)
    detail = opora_hub.opora_write.explain(error)
    return BatchConflict({
        'ok': False, 'status': 409, 'error': detail.get('error') or 'Stav se mezitím změnil.',
        'code': detail.get('code') or 'conflict', 'action': {k: action.get(k) for k in ('id', 'verb', 'targetId')},
        'changed': changed(state, after), 'done': done, 'skipped': skipped,
        'hint': 'Cizí změna mezi čtením a zápisem; dávka se zastavila. Prohlédni changed (state --fresh) '
                'a spusť tutéž dávku znovu: hotové akce přeskočí, nic se nezdvojí.'})


def run(base, project, workspace, action_ids=(), verbs=(), targets=(), all_ready=False, ttl=900, note=None):
    """Provede dávku akcí v pořadí serveru; vrací `{done, skipped, next}` nebo vyhodí `BatchConflict`."""
    if all_ready and not verbs:
        raise ValueError('act --all-ready potřebuje --verb (např. --verb propose_graph --verb accept).')
    if not all_ready and not action_ids:
        raise ValueError('act potřebuje --action-id (opakovatelné) nebo --all-ready --verb V.')
    state, _ = opora_hub.agent_state(base, project, workspace, fresh=True)
    done, skipped, pending, labels = [], [], [], {}

    def wanted(action):
        return (action.get('status') == 'ready' and action.get('verb') in verbs
                and (not targets or action.get('targetId') in targets))

    if all_ready:
        pending = [key(action) for action in state.get('actions', []) if wanted(action)]
    else:
        by_id = {action.get('id'): action for action in state.get('actions', [])}
        for identifier in dict.fromkeys(action_ids):
            action = by_id.get(identifier)
            if action is None:
                skipped.append({'id': identifier, 'reason': 'stale_id: akce v čerstvém stavu není (už provedená '
                                                             'nebo se stav posunul); dávka nic neprovedla'})
            elif key(action) not in labels:
                labels[key(action)] = identifier
                pending.append(key(action))
    seen = set(pending)
    while pending and len(done) < MAX_STEPS:
        # Další krok = první čekající klíč, který je v čerstvém stavu ready, v pořadí serveru (VERB_ORDER).
        order = [key(action) for action in state.get('actions', []) if action.get('status') == 'ready']
        item = next((found for found in order if found in pending), None)
        if item is None:
            break
        pending.remove(item)
        action = _index(state)[item]
        try:
            opora_hub.perform(base, project, workspace, action, ttl, note, request_id(action))
        except opora_hub.Refused as error:
            skipped.append(_skip(labels.get(item, action['id']), *item, 'refused: ' + str(error)))
            continue
        except opora_hub.HTTPError as error:
            if error.code != 409:
                raise
            raise _conflict(base, project, workspace, state, action, error, done, skipped) from error
        done.append({'id': action['id'], 'verb': item[0], 'targetId': item[1], 'status': 'done'})
        state, _ = opora_hub.agent_state(base, project, workspace, fresh=True)
        if all_ready:
            fresh = [key(found) for found in state.get('actions', []) if wanted(found) and key(found) not in seen]
            pending += fresh
            seen.update(fresh)
    index = _index(state)
    for item in pending:  # co zbylo: ve stavu už není, nebo je blokované
        action = index.get(item)
        reason = (_why_gone(state, item[1]) if action is None else 'step_limit' if action.get('status') == 'ready'
                  else 'blocked: ' + str(action.get('blockReason')))
        skipped.append(_skip(labels.get(item, action and action.get('id')), *item, reason))
    return {'done': done, 'skipped': skipped, 'next': opora_hub.first_ready(opora_hub.ready_actions(state))}
