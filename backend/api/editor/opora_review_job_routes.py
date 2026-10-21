"""Automated code review job API (docs/oporahub-review-jobs.md): worker leases, findings, merge gates."""
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from backend.canvas.opora_review_findings import FindingMissing, HumanRequired, ReviewFindings
from backend.canvas.opora_review_gate import read_review_gates
from backend.canvas.opora_review_job_tasks import ReviewTasks
from backend.canvas.opora_review_jobs import ReviewJobsDisabled, ReviewJobService

SCOPE = {"min_length": 1, "max_length": 64}


def create_review_job_router(service, jobs=None):
    router = APIRouter(prefix="/api/oporahub/review-jobs", tags=["oporahub"])
    jobs = jobs or ReviewJobService(service)
    tasks, findings = ReviewTasks(jobs), ReviewFindings(jobs)

    def call(request, action):
        if request.state.actor not in ("human", "agent"):
            return JSONResponse({"error": "Review identity is required.", "code": "identity_required"}, status_code=428)
        try:
            return action()
        except ReviewJobsDisabled as exc:
            return JSONResponse({"error": str(exc), "code": "review_jobs_disabled"}, status_code=409)
        except FindingMissing as exc:
            return JSONResponse({"error": str(exc), "code": "finding_not_found"}, status_code=404)
        except HumanRequired as exc:
            return JSONResponse({"error": str(exc), "code": "human_required"}, status_code=403)
        except ValueError as exc:
            return JSONResponse({"error": str(exc), "code": "review_conflict"}, status_code=409)

    def owner(request):
        name = getattr(request.state, "agent", None)
        if request.state.actor == "agent" and (not isinstance(name, str) or not name.strip()):
            raise ValueError("An identified review worker is required.")
        return "agent:" + name if request.state.actor == "agent" else "human"

    @router.get("")
    def listing(request: Request, project: str = Query(**SCOPE), workspace: str = Query(**SCOPE)):
        return call(request, lambda: jobs.list(project, workspace))

    @router.get("/gates")
    def gates(request: Request, project: str = Query(**SCOPE), workspace: str = Query(**SCOPE)):
        def read():
            items = read_review_gates(service, project, workspace, jobs.config())
            if items is None:
                raise ReviewJobsDisabled("Automated code review is not enabled.")
            return {"items": items}
        return call(request, read)

    @router.post("/sync")
    def sync(payload: dict, request: Request):
        def run():
            if set(payload) != {"project", "workspace"}:
                raise ValueError("Invalid review sync fields.")
            return {"created": jobs.sync(payload["project"], payload["workspace"])}
        return call(request, run)

    @router.post("/claim")
    def claim(payload: dict, request: Request):
        return call(request, lambda: tasks.claim(payload, owner(request)))

    @router.post("/{job}/tasks/{task}/heartbeat")
    def heartbeat(job: str, task: str, payload: dict, request: Request):
        return call(request, lambda: tasks.heartbeat(job, task, payload))

    @router.post("/{job}/tasks/{task}/release")
    def release(job: str, task: str, payload: dict, request: Request):
        return call(request, lambda: tasks.release(job, task, payload))

    @router.post("/{job}/tasks/{task}/submit")
    def submit(job: str, task: str, payload: dict, request: Request):
        return call(request, lambda: tasks.submit(job, task, payload))

    @router.post("/findings/{finding}/resolve")
    def resolve(finding: str, payload: dict, request: Request):
        return call(request, lambda: findings.resolve(finding, payload, request.state.actor))

    @router.post("/decisions")
    def decide(payload: dict, request: Request):
        return call(request, lambda: findings.decide(payload, request.state.actor))

    return router
