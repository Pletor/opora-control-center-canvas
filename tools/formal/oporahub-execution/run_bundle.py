"""Create offline agent-reported verification/report payloads for the fixed TLC profile."""
import argparse
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from tlc_capture import capture
from tlc_profile import CASES, JAR_SHA, artifact, checked_input, classify, sha, verification


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def run(jar, repository, commit, output, mode='all', timeout=900):
    if not re.fullmatch(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', repository) or '..' in repository:
        raise ValueError('Repository must be owner/name.')
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Commit must be 40 lowercase hex characters.')
    if type(timeout) is not int or not 1 <= timeout <= 900 or mode not in {'all', *CASES}:
        raise ValueError('Invalid fixed profile or timeout (1–900 seconds).')
    jar = Path(jar).resolve(strict=True)
    jar_bytes = jar.read_bytes()
    if sha(jar_bytes) != JAR_SHA:
        raise ValueError('Pinned TLC 1.7.4 distribution SHA256 mismatch.')
    java = shutil.which('java')
    if not java:
        raise ValueError('Java is unavailable; no tool installation is performed.')
    source = Path(__file__).resolve().parent
    runner_hashes = {name: sha((source / name).read_bytes()) for name in ('run_bundle.py', 'tlc_capture.py', 'tlc_profile.py')}
    models = {name: checked_input(source, name) for name in ('ExecutionAuthority.tla', *(case[0] for case in CASES.values()))}
    output = Path(output).absolute()
    output.mkdir(parents=False, exist_ok=False)
    # Copy the checked distribution to avoid executing a different file after its hash check.
    pinned = output / 'tla2tools-1.7.4.jar'
    pinned.write_bytes(jar_bytes)
    results = []
    for name, (cfg, _) in CASES.items():
        if mode != 'all' and mode != name:
            continue
        folder = output / name
        folder.mkdir()
        for filename in ('ExecutionAuthority.tla', cfg):
            (folder / filename).write_bytes(models[filename])
        request = verification(repository, commit, models['ExecutionAuthority.tla'], models[cfg], name)
        write_json(folder / 'verification.json', request)
        command = [java, '-XX:+UseParallelGC', '-Xmx768m', '-cp', str(pinned), 'tlc2.TLC', '-workers', '1',
                   '-fp', '0', '-seed', '1', '-config', cfg, '-metadir', str(folder / 'states'), '-coverage', '1', 'ExecutionAuthority.tla']
        started = datetime.now(UTC).isoformat()
        try:
            code, log, reason = capture(command, folder, timeout)
        except OSError as error:
            code, log, reason = -1, str(error).encode('utf-8'), 'runner-launch-failed'
        finished = datetime.now(UTC).isoformat()
        (folder / 'stdout.log').write_bytes(log)
        outcome, summary, checked = classify(name, code, log, reason)
        checked = [claim['id'] for claim in request['claims']] if checked is None else checked
        outputs = [artifact('stdout.log', 'stdout', log)]
        if outcome == 'counterexample':
            (folder / 'counterexample.log').write_bytes(log)
            outputs.append(artifact('counterexample.log', 'counterexample', log))
        manifest = {'profile': name, 'exitCode': code, 'termination': reason, 'outcome': outcome,
                    'startedAt': started, 'finishedAt': finished, 'runnerFiles': runner_hashes,
                    'trust': 'agent-reported', 'independentlyVerified': False, 'timeoutSeconds': timeout,
                    'outputComplete': reason is None, 'distributionSha256': sha(jar_bytes),
                    'inputs': [{k: v for k, v in item.items() if k != 'dataBase64'} for item in request['artifacts']],
                    'outputs': [{k: v for k, v in item.items() if k != 'dataBase64'} for item in outputs],
                    'limitations': ['No hard process-tree, disk or native sandbox guarantee.', 'No Lean adapter or implementation proof.']}
        # Metadata describes input and log bytes, not itself: no self-hash cycle.
        write_json(folder / 'run-metadata.json', manifest)
        outputs.append(artifact('run-metadata.json', 'run-metadata', (folder / 'run-metadata.json').read_bytes()))
        report = {'outcome': outcome, 'checkedClaims': checked, 'summary': summary, 'artifacts': outputs}
        write_json(folder / 'report.json', report)
        manifest = {**manifest, 'outputs': [{k: v for k, v in item.items() if k != 'dataBase64'} for item in outputs]}
        write_json(folder / 'manifest.json', manifest)
        results.append(manifest)
    write_json(output / 'results.json', results)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jar', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--mode', choices=['all', *CASES], default='all')
    parser.add_argument('--timeout-seconds', type=int, default=900)
    args = parser.parse_args()
    results = run(args.jar, args.repository, args.commit, args.output, args.mode, args.timeout_seconds)
    print(json.dumps([{'profile': item['profile'], 'outcome': item['outcome']} for item in results]))
    return 0 if all(item['outcome'] == ('passed' if item['profile'] == 'positive' else 'counterexample') for item in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
