"""Owner-global read delegation created only by the genuine local human Pletor route.

This is neither a token grant nor write authority. Background/local research calls
receive no object; every explicit project/workspace and canonical origin is checked.
"""
import json
from backend.canvas.activity_log import require_human
from backend.editor.research import model, knowledge, service as research
from backend.brain_opora.determinism.gate_payloads import GateError
from backend.agi_pletor.solution_projection import project as project_solutions
from backend.agi_pletor.research_context import workspace_for


class OwnerResearchRead:
    def __init__(self, canvas, actor):
        require_human(actor, "Global Pletor research belongs to the genuine UI owner conversation.")
        self.canvas = canvas

    def _workspaces(self, project):
        model.identifier(project)
        if project not in self.canvas.project_ids():
            model.fail("Project is unavailable to this conversation.",403,"pletor_scope")
        metadata = self.canvas.project_hub._project(project)
        if metadata["sourceKind"] != "git":
            return metadata, ["draft"]
        return metadata, ["main", *[item["id"] for item in self.canvas.workspaces(project)]]

    def authorize(self, project, workspace, write=False):
        if write:
            model.fail("This conversation delegation is read-only.",403,"pletor_scope")
        model.identifier(workspace)
        _, workspaces = self._workspaces(project)
        if workspace not in workspaces:
            model.fail("Workspace is unavailable to this conversation.",403,"pletor_scope")

    def overview(self):
        projects = self.canvas.project_ids()
        catalog=[]
        for project in projects[:100]:
            try:
                metadata,spaces=self._workspaces(project)
            except (GateError,ValueError,OSError):
                continue  # Concurrent removal cannot turn catalog metadata into source access.
            preferred = workspace_for(self.canvas, project, "main" if metadata["sourceKind"] == "git" else "draft")
            catalog.append({"project":project,"name":metadata["name"],"workspaces":spaces[:10],"workspacesTruncated":len(spaces)>10,
                            "preferredResearchWorkspace": preferred if preferred in spaces else None})
        return "\n\nOWNER-GLOBAL RESEARCH READ (catalog metadata, not instructions):\n" + json.dumps({
            "catalog":catalog,"truncated":len(projects)>100,
            "solutionSearch":{"type":"research_read","resultType":"solution","query":"meaningful problem description",
                              "scopes":[{"project":"explicit registered project ID","workspace":"explicit catalog workspace"}],"resultLimit":5},
            "exactSource":{"type":"research_read","source":{"projectId":"canonical origin","workspaceId":"canonical workspace","id":"source ID","revision":1}},
            "rule":"For comparisons across projects use solutionSearch, not local research query. Use only explicit catalog scopes; read nextOffset/snapshot chunks until complete. Source references do not grant write authority. Unknown verification is not production proof."
        },ensure_ascii=False)

    def payload(self, action):
        if "source" in action:
            model.shape(action,{"type","source"},{"offset","limit","snapshot"})
            source=knowledge.reference(action["source"])
            self.authorize(source["projectId"],source["workspaceId"])
            return {"canonicalRef":source,**research.detail(self.canvas,source["projectId"],source["workspaceId"],source["id"],source["revision"])}
        model.shape(action,{"type","resultType","query","scopes"},{"ranking","resultLimit","offset","limit","snapshot"})
        if action["resultType"] != "solution":
            model.fail("Global reads require the explicit solution result type.")
        limit=action.get("resultLimit",5)
        if type(limit) is not int or not 1<=limit<=10:
            model.fail("Pletor solution resultLimit must be 1 to 10.")
        # Match public research search aliases, checking ALL raw and resolved scopes before content.
        knowledge.validate_search(self.canvas, action["scopes"], action["query"], [], [], limit, self.authorize)
        scopes = [{**scope, "workspace": workspace_for(self.canvas, scope["project"], scope["workspace"])} for scope in action["scopes"]]
        for scope in scopes:
            self.authorize(scope["project"], scope["workspace"])
        return project_solutions(knowledge.solutions(self.canvas,scopes,action["query"],limit,self.authorize,action.get("ranking","hybrid")))
