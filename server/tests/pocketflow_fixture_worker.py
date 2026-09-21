"""Network-free subprocess fixture: runs pinned PocketFlow with mock HTTP responses."""
import json
from pathlib import Path
import sys
import time

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))
import httpx
from app import bounded_llm
from app.bounded_llm import ModelFailure

scenario = sys.argv.pop(1)
# Fail closed even if the adapter stops accepting the injected client.
def blocked(*args, **kwargs):
    raise AssertionError('Network forbidden in PocketFlow fixture')
original_send = httpx.Client.send
httpx.Client.send = blocked
OriginalSession = bounded_llm.ModelSession


class FixtureSession(OriginalSession):
    def __init__(self, config, directory, max_calls, client=None):
        def respond(request):
            if scenario == 'failure':
                return httpx.Response(401, json={'error': {'message': config.api_key}})
            if scenario == 'slow':
                time.sleep(30)
            if self.stage == 'IdentifyAbstractions':
                if scenario == 'too_many':
                    text = '```yaml\n' + ''.join(f'- name: 主题{i}\n  description: 测试\n  file_indices: [0]\n' for i in range(4)) + '```'
                else:
                    text = '```yaml\n- name: 辅助函数\n  description: 固定测试说明\n  file_indices: [0]\n```'
            elif self.stage == 'AnalyzeRelationships':
                text = '```yaml\nsummary: 固定测试概要\nrelationships: []\n```'
            elif self.stage == 'OrderChapters':
                text = '```yaml\n- 0\n```'
            elif self.stage == 'WriteChapters':
                text = '# 辅助函数\n\n固定网络替身章节，不是真实模型。'
            elif self.stage == 'FolderResponsibilities':
                text = json.dumps({'claims':[{'folder_path':'utils','description':'固定推断','references':[{'file_path':'utils/helper.py','line_start':1,'line_end':2,'quote':'def helper():\n    pass'}]}]})
            else:
                raise AssertionError('Unexpected stage')
            return httpx.Response(200, json={'model':config.model,'choices':[{'finish_reason':'stop','message':{'content':text}}], 'usage':{'prompt_tokens':10,'completion_tokens':10,'total_tokens':20,'cost':0}})
        # MockTransport bypasses httpx.Client.send override explicitly for this instance.
        client = httpx.Client(transport=httpx.MockTransport(respond))
        client.send = original_send.__get__(client, httpx.Client)
        super().__init__(config, directory, max_calls, client=client)


bounded_llm.ModelSession = FixtureSession
import runpy
runpy.run_path(str(SERVER / 'pocketflow/worker.py'), run_name='__main__')
