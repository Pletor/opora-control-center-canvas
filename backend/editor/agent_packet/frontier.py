"""Shared read-only frontier classification for API clients and the canvas."""

import re

from backend.editor.agent_memory.card_pipeline import summary as pipeline_summary
from backend.editor.agent_packet.desktop_v3_packets import redact_deep
from backend.editor.agent_packet.sector_status import SectorEdges, sector_blockers, sector_status

CLAIM_PREFIX = 'Převzato:'
TICKET_TYPES = ('research', 'prototype', 'grilling', 'task', 'gate')


def ticket_type(name):
    """Typ workflow: jen předpona názvu `[task]` atd.; `card` nese vrstvu, ne typ."""
    match = re.match(r'\[(\w+)\]', name or '')
    return match.group(1) if match and match.group(1) in TICKET_TYPES else ''


def claim_of(frame):
    for line in (frame or '').splitlines():
        if line.strip().startswith(CLAIM_PREFIX):
            return line.strip()[len(CLAIM_PREFIX):].strip()
    return ''


class FrontierIndex:
    """Co je pro všechny sektory stejné: stav sektorů, uzavření, jména, děti podle rodiče a vazby podle cíle.

    Postaví se jednou (O(N + E)); `work_overview` ji sdílí pro všechny rodiče místo výpočtu na rodiče.
    """

    def __init__(self, graph, state):
        nodes = graph.get('nodes', [])
        self.names = {n['id']: n.get('name', '') for n in nodes}
        self.statuses = sector_status(graph, state)
        self.done = {cid: bool(state.get('nodes', {}).get(cid, {}).get('done', {}).get('confirmed')) for cid in self.names}
        for sid, status in self.statuses.items():
            self.done[sid] = status['status'] == 'verified'
        self.children = {}
        for n in nodes:
            self.children.setdefault(n.get('parentId'), []).append(n)
        self.incoming = {}
        for e in graph.get('edges', []):
            if e.get('port', 'next') == 'next':
                self.incoming.setdefault(e.get('target'), []).append(e.get('source'))
        self._sector_edges = None

    def sector_edges(self, graph):
        # Líně: jen když se opravdu ptáme na blokace karty (stejně jako dřív, kdy se hrany četly až u karty).
        if self._sector_edges is None:
            self._sector_edges = SectorEdges(graph)
        return self._sector_edges


def frontier(graph, state, sector_id, frames, leases=None, index=None, merged=frozenset()):
    """Mapa wayfinderu nad sektorem: karty sektoru rozdělené na uzavřené, převzaté, blokované a frontier.

    Blokace je vazba `next` (nebo bez portu) z neuzavřené karty. Převzetí je řádek `Převzato:`
    v `agent-workspace.frame`. Pořadí karet je pořadí v grafu. `index` = sdílený `FrontierIndex`.
    `merged` = karty se sloučeným PR zapsaným do plánu: jako v agent-state (opora_agent_state_dag) už neblokují
    následníka a samy nejsou volné, čekají jen na uzavření člověkem.
    """
    nodes = graph.get('nodes', [])
    sector = next((n for n in nodes if n.get('id') == sector_id), None) if sector_id else {'id': '', 'name': 'Canvas', 'kind': 'sector'}
    if sector is None or sector.get('kind') not in ('sector', 'node'):
        raise ValueError('--node musí být ID sektoru (mapy) v tomto workspace.')
    index = FrontierIndex(graph, state) if index is None else index
    names, done, statuses = index.names, index.done, index.statuses
    siblings = index.children.get(sector_id or None, [])
    cards = [n for n in siblings if n.get('kind') in ('node', 'sector')]
    out = {'map': {'id': sector_id, 'name': sector.get('name', '')}, 'frontier': [], 'claimed': [], 'blocked': [], 'waiting': [], 'closed': [],
           'needsRouting': []}
    for card in cards:
        cid = card['id']
        row = {'id': cid, 'name': card.get('name', ''), 'type': ticket_type(card.get('name'))}
        # Pipeline karty: relace = karta + etapa `current`; karta bez pipeline čeká na router.
        stages = state.get('nodes', {}).get(cid, {}).get('stages')
        if card.get('kind') == 'node':
            row['pipeline'] = pipeline_summary(stages)
        blockers = [source for source in index.incoming.get(cid, ()) if not done.get(source, False) and source not in merged]
        blockers = list(dict.fromkeys([*blockers, *(b['id'] for b in sector_blockers(graph, state, cid, statuses, index.sector_edges(graph)))]))
        claim = claim_of(frames.get(cid, ''))
        if leases is not None:
            lease = leases.get(cid)
            claim = lease['owner'] if lease and lease['active'] else ''
            if lease:
                row['lease'] = lease
        waiting = [{'blockId': b['id'], 'ask': b['state'].get('note') or b['state'].get('condition') or b.get('title', '')}
                   for b in state.get('nodes', {}).get(cid, {}).get('blocks', [])
                   if b.get('state', {}).get('status') == 'blocked']
        waiting += [{'stageId': s['id'], 'ask': f"Pipeline: etapa „{s['title']}“ selhala i po opakováních. {s['note']}".strip()}
                    for s in row.get('pipeline', {}).get('stuck', [])]
        if cid in merged and not done[cid]:
            waiting.append({'ask': 'PR je sloučený a zapsaný do plánu; kartu uzavře člověk.'})
        if not done[cid] and card.get('kind') == 'node' and not row['pipeline']['routed']:
            out['needsRouting'].append({'id': cid, 'name': row['name'], 'type': row['type']})
        if done[cid]:
            out['closed'].append(row)
        elif waiting:
            out['waiting'].append({**row, 'waitingOnHuman': waiting, 'claim': claim,
                                   'blockedBy': [{'id': b, 'name': names.get(b, '')} for b in blockers]})
        elif claim:
            out['claimed'].append({**row, 'claim': claim})
        elif blockers:
            out['blocked'].append({**row, 'blockedBy': [{'id': b, 'name': names.get(b, '')} for b in blockers]})
        else:
            out['frontier'].append(row)
    ids = {sector_id, *(c['id'] for c in cards)}
    out['decisions'] = [{k: d[k] for k in ('id', 'text', 'nodeId', 'pinned', 'by', 'createdAt') if k in d} for d in state.get('decisions', []) if d.get('nodeId') in ids]
    out['fog'] = [{'id': n['id'], 'name': n.get('name', '')} for n in siblings if n.get('kind') == 'comment']
    return redact_deep(out)
