import json
import joblib
import httpx
import pytest
from backend.app.config import Settings, settings
from backend.app.llm import LLMRouter, Diagnosis
from backend.app.monitor import Monitor


class ExportedModelStub:
    def predict(self, x):
        assert list(x.columns) == ['Water Flow 1', 'Pressure 1 Out']
        return [1]


def test_joblib_loading_without_training(test_root):
    path = test_root / 'monitor.joblib'
    joblib.dump({'model': ExportedModelStub(), 'features': ['Water Flow 1', 'Pressure 1 Out'],
        'class_map': {'1': 'leak'}, 'version': 'adapter-test'}, path)
    try:
        m = Monitor()
        assert m.status()['connected']
        assert m.predict({'Water Flow 1': 2.2, 'Pressure 1 Out': 0.4}) == {'classification': 'leak', 'score': None, 'model_version': 'adapter-test'}
        assert m.predict({'Water Flow 1': 2.2})['classification'] == 'review'
        joblib.dump({'model': ExportedModelStub(), 'features': ['Labels'], 'class_map': {'1': 'leak'}}, path)
        assert not m.reload()['connected']
        assert 'prohibited' in m.status()['error']
    finally:
        path.unlink(missing_ok=True)


FALLBACK = {'classification': 'review', 'priority': 'medium', 'summary': 'The supplied sensor window needs an operator review.',
    'evidence': ['Water Flow 1 latest 2.2 in original sensor units.'], 'recommended_action': 'Verify instrument operation before inspecting the water system.'}


@pytest.mark.parametrize('gemini_valid', [True, False])
def test_provider_fallback_validates_json_and_never_returns_credentials(monkeypatch, gemini_valid):
    calls = []
    original_client = httpx.Client
    def handler(request):
        calls.append(request.url.host)
        if request.url.host == 'api.groq.com':
            return httpx.Response(503, json={'error': 'service unavailable'})
        if 'googleapis' in request.url.host:
            content = json.dumps(FALLBACK) if gemini_valid else '{"classification":"invented"}'
            return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': content}]}}]})
        return httpx.Response(200, json={'message': {'content': json.dumps(FALLBACK)}})
    monkeypatch.setattr('backend.app.llm.httpx.Client', lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    config = Settings(_env_file=None, groq_api_key='test-groq-secret', gemini_api_key='test-gemini-secret')
    result, provider, failures = LLMRouter(config).structured('Review', {'monitor': {'connected': False}}, Diagnosis, FALLBACK)
    assert provider == ('gemini' if gemini_valid else 'ollama')
    assert len(calls) == (2 if gemini_valid else 3)
    assert result == FALLBACK
    assert 'secret' not in str(failures)


def test_all_providers_unavailable_uses_visible_evidence_only_fallback(monkeypatch):
    original_client = httpx.Client
    def handler(request):
        raise httpx.ConnectError('unavailable', request=request)
    monkeypatch.setattr('backend.app.llm.httpx.Client', lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    result, provider, failures = LLMRouter(Settings(_env_file=None)).structured('Review', {}, Diagnosis, FALLBACK)
    assert provider == 'evidence_only'
    assert failures == ['ollama: ConnectError']
    assert result == FALLBACK


def test_unverified_units_are_rejected():
    with pytest.raises(ValueError, match='unverified'):
        Diagnosis.model_validate({**FALLBACK, 'summary': 'The pressure is normal at 5.0 bar.'})
