"""Native SiteAdmin review remains visible and usable without forged human authority."""
from urllib.parse import parse_qs, urlparse
from backend.api.brain_opora.test_canvas_capability_routes import setup, call
from backend.project.site_admin import store, proposals


def test_atomic_bundle_and_staged_attachment_read_native_scope_and_limits(setup, monkeypatch):
    import base64
    import hashlib
    from backend.project.site_admin.test_store import SVG, b64
    from backend.project.site_admin import proposal_attachments
    client, service, auth = setup
    before = store.read(service, 'draft')
    data = {'expectedRevision': before['revision'], 'changes': {'title': 'Atomic bundle'},
            'attachments': [{'kind': 'asset', 'op': 'put', 'group': 'Logos', 'name': 'bundle.svg', 'data': b64(SVG)}]}
    response = call(client, auth, 'site_admin_routes.proposal_create', data, 'bundle')
    assert response.status_code == 200, response.text
    result = response.json()
    record = result['result']
    assert record['document']['title'] == 'Atomic bundle' and record['attachments'][0]['sha256'] == hashlib.sha256(SVG).hexdigest()
    assert store.read(service, 'draft') == before
    assert call(client, auth, 'site_admin_routes.proposal_create', data, 'bundle').json() == result
    assert call(client, auth, 'site_admin_routes.proposal_create', {**data, 'expectedRevision': 999}, 'stale-bundle').status_code == 409
    read = {'proposal_id': record['id'], 'index': 0}
    path = '/api/site-admin/proposals/' + record['id'] + '/attachments/0'
    actual = call(client, auth, 'site_admin_routes.proposal_attachment', read)
    native = client.get(path, params={'project': 'draft'}, headers=auth)
    assert actual.status_code == native.status_code == 200
    assert base64.b64decode(actual.json()['result']['data']) == native.content == SVG
    assert actual.json()['result']['sha256'] == native.headers['X-Content-SHA256']
    assert call(client, auth, 'site_admin_routes.proposal_attachment', read, scope={'project': 'foreign', 'workspace': 'draft'}).status_code == 403
    assert call(client, auth, 'site_admin_routes.proposal_attachment', {**read, 'index': -1}).status_code == 404
    assert call(client, auth, 'site_admin_routes.proposal_attachment', {**read, 'index': True}).status_code == 422
    monkeypatch.setattr(proposal_attachments, 'BUNDLE_BYTES', len(SVG)-1)
    refused = call(client, auth, 'site_admin_routes.proposal_attachment', read)
    direct = client.get(path, params={'project': 'draft'}, headers=auth)
    assert refused.status_code == direct.status_code and refused.status_code >= 400


def test_site_write_prepares_native_proposal_with_cas_and_human_review(setup):
    client, service, auth = setup
    before = store.read(service, 'draft')
    data = {'expectedRevision': before['revision'], 'changes': {'title': 'Proposed site'}, 'note': 'Review title'}
    first = call(client, auth, 'site_admin_routes.proposal_create', data, 'site-proposal')
    assert first.status_code == 200, first.text
    result = first.json()
    assert result['state'] == 'awaiting_human' and not result['applied'] and result['verified']
    proposal = result['result']
    assert proposal in proposals.pending(service, 'draft') and proposal['document']['title'] == 'Proposed site'
    assert store.read(service, 'draft') == before
    assert call(client, auth, 'site_admin_routes.proposal_create', data, 'site-proposal').json() == result
    assert call(client, auth, 'site_admin_routes.proposal_create', {**data, 'note': 'Changed'}, 'site-proposal').status_code == 409
    for decision in ('accept', 'reject'):
        review = call(client, auth, 'site_admin_routes.proposal_' + decision, {'proposal_id': proposal['id']})
        assert review.status_code == 200 and review.json()['requestedDecision'] == decision
        assert review.json()['proposal'] == proposal and not review.json()['applied']
        query = parse_qs(urlparse(review.json()['url']).query)
        assert query['projectView'] == ['site'] and query['environment'] == ['project']
        assert store.read(service, 'draft') == before
    # A full document save becomes a real replacement proposal using native normalization.
    payload = {'expectedRevision': before['revision'], 'document': {**before, 'title': 'Full document proposal'}}
    saved = call(client, auth, 'site_admin_routes.site_admin_save', payload, 'site-full')
    assert saved.status_code == 200 and saved.json()['result']['document']['title'] == 'Full document proposal', saved.text
    assert store.read(service, 'draft') == before
    assert len(proposals.pending(service, 'draft')) == 1  # Native supersession semantics.
    stale = call(client, auth, 'site_admin_routes.site_admin_save', {**payload, 'expectedRevision': 99}, 'stale')
    assert stale.status_code == 409
    assert call(client, auth, 'site_admin_routes.proposal_accept', {'proposal_id': proposal['id']}).status_code == 409


