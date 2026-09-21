"""Isolated backend for browser tests. No writes to the development database."""
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from app.config import ROOT, Settings
from app.main import create_app
from app.model_config import ModelConfig, DEFAULT_MODEL, BASE_URL
from app.pocketflow_adapter import worker_command

parent = ROOT / 'var' / 'tests'
parent.mkdir(parents=True, exist_ok=True)
with TemporaryDirectory(prefix='browser-', dir=parent) as directory:
    app = create_app(Settings(Path(directory), real_enabled=True))
    # Test server only: the fixture replaces HTTP with MockTransport and blocks other HTTP sends.
    app.state.runner.model_loader = lambda: ModelConfig('OPENROUTER', 'fixture/offline-no-model-request', BASE_URL, 'FAKE_BROWSER_FIXTURE_KEY')
    recipe = app.state.runner.recipes['pocketflow-tutorial']
    app.state.runner.recipes[recipe.id] = replace(recipe, verification='测试服务：固定 PocketFlow 入口＋离线模型响应；未发送真实模型请求')
    def offline_command(input_dir, output_dir, language, topics):
        command = worker_command(input_dir, output_dir, language, topics)
        return [*command[:3], str(ROOT / 'server/tests/pocketflow_fixture_worker.py'), 'success', *command[4:]]
    app.state.runner.real_command = offline_command
    uvicorn.run(app, host='127.0.0.1', port=8001)
