"""Testy nikdy nespouštějí worker automatické aktualizace map (ten by volal Graphify a Sonnet).

Fronta se v testech řídí ručně přes `claim()` a `run_one()`; viz docs/mapy-projektu.md.
"""
import os

os.environ['OPORA_MAP_REFRESH_WORKER'] = '0'
# Smyčku uzavření běhů (PR → merge) testy řídí ručně přes run_once(); nikdy nečte GitHub sama.
os.environ['OPORA_EXECUTION_PR_WORKER'] = '0'
# Auto-rebase smyčku testy řídí ručně přes run_once() (docs/oporahub-auto-rebase.md).
os.environ['OPORA_AUTO_REBASE_WORKER'] = '0'
os.environ['OPORA_HARNESS_MEMORY_WORKER'] = '0'
# Strážce testy řídí ručně přes run_once(now) s falešným časem (docs/strazci.md).
os.environ['OPORA_GUARDS_WORKER'] = '0'
# Srdce mozku (docs/brain-heart.md) testy nikdy nespouští: žádný proces `claude`, plánovač srdce řídí test ručně.
os.environ['OPORA_HEART'] = 'off'
# Sdílené hodnoty cache čtení (karta P3) se nesmí měnit na místě: v testech to hlídá otisk
# hodnoty při každém čtení z cache (backend/canvas/read_cache.py).
os.environ['OPORA_READ_CACHE_GUARD'] = '1'

# Testovací klient hraje lidské UI (upgrade-opora #29): server bere za člověka jen požadavek
# s relačním dokladem `opora_ui`. Pevné tajemství dostane každá aplikace z prostředí a každý
# TestClient nese jeho cookie, takže testy zápisů za člověka fungují jako v prohlížeči.
# Agent se dál hlásí hlavičkou `X-Opora-Actor` (ta má přednost) a test „bez dokladu“ cookie smaže.
TEST_UI_SECRET = 'test-ui-secret-' + 'x' * 24
os.environ['OPORA_UI_SECRET'] = TEST_UI_SECRET

from starlette.testclient import TestClient

_init = TestClient.__init__


def _as_human_ui(self, *args, **kwargs):
    _init(self, *args, **kwargs)
    self.cookies.set('opora_ui', TEST_UI_SECRET)


TestClient.__init__ = _as_human_ui


import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "plan_steps_claim: claim readiness also requires accepted plan steps")


@pytest.fixture(autouse=True)
def _legacy_claims_without_plan_steps(request, monkeypatch):
    """Execution suites written before plan steps claim cards whose accepted spec has no steps.

    The claim endpoint refuses such cards (docs/oporahub-plan-steps.md); only tests marked
    `plan_steps_claim` enforce that half, the blockedBy half always applies."""
    if request.node.get_closest_marker("plan_steps_claim") is None:
        from backend.canvas import opora_agent_state_steps
        monkeypatch.setattr(opora_agent_state_steps, "REQUIRE_STEPS", False)


@pytest.fixture
def real_graphify(monkeypatch):
    """Interpret s graphifyy==0.9.24 nalezený stejně jako spouštěč `uv run opora`.

    Spouštěč (tools/opora.py) bere `[integrations] graphify_python` z opora.toml + opora.local.toml
    a předá ho backendu jako OPORA_GRAPHIFY_PYTHON; pytest ty soubory sám nečte. Proměnná
    z prostředí má přednost. Bez interpretu se test výslovně přeskočí, nikdy tiše neprojde."""
    from backend.project.maps import graphify_runtime
    from backend.project.maps.map_artifacts import ArtifactUnavailable
    from tools.opora import ENV_BY_KEY, load_config

    if not os.environ.get('OPORA_GRAPHIFY_PYTHON'):
        configured = load_config().get('integrations', {}).get('graphify_python')
        if configured:
            monkeypatch.setenv(ENV_BY_KEY['graphify_python'], str(configured))
    graphify_runtime.runtime.cache_clear()
    try:
        interpreter = graphify_runtime.runtime()
    except ArtifactUnavailable as exc:
        graphify_runtime.runtime.cache_clear()
        pytest.skip(f'Původní Graphify není k dispozici: {exc} '
                    '(graphify_python v opora.local.toml nebo OPORA_GRAPHIFY_PYTHON).')
    yield interpreter
    graphify_runtime.runtime.cache_clear()
