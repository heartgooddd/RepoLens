"""Explicit local OpenRouter configuration; never include credentials in repr/status."""
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import ROOT

DEFAULT_MODEL = 'deepseek/deepseek-v4-flash'
DEFAULT_FILE = ROOT / 'server' / '.env'
BASE_URL = 'https://openrouter.ai/api'
FIELDS = ('LLM_PROVIDER', 'OPENROUTER_MODEL', 'OPENROUTER_BASE_URL', 'OPENROUTER_API_KEY')


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    base_url: str
    api_key: str = field(repr=False)

    def missing(self) -> list[str]:
        return [key for key, value in zip(FIELDS, (self.provider, self.model, self.base_url, self.api_key)) if not value.strip()]

    def status(self) -> dict:
        return {'provider': self.provider, 'model': self.model, 'api_key_configured': bool(self.api_key),
                'configuration_complete': not self.missing(), 'missing': self.missing(),
                'authentication_verified': False}


def load_model_config(path: Path = DEFAULT_FILE, environ=None) -> ModelConfig:
    # Small KEY=value format. No shell execution, interpolation, or implicit global dotenv lookup.
    values = {}
    if path.is_file():
        if path.stat().st_size > 16384:
            raise ValueError('本机模型配置文件超过 16 KiB。')
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, separator, value = line.partition('=')
            key = key.strip()
            if key not in FIELDS:
                continue
            if not separator or key in values:
                raise ValueError('模型配置字段重复或格式不正确。')
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            values[key] = value
    environment = os.environ if environ is None else environ
    for key in FIELDS:
        if key in environment:
            values[key] = environment[key].strip()
    config = ModelConfig(values.get('LLM_PROVIDER', 'OPENROUTER'),
                         values.get('OPENROUTER_MODEL', DEFAULT_MODEL),
                         values.get('OPENROUTER_BASE_URL', BASE_URL),
                         values.get('OPENROUTER_API_KEY', ''))
    if config.provider != 'OPENROUTER':
        raise ValueError('当前检查器只支持显式选择 OPENROUTER。')
    if config.base_url != BASE_URL:
        raise ValueError('OpenRouter 地址必须为 https://openrouter.ai/api（不带 /v1）。')
    if not re.fullmatch(r'[a-zA-Z0-9._-]+/[a-zA-Z0-9._:-]+', config.model):
        raise ValueError('模型 ID 格式不正确。')
    if config.api_key and (not config.api_key.startswith('sk-or-') or any(c.isspace() for c in config.api_key)):
        raise ValueError('OpenRouter 密钥格式不正确，请在本机配置文件中检查。')
    return config
