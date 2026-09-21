import json

import httpx
import pytest

from app.model_check import smoke_check
from app.model_config import BASE_URL, DEFAULT_MODEL, ModelConfig, load_model_config

KEY = 'sk-or-v1-FAKE_UNIT_TEST_ONLY'


def test_local_config_and_environment_precedence_without_secret_status(tmp_path):
    path = tmp_path / '.env'
    path.write_text(f'LLM_PROVIDER=OPENROUTER\nOPENROUTER_MODEL={DEFAULT_MODEL}\nOPENROUTER_API_KEY="{KEY}"\n')
    config = load_model_config(path, {})
    assert config.api_key == KEY and config.missing() == []
    assert KEY not in repr(config) and KEY not in json.dumps(config.status())
    assert config.base_url == BASE_URL
    override = load_model_config(path, {'OPENROUTER_API_KEY': ''})
    assert override.missing() == ['OPENROUTER_API_KEY']


def test_missing_key_makes_no_network_request(tmp_path):
    config = load_model_config(tmp_path / 'absent', {})
    def reject(_):
        pytest.fail('Missing configuration must not make an HTTP request')
    with httpx.Client(transport=httpx.MockTransport(reject)) as client:
        result = smoke_check(config, client)
    assert result['status'] == 'blocked' and result['missing'] == ['OPENROUTER_API_KEY']


@pytest.mark.parametrize('value', ['https://example.com/api', 'https://openrouter.ai/api/v1'])
def test_reject_untrusted_or_duplicate_version_endpoint(tmp_path, value):
    with pytest.raises(ValueError):
        load_model_config(tmp_path / 'absent', {'OPENROUTER_BASE_URL': value})


def test_single_bounded_request_returns_usage_and_redacts_key():
    calls = []
    def respond(request):
        calls.append(request)
        assert str(request.url) == 'https://openrouter.ai/api/v1/chat/completions'
        assert request.headers['authorization'] == 'Bearer ' + KEY
        payload = json.loads(request.content)
        assert payload['max_tokens'] == 256
        assert payload['provider']['allow_fallbacks'] is False
        assert payload['provider']['max_price'] == {'prompt': 0.1, 'completion': 0.25}
        assert payload['model'] == DEFAULT_MODEL and 'def add' in payload['messages'][0]['content']
        return httpx.Response(200, json={'model':DEFAULT_MODEL, 'choices':[{'finish_reason':'stop','message':{'content':'测试结果 '+KEY}}], 'usage':{'prompt_tokens':50,'completion_tokens':20,'cost':0.00001}})
    config = ModelConfig('OPENROUTER', DEFAULT_MODEL, BASE_URL, KEY)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = smoke_check(config, client)
    assert len(calls) == 1 and result['status'] == 'passed'
    assert result['usage']['cost'] == 0.00001 and KEY not in json.dumps(result)


@pytest.mark.parametrize('status,reason', [(401,'authentication_failed'),(402,'insufficient_credits'),(429,'rate_limited'),(503,'provider_error')])
def test_failure_not_retried_and_remote_errors_not_echoed(status, reason):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(status, text='remote error contains '+KEY)
    config = ModelConfig('OPENROUTER', DEFAULT_MODEL, BASE_URL, KEY)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = smoke_check(config, client)
    assert result['reason'] == reason and len(calls) == 1
    assert KEY not in json.dumps(result) and result['retry_performed'] is False
