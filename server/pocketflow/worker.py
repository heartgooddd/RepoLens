"""Invoke the unchanged, pinned main.py with bounded calls and one attempt per node."""
import json
from pathlib import Path
import runpy
import sys

SERVER = Path(__file__).resolve().parents[1]
ROOT = SERVER.parent
UPSTREAM = ROOT / 'upstream' / 'pocketflow-codebase-knowledge'
sys.path.insert(0, str(SERVER))

from app.bounded_llm import ModelFailure, ModelSession
from app.model_config import ModelConfig

STAGES = ('FetchRepo', 'IdentifyAbstractions', 'AnalyzeRelationships', 'OrderChapters', 'WriteChapters', 'CombineTutorial')


def run(metadata, arguments):
    # Config travels over stdin, never in argv, a credential file, or inherited shell env.
    config = ModelConfig('OPENROUTER', metadata['model'], 'https://openrouter.ai/api', metadata['api_key'])
    session = ModelSession(config, Path.cwd() / 'model-data', metadata['topics'] + 4)
    sys.path.insert(0, str(UPSTREAM))
    import nodes
    for name in STAGES:
        cls = getattr(nodes, name)
        original = cls.prep
        def prep(self, shared, stage=name, delegate=original):
            self.max_retries, self.wait = 1, 0
            session.stage = stage
            print('REPOLENS_STAGE:' + stage, flush=True)
            return delegate(self, shared)
        cls.prep = prep

    def bounded_call(prompt, use_cache=False):
        # Upstream says "top 5-3" when max-abstractions=3. Correct only this known instruction.
        prompt = prompt.replace(f'Identify the top 5-{metadata["topics"]} core',
                                f'Identify between 1 and {metadata["topics"]} core')
        return session(prompt, use_cache=False)
    nodes.call_llm = bounded_call
    original_post = nodes.IdentifyAbstractions.post
    def checked_post(self, shared, prep_res, exec_res):
        if not 1 <= len(exec_res) <= metadata['topics']:
            raise ModelFailure('abstraction_limit')
        return original_post(self, shared, prep_res, exec_res)
    nodes.IdentifyAbstractions.post = checked_post

    sys.argv = [str(UPSTREAM / 'main.py'), *arguments]
    try:
        runpy.run_path(str(UPSTREAM / 'main.py'), run_name='__main__')
        input_dir = Path(arguments[arguments.index('--dir') + 1])
        output = Path(arguments[arguments.index('--output') + 1]) / 'project'
        session.stage = 'FolderResponsibilities'
        print('REPOLENS_STAGE:FolderResponsibilities', flush=True)
        prompt = (SERVER / 'app/prompts/folder-responsibility-v1.md').read_text()
        evidence = []
        for file in sorted(input_dir.rglob('*')):
            if file.is_file():
                path = metadata['scope'] + '/' + file.relative_to(input_dir).as_posix()
                evidence.append({'file_path': path, 'lines': [{'line': i, 'text': line} for i, line in enumerate(file.read_text().splitlines(), 1)]})
        answer = session(prompt + '\n仅解释 utils 目录，中文，最多3条职责。只输出JSON。\n' +
                         json.dumps({'snapshot_id': metadata['snapshot_id'], 'folder_path': metadata['scope'], 'files': evidence}, ensure_ascii=False))
        try:
            if answer.strip().startswith('```'):
                answer = answer.strip().split('\n', 1)[1].rsplit('```', 1)[0]
            claims = json.loads(answer)
            if not isinstance(claims, dict) or not isinstance(claims.get('claims'), list) or not claims['claims']:
                raise ValueError('Invalid claims')
        except (ValueError, TypeError):
            claims = {'claims': [{'folder_path': metadata['scope'], 'description': '模型职责输出无法解析，待核实。', 'references': []}]}
        (output / 'folder-claims.json').write_text(json.dumps(claims, ensure_ascii=False), encoding='utf-8')
        index = output / 'index.md'
        index.write_text(index.read_text().replace('**Source Repository:** [None](None)',
            f'**来源快照：** `{metadata["snapshot_id"]}` · `{metadata["scope"]}` · Commit `{metadata["commit"]}`'), encoding='utf-8')
        (output / 'model-usage.json').write_text(json.dumps(session.summary(), ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        session.client.close()


def main():
    try:
        metadata = json.loads(sys.stdin.read(16384))
        run(metadata, sys.argv[1:])
    except ModelFailure as error:
        print('REPOLENS_ERROR:' + str(error), flush=True)
        return 1
    except Exception as error:
        # No raw exceptions: upstream validation errors may include provider content.
        print('REPOLENS_ERROR:worker_' + type(error).__name__, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
