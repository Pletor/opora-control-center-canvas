"""Agreguje jednotlivé read-only zdroje (agent_sources.py) do jednoho katalogu běhů.

Katalog nikdy nevymýšlí pole, která zdroj neposkytuje: chybějící úroveň
'mozku pro LLM' (kontext, verifikace, iterace/rozpočet) se vrací jako honest
'unavailable', ne jako prázdná realizace neexistujícího harness.
"""

_LANE_RE_SAFE_LEN = 64


class UnknownSource(LookupError):
    pass


class AgentCatalog:
    def __init__(self, *, platno=None, orchestrator=None, process=None):
        self.platno = platno
        self.orchestrator = orchestrator
        self.process = process

    def source_health(self):
        out = {}
        if self.process is not None:
            out[self.process.source_id] = self.process.health()
        if self.platno is not None:
            out[self.platno.source_id] = self.platno.health()
        if self.orchestrator is not None:
            if self.orchestrator.is_available():
                out[self.orchestrator.source_id] = {
                    "available": True,
                    "status": "ok",
                    "lanes": self.orchestrator.list_lanes(),
                }
            else:
                out[self.orchestrator.source_id] = {
                    "available": False,
                    "status": "missing",
                    "error": "source_root_missing",
                    "lanes": [],
                }
        return out

    def _orchestrator_runs(self):
        if self.orchestrator is None:
            return []
        runs = []
        for lane in self.orchestrator.list_lanes():
            # Jedna nečitelná nebo mezitím zmizelá lane nesmí zlikvidovat výpis
            # ostatních zdravých zdrojů; vynechá se, místo aby se předstíral běh.
            try:
                run = self._normalize_orchestrator_run(lane)
            except (ValueError, OSError):
                continue
            if run is not None:
                runs.append(run)
        return runs

    def _normalize_orchestrator_run(self, lane):
        detail = self.orchestrator.read_lane(lane)
        if not detail.get("available"):
            return None
        state = detail["state"]
        state_data = state.get("data") if isinstance(state, dict) else None
        events_status = detail.get("eventsStatus", "ok")
        # Nedostupný log událostí se hlásí jako chybějící vstup, ne jako nula událostí.
        missing = ["cost", "contextSnapshot", "verifierArtifact", "iterations", "budget", "doneReasonStructured"]
        if events_status not in ("ok", "missing"):
            missing = ["events", *missing]
        return {
            "sourceId": "hermes-orchestrator",
            "runId": lane,
            "sourceRef": detail["sourceRef"],
            "sessionId": (state_data or {}).get("sessionId"),
            "modelAlias": (state_data or {}).get("modelAlias"),
            "stateOrigin": "state.json+events.jsonl",
            "sourceTimestamp": None,
            "lastEventSeq": detail["lastEventSeq"],
            "eventCounts": detail["eventCounts"],
            "eventsStatus": events_status,
            "eventsReason": detail.get("eventsReason"),
            "truncated": detail["truncated"],
            "status": {
                "reported": "running" if (state_data or {}).get("running") else "stopped",
                "liveness": detail["liveness"]["status"],
                "note": detail["liveness"].get("note"),
            },
            "preview": detail["preview"],
            "result": detail["result"],
            "cost": None,
            "missing": missing,
        }

    def _platno_runs(self):
        if self.platno is None:
            return []
        status = self.platno.status()
        runs = []
        for bucket, reported in (("running", status["running"]), ("waiting", status["waiting"])):
            for item in reported:
                run_id = item.get("run_id") or item.get("id")
                if not isinstance(run_id, str):
                    continue
                runs.append(
                    {
                        "sourceId": self.platno.source_id,
                        "runId": run_id,
                        "sessionId": item.get("session_id") or item.get("worker_session_id"),
                        "stateOrigin": f"platno_status_{bucket}",
                        "sourceTimestamp": status["sourceTimestamp"],
                        "lastEventSeq": None,
                        "status": {"reported": bucket, "liveness": "reported_by_bridge_proxy" if status["bridgeOk"] else "bridge_unavailable"},
                        "preview": [],
                        "cost": status["cost"],
                        "missing": ["events", "contextSnapshot", "verifierArtifact", "iterations", "budget"],
                    }
                )
        return runs

    def list_runs(self, *, source_id=None, limit=20, cursor=0):
        all_runs = []
        if self.process is not None and source_id in (None, self.process.source_id):
            all_runs.extend(self.process.list_runs())
        if source_id is None or (self.orchestrator and source_id == self.orchestrator.source_id):
            all_runs.extend(self._orchestrator_runs())
        if source_id is None or (self.platno and source_id == self.platno.source_id):
            all_runs.extend(self._platno_runs())
        seen = set()
        deduped = []
        for run in all_runs:
            key = (run["sourceId"], run["runId"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(run)
        limit = min(max(1, limit), 100)
        start = max(0, cursor)
        page = deduped[start : start + limit]
        next_cursor = start + limit if start + limit < len(deduped) else None
        return {"items": page, "nextCursor": next_cursor, "total": len(deduped)}

    def run_detail(self, source_id, run_id):
        if self.process is not None and source_id == self.process.source_id:
            return self.process.run_detail(run_id)
        if self.orchestrator is not None and source_id == self.orchestrator.source_id:
            detail = self.orchestrator.read_lane(run_id)
            run = self._normalize_orchestrator_run(run_id)
            if run is None:
                return {"sourceId": source_id, "runId": run_id, "available": False,
                        "error": detail.get("error") or "run_not_found"}
            run["brain"] = {
                "promptSpec": "unavailable",
                "contextSnapshot": "unavailable",
                "toolAction": run["preview"][-1] if run["preview"] else None,
                "verifierArtifact": "unavailable",
                "iterations": "unavailable",
                "maxIterations": "unavailable",
                "budget": "unavailable",
                "noProgressSignal": "unavailable",
                "doneReason": (detail.get("result") or {}).get("subtype") if detail.get("result") else None,
            }
            return run
        if self.platno is not None and source_id == self.platno.source_id:
            for run in self._platno_runs():
                if run["runId"] == run_id:
                    run["brain"] = {
                        "promptSpec": "unavailable",
                        "contextSnapshot": "unavailable",
                        "toolAction": "unavailable",
                        "verifierArtifact": "unavailable",
                        "iterations": "unavailable",
                        "maxIterations": "unavailable",
                        "budget": "unavailable",
                        "noProgressSignal": "unavailable",
                        "doneReason": None,
                    }
                    return run
            return {"sourceId": source_id, "runId": run_id, "available": False, "error": "run_not_found"}
        raise UnknownSource(source_id)
