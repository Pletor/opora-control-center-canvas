"""Observed source pins for native fragment-backed proposals; never approve research claims."""
import json

from backend.editor.research.execution_evidence import imported_pins, original_input
from backend.editor.research.finalization import output_digest


def observe(db, project, workspace, fragments):
    rows = db.execute('SELECT payload FROM research_card_revisions t WHERE project_id=? AND workspace_id=? '
                      'AND revision=(SELECT MAX(revision) FROM research_card_revisions WHERE project_id=t.project_id '
                      'AND workspace_id=t.workspace_id AND id=t.id)', (project, workspace))
    cards = sorted((json.loads(row[0]) for row in rows), key=lambda card: card['id'])
    result = {}
    for node, refs in fragments.items():
        observed = []
        for ref in refs:
            source = ref['fragmentId']
            row = db.execute('SELECT kind,revision FROM brief_fragment_revisions WHERE project_id=? AND workspace_id=? '
                             'AND fragment_id=? ORDER BY revision DESC LIMIT 1', (project, workspace, source)).fetchone()
            if row is None or row[0] != 'research':
                continue
            if row[1] != ref['revision']:
                raise ValueError('Research fragment revision changed; read the original before proposing work.')
            details = db.execute('SELECT revision,fields FROM brief_fragment_details WHERE project_id=? AND workspace_id=? '
                                 'AND fragment_id=? ORDER BY revision DESC LIMIT 1', (project, workspace, source)).fetchone()
            if details is None:
                raise ValueError('Original research details are missing from this workspace.')
            research = json.loads(details[1]).get('research', {})
            linked = [card for card in cards if source in card['refs']['fragmentIds']]
            questions = [card for card in linked if card['kind'] == 'question']
            items = {}
            for linked_card in linked:
                component = imported_pins(db, project, workspace, linked_card['id'], {'cards': cards}, source_fragment=source)
                for item in component['items']:
                    items[item['kind'], item['id']] = item
            observed.append({'sourceId': source, 'sourceRevision': ref['revision'], 'detailsRevision': details[0],
                'assessment': 'observed-unverified', 'runStatus': research.get('status'), 'round': research.get('round'),
                'sourceEvidenceCount': len(research.get('evidence', [])),
                'evidence': {'coverage': 'explicit-fragment-and-mapped-source-components',
                    'originalSourceCoverage': 'semantic-input-and-observed-output-not-completion',
                    'originalInput': original_input(db, project, workspace, source, ref['revision']),
                    'originalOutput': {'id': source, 'detailsRevision': details[0], 'digest': output_digest(research)},
                    'mappedQuestions': [{'id': q['id'], 'revision': q['revision']} for q in questions],
                    'mappedCards': [{'id': card['id'], 'revision': card['revision']} for card in linked],
                    'items': [items[key] for key in sorted(items)]}})
        if observed:
            result[node] = observed
    return result


def validate_shape(value, fragments):
    if not isinstance(value, dict) or not set(value) <= set(fragments):
        raise ValueError('Research fragment evidence target mismatch.')
    for node, records in value.items():
        refs = {ref['fragmentId']: ref['revision'] for ref in fragments[node]}
        if not isinstance(records, list) or not records:
            raise ValueError('Invalid observed research fragment evidence.')
        seen = set()
        for record in records:
            source = record.get('sourceId')
            if (source in seen or refs.get(source) != record.get('sourceRevision')
                    or record.get('assessment') != 'observed-unverified'
                    or type(record.get('detailsRevision')) is not int or record['detailsRevision'] < 1):
                raise ValueError('Research fragment evidence does not match its source reference.')
            seen.add(source)
            evidence = record['evidence']
            if (evidence['originalInput']['id'] != source or evidence['originalOutput']['id'] != source
                    or evidence['originalInput']['fragmentRevision'] != refs[source]
                    or evidence['originalOutput']['detailsRevision'] != record['detailsRevision']):
                raise ValueError('Research fragment evidence source pins differ.')
            for pin in evidence['items']:
                if pin['kind'] not in ('card', 'edge') or type(pin['revision']) is not int or pin['revision'] < 1:
                    raise ValueError('Invalid mapped research revision pin.')
    return value
