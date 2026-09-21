"""One bounded OpenRouter smoke request. Default invocation only checks local config."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .config import ROOT
from .model_config import DEFAULT_FILE, load_model_config


def smoke_check(config, client: httpx.Client) -> dict:
    if config.missing():
        return {'status': 'blocked', 'reason': 'missing_configuration', **config.status()}
    # Synthetic source only. No repository files, model fallback, or automatic retry.
    payload = {'model': config.model, 'messages': [
        {'role': 'user', 'content': '请用中文一句话解释此代码，只说明可直接看到的行为，不推测业务用途：\ndef add(a, b):\n    return a + b'}],
        'max_tokens': 256, 'temperature': 0, 'reasoning': {'enabled': False},
        'provider': {'sort': 'price', 'allow_fallbacks': False, 'require_parameters': True,
                     'max_price': {'prompt': 0.10, 'completion': 0.25}}}
    try:
        response = client.post(config.base_url + '/v1/chat/completions', json=payload,
                               headers={'Authorization': 'Bearer ' + config.api_key})
        if response.status_code != 200:
            # Never echo remote error bodies/headers: they can reflect input or credentials.
            reasons = {401: 'authentication_failed', 402: 'insufficient_credits', 403: 'access_denied',
                       404: 'model_or_route_unavailable', 429: 'rate_limited'}
            return {'status': 'failed', 'http_status': response.status_code,
                    'reason': reasons.get(response.status_code, 'provider_error'), 'retry_performed': False}
        data = response.json()
        choice = data['choices'][0]
        content = choice['message']['content']
        if not isinstance(content, str) or not content.strip():
            raise ValueError('Empty content')
        usage = data.get('usage', {})
        report = {'status': 'passed' if choice.get('finish_reason') == 'stop' else 'incomplete',
                  'requested_model': config.model, 'returned_model': data.get('model'),
                  'finish_reason': choice.get('finish_reason'), 'response': content[:2000],
                  'usage': {key: usage.get(key) for key in ('prompt_tokens','completion_tokens','total_tokens','cost')},
                  'retry_performed': False, 'synthetic_input': True}
        # Defensive redaction even for an unexpected server response.
        return json.loads(json.dumps(report, ensure_ascii=False).replace(config.api_key, '[REDACTED]'))
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        return {'status': 'failed', 'reason': 'network_or_invalid_response', 'retry_performed': False}


def main():
    parser = argparse.ArgumentParser(description='本机 OpenRouter 配置检查；--smoke 仅发送一次受限测试请求。')
    parser.add_argument('--env-file', type=Path, default=DEFAULT_FILE)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    try:
        config = load_model_config(args.env_file)
    except (OSError, ValueError):
        print(json.dumps({'status':'blocked','reason':'invalid_local_configuration'}, ensure_ascii=False))
        return 2
    report = {'status': 'ready' if not config.missing() else 'blocked', **config.status()}
    if args.smoke:
        with httpx.Client(timeout=30, trust_env=False, follow_redirects=False) as client:
            report = smoke_check(config, client)
        report['checked_at'] = datetime.now(timezone.utc).isoformat()
        directory = ROOT / 'var' / 'model-checks'
        directory.mkdir(parents=True, exist_ok=True)
        report_path = directory / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] in ('ready', 'passed') else 2


if __name__ == '__main__':
    raise SystemExit(main())
