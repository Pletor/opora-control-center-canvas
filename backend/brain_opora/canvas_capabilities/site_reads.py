"""Scoped design documents use the same native store and compilers as the UI."""
import base64
import hashlib
from backend.project.site_admin.export import export_zip
from backend.project.site_admin import compile as compiled, proposals, store, proposal_attachments
from backend.project.site_admin.summary import summary
from backend.api.project.site_admin_routes import _errors
from backend.brain_opora.canvas_capabilities.contracts import contract

NAMES = ("site_admin_view", "tokens_css", "components_css", "tokens_json", "readme", "site_admin_summary", "proposal_list")
CONTRACTS = {"site_admin_routes." + name: contract() for name in NAMES}

CONTRACTS.update({
    "site_admin_routes.proposal_attachment": contract(("proposal_id", "index"), types={"index": "integer"},
        output="Immutable scoped staged attachment bytes, native size bounds and verified SHA256"),
    "site_admin_routes.asset_file": contract(("group", "name"), output="Native file bytes as base64, mediaType, size and SHA256"),
    "site_admin_routes.font_file": contract(("name",), output="Native font bytes as base64, mediaType, size and SHA256"),
    "site_admin_routes.site_admin_export": contract(output="Native design ZIP as base64, revision, size and SHA256"),
})
for _name in ("asset_file", "font_file", "site_admin_export", "proposal_attachment"):
    CONTRACTS["site_admin_routes." + _name]["test"] = "backend/api/brain_opora/test_canvas_capability_site.py"

def read(service, project, capability, data=None):
    data = data or {}
    def native():
        if capability == 'site_admin_routes.proposal_attachment':
            with service.lock_for(project):
                item, raw = proposal_attachments.content(service, project, data['proposal_id'], data['index'])
                return {'encoding': 'base64', 'data': base64.b64encode(raw).decode('ascii'),
                        'mediaType': 'application/octet-stream', 'name': item['name'], 'size': len(raw),
                        'sha256': hashlib.sha256(raw).hexdigest()}
        if capability in ('site_admin_routes.asset_file', 'site_admin_routes.font_file', 'site_admin_routes.site_admin_export'):
            with service.lock_for(project):
                extra = {}
                if capability.endswith('site_admin_export'):
                    revision, content = export_zip(service, project)
                    media, extra = 'application/zip', {'revision': revision, 'name': 'design.zip'}
                else:
                    path, media = store.asset_path(service, project, data['group'], data['name']) if capability.endswith('asset_file') else store.font_path(service, project, data['name'])
                    content = path.read_bytes()
                return {'encoding': 'base64', 'data': base64.b64encode(content).decode('ascii'),
                        'mediaType': media, 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(), **extra}
        if capability == "site_admin_routes.proposal_list":
            return {"proposals": [{k: v for k, v in item.items() if k != "document"}
                                  for item in proposals.pending(service, project)]}
        document = store.read(service, project)
        if capability == "site_admin_routes.site_admin_view":
            return {"revision": document["revision"], "document": document}
        if capability == "site_admin_routes.site_admin_summary":
            return {**summary(document), "pendingProposals": len(proposals.pending(service, project))}
        compilers = {"site_admin_routes.tokens_css": compiled.tokens_css,
                     "site_admin_routes.components_css": compiled.components_css,
                     "site_admin_routes.tokens_json": compiled.tokens_json,
                     "site_admin_routes.readme": compiled.readme}
        return compilers[capability](document)
    return _errors(native)