def test_native_site_binary_reads_preserve_bytes_and_export_without_path_escape(setup):
    import base64
    import hashlib
    import io
    import zipfile
    from backend.project.site_admin.test_store import SVG, WOFF2, b64
    client, service, auth = setup
    store.put_asset(service, 'draft', 'Logos', 'mark.svg', b64(SVG))
    store.put_font(service, 'draft', 'inter.woff2', b64(WOFF2))  # Explicit fixture, not catalog write.
    for capability, data, expected in (
        ('asset_file', {'group': 'Logos', 'name': 'mark.svg'}, SVG),
        ('font_file', {'name': 'inter.woff2'}, WOFF2),
    ):
        response = call(client, auth, 'site_admin_routes.' + capability, data)
        assert response.status_code == 200, response.text
        result = response.json()['result']
        assert base64.b64decode(result['data']) == expected
        assert result['size'] == len(expected) and result['sha256'] == hashlib.sha256(expected).hexdigest()
    archive = call(client, auth, 'site_admin_routes.site_admin_export').json()['result']
    content = base64.b64decode(archive['data'])
    assert archive['sha256'] == hashlib.sha256(content).hexdigest()
    with zipfile.ZipFile(io.BytesIO(content)) as exported:
        assert exported.read('design/assets/Logos/mark.svg') == SVG
        assert exported.read('design/fonts/inter.woff2') == WOFF2
        assert 'design/tokens.json' in exported.namelist()
    assert call(client, auth, 'site_admin_routes.asset_file', {'group': '..', 'name': 'mark.svg'}).status_code == 422
    assert call(client, auth, 'site_admin_routes.font_file', {'name': '../inter.woff2'}).status_code == 422
    assert call(client, auth, 'site_admin_routes.font_file', {'name': 'absent.woff2'}).status_code == 404


def test_asset_font_operations_stage_native_immutable_review_without_live_writes(setup):
    import hashlib
    from backend.project.site_admin.test_store import SVG, WOFF2, b64
    from backend.project.site_admin import proposal_attachments
    client, service, auth = setup
    revision = store.read(service, 'draft')['revision']
    for kind, name, raw in (('asset', 'mark.svg', SVG), ('font', 'inter.woff2', WOFF2)):
        extra = {'group': 'Logos'} if kind == 'asset' else {}
        data = {'expectedRevision': revision, 'name': name, 'data': b64(raw), **extra}
        operation = 'site_admin_routes.'+kind+'_upload'
        response = call(client, auth, operation, data, kind+'-upload')
        assert response.status_code == 200, response.text
        saved = response.json()
        assert saved['state'] == 'awaiting_human' and not saved['applied']
        record = saved['result']
        assert record['status'] == 'pending-attachments'
        attachment = record['attachments'][0]
        assert attachment['sha256'] == hashlib.sha256(raw).hexdigest() and 'data' not in attachment
        assert proposal_attachments.blob(service, 'draft', attachment['sha256']) == raw
        assert call(client, auth, operation, data, kind+'-upload').json() == saved
        assert call(client, auth, operation, {**data, 'note': 'different'}, kind+'-upload').status_code == 409
        read = call(client, auth, 'site_admin_routes.'+kind+'_file', {'name': name, **extra})
        assert read.status_code == 404
        # Only explicit human fixture acceptance applies the staged bytes.
        proposals.accept(service, 'draft', record['id'], revision)
        revision = store.read(service, 'draft')['revision']
        assert call(client, auth, 'site_admin_routes.'+kind+'_file', {'name': name, **extra}).status_code == 200
        delete = {'expectedRevision': revision, 'name': name, **extra}
        pending = call(client, auth, 'site_admin_routes.'+kind+'_delete', delete, kind+'-delete')
        assert pending.status_code == 200, pending.text
        assert pending.json()['result']['attachments'][0]['baseDigest'] == hashlib.sha256(raw).hexdigest()
        assert call(client, auth, 'site_admin_routes.'+kind+'_file', {'name': name, **extra}).status_code == 200
        assert store.read(service, 'draft')['revision'] == revision
        assert call(client, auth, 'site_admin_routes.proposal_accept', {'proposal_id': pending.json()['result']['id']}).json()['state'] == 'awaiting_human'
