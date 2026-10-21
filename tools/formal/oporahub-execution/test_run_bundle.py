"""Finite-profile evidence, bounded child process and offline artifact regression tests."""
import base64
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_bundle
import tlc_profile
from tlc_capture import capture, clean_environment

SUCCESS = b'Model checking completed. No error has been found.\n0 states left on queue.\nFinished in 01s'


@pytest.mark.parametrize(('code', 'log', 'reason', 'outcome'), [
    (0, SUCCESS, None, 'passed'),
    (0, b'No error has been found.', None, 'inconclusive'),
    (12, SUCCESS, None, 'failed'),
    (0, SUCCESS, 'wall-timeout', 'inconclusive'),
    (0, SUCCESS, 'output-limit', 'inconclusive'),
    (0, SUCCESS + b'\nError: failure', None, 'inconclusive'),
    (0, SUCCESS.replace(b'0 states left', b'10 states left'), None, 'inconclusive'),
    (0, SUCCESS.replace(b'0 states left', b'100 states left'), None, 'inconclusive'),
    (0, b'Running Random Simulation\n' + SUCCESS, None, 'inconclusive'),
])
def test_positive_requires_complete_evidence(code, log, reason, outcome):
    assert tlc_profile.classify('positive', code, log, reason)[0] == outcome


@pytest.mark.parametrize(('mode', 'invariant'), [('negative', 'OneActiveOwner'), ('stale-negative', 'NoStaleEpochReceipt')])
def test_mutants_are_counterexamples_not_passes(mode, invariant):
    log = f'Error: Invariant {invariant} is violated.\nState 1: Initial\nFinished in 00s'.encode()
    assert tlc_profile.classify(mode, 12, log)[:1] == ('counterexample',)
    assert tlc_profile.classify(mode, 0, log)[0] != 'counterexample'
    assert tlc_profile.classify(mode, 12, log.replace(invariant.encode(), b'Other'))[0] == 'failed'
    assert tlc_profile.classify(mode, 0, SUCCESS)[0] == 'inconclusive'


def test_profile_claims_are_exact_definitions():
    source = Path(__file__).parent
    model = tlc_profile.checked_input(source, 'ExecutionAuthority.tla')
    cfg = tlc_profile.checked_input(source, 'ExecutionAuthority.cfg')
    claims = tlc_profile.claims(model, cfg)
    assert [item['id'] for item in claims] == ['TypeOK', 'OneActiveOwner', 'NoUnauthorizedReceipt', 'OneReceiptPerExecution', 'Idempotency', 'MonotonicEpoch']
    for item in claims:
        assert item['statement'] in model.decode()
        assert item['statement'].startswith(item['id'] + ' ==')
    assert claims[-1]['statement'] == "MonotonicEpoch == [][epoch' >= epoch]_vars"


def test_profile_mutation_fails_closed(tmp_path):
    (tmp_path / 'ExecutionAuthority.cfg').write_bytes(b'INVARIANT Invented')
    with pytest.raises(ValueError, match='hash mismatch'):
        tlc_profile.checked_input(tmp_path, 'ExecutionAuthority.cfg')


def test_jar_hash_rejected_before_creating_output(tmp_path):
    jar = tmp_path / 'bad.jar'
    jar.write_bytes(b'not TLC')
    with pytest.raises(ValueError, match='SHA256 mismatch'):
        run_bundle.run(jar, 'owner/repo', 'a' * 40, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_capture_timeout_and_overflow(tmp_path):
    code, log, reason = capture([sys.executable, '-c', 'import time; print("started",flush=True); time.sleep(10)'], tmp_path, .15)
    assert code != 0 and reason == 'wall-timeout'
    code, log, reason = capture([sys.executable, '-c', 'import sys; sys.stdout.write("x"*100000); sys.stdout.flush()'], tmp_path, 3, limit=1000)
    assert len(log) == 1000 and reason.startswith('output-limit')


def test_clean_java_environment(monkeypatch):
    for name in ('JAVA_TOOL_OPTIONS', '_JAVA_OPTIONS', 'JDK_JAVA_OPTIONS', 'CLASSPATH'):
        monkeypatch.setenv(name, 'hostile')
        assert name not in clean_environment()


def test_bundle_exact_bytes_and_no_token_payload(tmp_path, monkeypatch):
    jar = tmp_path / 'tool.jar'
    jar.write_bytes(b'test distribution')
    monkeypatch.setattr(run_bundle, 'JAR_SHA', tlc_profile.sha(jar.read_bytes()))
    monkeypatch.setattr(run_bundle.shutil, 'which', lambda name: '/fixed/java')
    captured = []

    def fake(command, folder, timeout):
        captured.append(command)
        return 0, SUCCESS, None

    monkeypatch.setattr(run_bundle, 'capture', fake)
    output = tmp_path / 'out'
    run_bundle.run(jar, 'owner/repo', 'a' * 40, output, 'positive', 10)
    request = json.loads((output / 'positive/verification.json').read_text())
    report = json.loads((output / 'positive/report.json').read_text())
    assert set(request) == {'tool', 'source', 'claims', 'assumptions', 'configuration', 'artifacts'}
    assert set(report) == {'outcome', 'checkedClaims', 'summary', 'artifacts'}
    assert report['checkedClaims'] == [item['id'] for item in request['claims']]
    for item in request['artifacts'] + report['artifacts']:
        data = base64.b64decode(item['dataBase64'])
        assert tlc_profile.sha(data) == item['sha256']
        assert (output / 'positive' / item['path']).read_bytes() == data
    assert captured[0][0] == '/fixed/java' and captured[0][-1] == 'ExecutionAuthority.tla'
    metadata_item = next(item for item in report['artifacts'] if item['role'] == 'run-metadata')
    metadata = json.loads(base64.b64decode(metadata_item['dataBase64']))
    assert datetime.fromisoformat(metadata['startedAt']) <= datetime.fromisoformat(metadata['finishedAt'])
    assert datetime.fromisoformat(metadata['startedAt']).utcoffset().total_seconds() == 0
    assert metadata['exitCode'] == 0 and metadata['termination'] is None
    assert metadata['timeoutSeconds'] == 10 and metadata['outputComplete'] is True
    assert metadata['trust'] == 'agent-reported' and metadata['independentlyVerified'] is False
    assert not any(item['path'] == 'run-metadata.json' for item in metadata['outputs'])
    for filename, digest in metadata['runnerFiles'].items():
        assert tlc_profile.sha((Path(__file__).parent / filename).read_bytes()) == digest
    assert (output / 'tla2tools-1.7.4.jar').read_bytes() == jar.read_bytes()
    with pytest.raises(FileExistsError):
        run_bundle.run(jar, 'owner/repo', 'a' * 40, output, 'positive', 10)


def test_json_rejects_nonfinite(tmp_path):
    with pytest.raises(ValueError):
        run_bundle.write_json(tmp_path / 'bad.json', {'bad': float('nan')})
