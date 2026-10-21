"""Allowlisted finite model profile; no caller-provided model or Java arguments."""
import base64
import hashlib
import re

JAR_SHA = '936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88'
INPUT_SHA = {
    'ExecutionAuthority.tla': 'd9893a4a25eeb2ea86d3264d01801cdea5b19a73698d0cba1f2af33a9722d3f5',
    'ExecutionAuthority.cfg': 'e8bea279eed9a99ea838484d28d33b684f574ae8243e3aa2df88ed0d34410a7b',
    'NoFence.cfg': '6c8fb0290bc20c96d858bc818c2e90c66102ccf1115467c8ce49b1fd2efb3696',
    'NoEpochReceipt.cfg': '7a86ddaefc782e3182a7e9e1c748dc6421b01fab65d0ccc5a642540a5e3f08e3',
}
CASES = {'positive': ('ExecutionAuthority.cfg', None), 'negative': ('NoFence.cfg', 'OneActiveOwner'),
         'stale-negative': ('NoEpochReceipt.cfg', 'NoStaleEpochReceipt')}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def artifact(path, role, data):
    return {'path': path, 'role': role, 'sha256': sha(data), 'dataBase64': base64.b64encode(data).decode('ascii')}


def checked_input(directory, name):
    path = directory / name
    if path.is_symlink():
        raise ValueError('Profile symlinks are not allowed.')
    data = path.read_bytes()
    if sha(data.replace(b'\r\n', b'\n')) != INPUT_SHA[name]:
        raise ValueError('Bundled profile hash mismatch: ' + name)
    return data


def claims(model, config):
    text, cfg = model.decode('utf-8'), config.decode('utf-8')
    invariant = re.search(r'^INVARIANTS (.+)$', cfg, re.MULTILINE).group(1).split()
    temporal = re.search(r'^PROPERTY (.+)$', cfg, re.MULTILINE).group(1).split()
    result = []
    for name in invariant + temporal:
        match = re.search(r'^' + re.escape(name) + r' == .*?(?=^\w+.*? ==|^=+\s*$|\Z)', text, re.MULTILINE | re.DOTALL)
        if not match:
            raise ValueError('Configured claim missing from exact model.')
        result.append({'id': name, 'kind': 'invariant' if name in invariant else 'temporal-property',
                       'statement': match.group(0).strip()})
    return result


def verification(repository, commit, model, config, name):
    return {'tool': {'name': 'tlc', 'version': 'TLC 2.19 (distribution 1.7.4)', 'distributionSha256': JAR_SHA},
            'source': {'repository': repository, 'commitSha': commit}, 'claims': claims(model, config),
            'assumptions': ['Finite abstract execution authority, not a refinement proof of Python or TypeScript.',
                            'TLC standard modules are provided by the pinned distribution.',
                            'No fairness assumption; deadlock checking is explicitly disabled.',
                            'Repository and commit are caller-reported provenance, not independently verified.'],
            'configuration': {'profile': name, 'mode': 'exhaustive-model-checking', 'workers': 1, 'seed': 1, 'fingerprint': 0,
                              'bounds': {'owners': 2, 'claimIds': 2, 'requestIds': 1, 'payloads': 2, 'maxEpoch': 2,
                                         'maxTime': 2, 'ttl': [1, 2], 'revision': [0, 1], 'context': [0, 1]},
                              'fairness': [], 'axioms': [], 'checkDeadlock': False, 'enforceFence': name == 'positive',
                              'trust': 'agent-reported', 'independentlyVerified': False},
            'artifacts': [artifact('ExecutionAuthority.tla', 'model', model), artifact(CASES[name][0], 'configuration', config)]}


def classify(name, code, output, reason=None):
    if reason:
        return 'inconclusive', reason, []
    text = output.decode('utf-8', errors='replace')
    if re.search(r'\bsimulation\b', text, re.IGNORECASE):
        return 'inconclusive', 'Simulation does not exhaust the finite model.', []
    expected = CASES[name][1]
    if expected and code == 12 and f'Error: Invariant {expected} is violated.' in text and 'State 1:' in text and 'Finished in ' in text:
        return 'counterexample', 'Expected negative sensitivity example; never a passing proof.', [expected]
    empty_queue = re.search(r'(?:^|,\s*)0 states left on queue\.[ \t]*\r?$', text, re.MULTILINE)
    if name == 'positive' and code == 0 and 'Model checking completed. No error has been found.' in text and empty_queue and 'Finished in ' in text and 'Error:' not in text:
        return 'passed', 'Exhausted this finite model only; no implementation proof or independent trust.', None
    return ('failed' if code else 'inconclusive'), 'Unexpected exit or incomplete model-checking evidence.', []
