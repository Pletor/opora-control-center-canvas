"""Ohraničený Claude worker s identitou procesu a časovanou telemetrií."""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.llm_runs import _WindowsJob
from backend.node_session_sources import default_process_create_time


def now():
    return datetime.now(UTC).isoformat()


def main():
    spec = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    out = Path(spec['artifacts']); out.mkdir(parents=True, exist_ok=True)
    command = [shutil.which('claude'), '-p', '--model', spec['model'], '--effort', 'high',
               '--max-turns', '36', '--max-budget-usd', '8', '--output-format', 'stream-json',
               '--verbose', '--session-id', spec['sessionId'],
               '--tools', 'Read,Glob,Grep,Edit,Write,Bash', '--allowedTools', 'Read,Glob,Grep,Edit,Write,Bash',
               '--permission-mode', 'acceptEdits', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
               '--setting-sources', '', '--settings', json.dumps({'disableAllHooks': True, 'permissions': {'deny': [
                   'Read(**/.env)', 'Read(**/.env.*)', 'Read(**/auth.json)', 'Read(**/.git-credentials)',
                   'Bash(git push*)', 'Bash(git reset*)', 'Bash(git clean*)', 'Bash(git rebase*)']}})]
    if command[0] is None:
        raise RuntimeError('Claude CLI unavailable')
    state = {'sessionId': spec['sessionId'], 'modelAlias': spec['model'], 'running': False, 'pid': None,
             'pidCreatedAt': None, 'startedAt': now(), 'finishedAt': None, 'localTreeInactive': True,
             'exitCode': None, 'finishReason': None, 'success': None}
    def save():
        temporary = out / 'state.tmp'
        temporary.write_text(json.dumps(state, indent=2), encoding='utf-8')
        temporary.replace(out / 'state.json')
    save()
    job = _WindowsJob(); process = None; result = None; output_limit = threading.Event()
    stream_errors = []
    def consume(stream, path, json_events=False):
        nonlocal result
        written = 0
        try:
            with path.open('wb') as target:
                while True:
                    line = stream.readline(1048577)
                    if not line: break
                    written += len(line)
                    if written > 32 * 1024 * 1024 or len(line) > 1048576:
                        output_limit.set(); break
                    if json_events:
                        try:
                            event = json.loads(line)
                            if isinstance(event, dict):
                                event['_observedAt'] = now()
                                if event.get('type') == 'result': result = event
                                line = (json.dumps(event, ensure_ascii=True) + '\n').encode()
                        except (ValueError, UnicodeError):
                            continue
                    target.write(line); target.flush()
        except (OSError, ValueError, TypeError) as exc:
            stream_errors.append(type(exc).__name__); output_limit.set()
    try:
        with Path(spec['prompt']).open('rb') as prompt:
            process = subprocess.Popen(command, cwd=spec['worktree'], stdin=prompt,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       creationflags=job.CREATE_SUSPENDED | job.CREATE_NO_WINDOW,
                                       env=os.environ.copy())
            try: job.assign_and_resume(process)
            except BaseException:
                process.kill(); process.wait(timeout=10); raise
            created_at = default_process_create_time(process.pid)
            if created_at is None:
                raise RuntimeError('Cannot verify worker process identity')
            state.update(running=True, pid=process.pid, pidCreatedAt=created_at, localTreeInactive=False)
            save()
            readers = [threading.Thread(target=consume, args=(process.stdout, out/'events.jsonl', True)),
                       threading.Thread(target=consume, args=(process.stderr, out/'stderr.log'))]
            for thread in readers: thread.start()
            deadline = time.monotonic() + 900
            reason = 'completed'
            while process.poll() is None:
                if output_limit.is_set(): reason = 'output_limit'; break
                if time.monotonic() >= deadline: reason = 'deadline'; break
                time.sleep(0.5)
            if job.active_processes() and not job.terminate_wait(timeout=10):
                raise RuntimeError('Process tree still active')
            process.wait(timeout=10)
            for thread in readers: thread.join(timeout=10)
            inactive = job.active_processes() == 0
            success = bool(reason == 'completed' and process.returncode == 0 and result and
                           result.get('subtype') == 'success' and not result.get('is_error') and not stream_errors)
            if result: (out/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            state.update(running=False, finishedAt=now(), localTreeInactive=inactive,
                         exitCode=process.returncode, finishReason=reason, success=success)
            save()
            print(json.dumps(state))
            if result: print(str(result.get('result', ''))[-10000:])
            return 0 if success and inactive else 1
    finally:
        if process is not None and process.poll() is None: job.terminate_wait(timeout=10)
        job.close()


if __name__ == '__main__':
    raise SystemExit(main())
