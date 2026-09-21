"""Single-owner local subprocess tasks with durable transitions and bounded output."""
import asyncio
import fcntl
import hashlib
import json
import os
import signal
import sys
from pathlib import Path
from uuid import uuid4
from pydantic import ValidationError

from .claims import verify_claims
from .config import Settings
from .db import connect
from .import_policy import fail, validate_path, MAX_FILE
from .pocketflow_adapter import COMMIT, isolated_environment, stub_command
from .model_config import load_model_config
from .run_models import ACTIVE, STAGES, RunRequest, RecipeRunRequest
from .recipes import REGISTRY
from .isolation import capability, sandbox_command
from .run_store import get_run, now, update_run

MAX_LOG = 256 * 1024
MAX_ARTIFACT = 512 * 1024


def result_cache_key(*, snapshot_id: str, snapshot_revision: str, mode: str, provider: str | None, model: str | None,
                     prompt_version: str | None, language: str, topics: int, scope: str, scenario: str,
                     recipe_id: str | None = None, recipe_version: str | None = None, recipe_parameters: dict | None = None) -> str:
    """Key model/stub output by immutable input plus every output-affecting configuration value."""
    payload = {
        'snapshot_id': snapshot_id, 'snapshot_revision': snapshot_revision, 'mode': mode, 'provider': provider, 'model': model,
        'prompt_version': prompt_version, 'language': language, 'topics': topics, 'scope': scope,
        'scenario': scenario, 'runner_commit': COMMIT,
        'recipe_id': recipe_id, 'recipe_version': recipe_version,
        'recipe_parameters': recipe_parameters,
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()
    return 'sha256:' + hashlib.sha256(encoded).hexdigest()


class Runner:
    def __init__(self, settings: Settings, timeout: float = 180):
        self.settings = settings
        self.timeout = timeout
        self.tasks = {}
        self.processes = {}
        self.lock = None
        self.closing = False
        self.model_loader = load_model_config
        self.real_command = None  # Internal injection seam for network-free M3 regression tests.
        self.configs = {}
        self.recipes = dict(REGISTRY)
        self.execution_recipes = {}

    def recipe_catalog(self):
        configuration = self.configuration()
        isolation = capability()
        items = []
        for recipe in self.recipes.values():
            if not recipe.public:
                continue
            item = recipe.description()
            reasons = []
            if recipe.requires_model and not configuration['real_ready']:
                reasons.append('模型配置不齐全或后台未启用真实运行。')
            if not item['environment']['ready']:
                reasons.append('固定入口或依赖环境尚未就绪。')
            if not isolation['available']:
                reasons.append(isolation['reason'])
            items.append({**item, 'isolation': isolation, 'ready': not reasons, 'unavailable_reasons': reasons})
        return {'items': items}

    def configuration(self):
        try:
            status = self.model_loader().status()
        except (OSError, ValueError):
            status = {'configuration_complete': False, 'api_key_configured': False, 'missing': ['invalid_local_configuration']}
        return {'mode': 'selectable', 'real_enabled': self.settings.real_enabled,
                'real_ready': self.settings.real_enabled and status['configuration_complete'],
                'model': status, 'timeout_seconds': self.timeout, 'real_timeout_seconds': 900,
                'real_scope': 'utils', 'real_language': 'zh', 'real_max_topics': 3}

    def start(self):
        self.lock = (self.settings.data_dir / 'runs' / '.runner.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise RuntimeError('Only one RepoLens backend may own this data directory') from None
        with connect(self.settings.database) as db:
            db.execute("UPDATE runs SET status='interrupted', ended_at=?, error=? WHERE status IN ('queued','running','cancelling')",
                       (now(), '后台已重启，遗留任务已中断；不会自动续跑。'))

    async def close(self):
        self.closing = True
        for run_id in list(self.tasks):
            run = get_run(self.settings.database, run_id)
            if run and run.status in ACTIVE:
                update_run(self.settings.database, run_id, status='interrupted', ended_at=now(), error='后台关闭，任务中断。')
            await self.terminate(run_id)
        if self.tasks:
            await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
        if self.lock:
            self.lock.close()

    def create(self, request: RunRequest):
        recipe = None
        if isinstance(request, RecipeRunRequest):
            recipe = self.recipes.get(request.recipe_id)
            if recipe is None:
                fail('recipe_not_found', '操作配方未登记。', 404)
            try:
                parameters = recipe.parameter_model.model_validate(request.parameters).model_dump()
            except ValidationError:
                fail('recipe_parameter_invalid', '参数类型或取值不符合配方。')
            request = RunRequest(snapshot_id=request.snapshot_id, mode='pocketflow' if recipe.requires_model else 'stub',
                                 scope=parameters.get('scope', '.'), language=parameters.get('language', 'zh'), topics=parameters.get('topics', 3))
        elif request.mode == 'pocketflow':
            recipe = self.recipes['pocketflow-tutorial']
            try:
                parameters = recipe.parameter_model.model_validate({'scope': request.scope, 'language': request.language, 'topics': request.topics}).model_dump()
            except ValidationError:
                fail('recipe_parameter_invalid', '参数类型或取值不符合配方。')
        if self.closing:
            fail('runner_closing', '后台正在关闭，请稍后重试。', 503)
        with connect(self.settings.database) as db:
            snapshot = db.execute('SELECT * FROM snapshots WHERE id = ?', (str(request.snapshot_id),)).fetchone()
            scope = db.execute('SELECT path FROM folder_cards WHERE snapshot_id = ? AND path = ?', (str(request.snapshot_id), request.scope)).fetchone()
        if not snapshot:
            fail('snapshot_not_found', '项目快照不存在。', 404)
        if request.scope != '.':
            validate_path(request.scope)
        if not scope:
            fail('invalid_scope', '分析范围必须是此快照已登记的目录。')
        config = None
        if recipe:
            if recipe.input_commit is not None and snapshot['commit_sha'] != recipe.input_commit:
                fail('recipe_input_unsupported', '此快照不符合配方当前支持的版本。')
            if request.scenario != 'success':
                fail('recipe_parameter_invalid', '配方不接受替身情境参数。')
        if request.mode == 'pocketflow':
            if not self.settings.real_enabled:
                fail('real_run_disabled', '后台未启用真实运行。', 409)
            try:
                config = self.model_loader()
            except (OSError, ValueError):
                fail('model_config_invalid', '本机模型配置不正确，请检查配置文件。', 409)
            if config.missing():
                fail('model_config_missing', '模型配置缺失，请在本机填写 OpenRouter 密钥。', 409)
        if recipe:
            if not capability()['available']:
                fail('isolation_unavailable', 'macOS 沙箱不可用，已拒绝启动真实配方。', 409)
            if not recipe.runtime_ready():
                fail('recipe_runtime_unavailable', '固定入口或依赖环境未就绪。', 409)
        prompt_version = 'folder-responsibility-v1' if config else None
        cache_key = result_cache_key(
            snapshot_id=str(request.snapshot_id), snapshot_revision=snapshot['revision'], mode=request.mode,
            provider=config.provider if config else None, model=config.model if config else None,
            prompt_version=prompt_version, language=request.language, topics=request.topics,
            scope=request.scope, scenario=request.scenario,
            recipe_id=recipe.id if recipe else None, recipe_version=recipe.version if recipe else None,
            recipe_parameters=parameters if recipe else None,
        )
        with connect(self.settings.database) as db:
            cached = db.execute("SELECT id FROM runs WHERE result_cache_key = ? AND status = 'succeeded' ORDER BY ended_at DESC LIMIT 1",
                                (cache_key,)).fetchone()
        if request.mode == 'pocketflow' and cached and self.valid_cached_result(cached['id']):
            return get_run(self.settings.database, cached['id']), True
        with connect(self.settings.database) as db:
            if db.execute("SELECT id FROM runs WHERE status IN ('queued','running','cancelling') LIMIT 1").fetchone():
                fail('runner_busy', '当前已有任务，请完成或取消后再创建。', 409)
        run_id = str(uuid4())
        directory = self.settings.data_dir / 'runs' / run_id
        directory.mkdir()
        (directory / 'run.log').write_text('真实 PocketFlow 任务已创建；失败不自动重试。\n' if config else '替身任务已创建；不会发送模型请求。\n', encoding='utf-8')
        with connect(self.settings.database) as db:
            db.execute('''INSERT INTO runs(id,snapshot_id,mode,status,stage,language,topics,scope,scenario,created_at,upstream_commit,model_provider,model_name,prompt_version,result_cache_key)
                          VALUES (?,?,?,'queued','queued',?,?,?,?,?,?,?,?,?,?)''',
                       (run_id, str(request.snapshot_id), request.mode, request.language, request.topics, request.scope, request.scenario, now(), COMMIT,
                        config.provider if config else None, config.model if config else None, prompt_version, cache_key))
            if recipe:
                db.execute('UPDATE runs SET recipe_id=?,recipe_version=?,parameters_json=?,isolation_kind=? WHERE id=?',
                           (recipe.id, recipe.version, json.dumps(parameters, sort_keys=True), 'macos-seatbelt', run_id))
                self.execution_recipes[run_id] = recipe
        if config:
            self.configs[run_id] = config
        task = asyncio.create_task(self.execute(run_id))
        self.tasks[run_id] = task
        task.add_done_callback(lambda _: self.tasks.pop(run_id, None))
        return get_run(self.settings.database, run_id), False

    def valid_cached_result(self, run_id: str) -> bool:
        base = self.settings.data_dir / 'runs' / run_id / 'output'
        with connect(self.settings.database) as db:
            rows = list(db.execute('SELECT path,size_bytes,sha256 FROM artifacts WHERE run_id = ?', (run_id,)))
        if not rows:
            return False
        for row in rows:
            try:
                validate_path(row['path'])
                path = base / row['path']
                if any(item.is_symlink() for item in [path, *path.parents]) or not path.resolve().is_relative_to(base.resolve()):
                    return False
                raw = path.read_bytes()
            except (OSError, ValueError):
                return False
            if len(raw) != row['size_bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
                return False
        return True

    def prepare_input(self, run):
        destination = self.settings.data_dir / 'runs' / run.id / 'input'
        destination.mkdir()
        with connect(self.settings.database) as db:
            rows = list(db.execute('SELECT * FROM snapshot_files WHERE snapshot_id = ?', (run.snapshot_id,)))
        selected = [r for r in rows if run.scope == '.' or r['path'].startswith(run.scope + '/')]
        if not selected:
            raise ValueError('范围中没有已登记文件。')
        for row in selected:
            validate_path(row['path'])
            target = self.settings.data_dir / 'snapshots' / run.snapshot_id / row['path']
            if any(p.is_symlink() for p in [target, *target.parents]):
                raise ValueError('快照包含链接。')
            with target.open('rb') as stream:
                raw = stream.read(MAX_FILE + 1)
            if len(raw) != row['size_bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('快照内容已变化。')
            relative = row['path'] if run.scope == '.' else row['path'][len(run.scope) + 1:]
            output = destination / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(raw)
        return destination

    async def terminate(self, run_id):
        process = self.processes.get(run_id)
        if process is None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        recipe = self.execution_recipes.get(run_id)
        await asyncio.sleep(recipe.stop_grace_seconds if recipe else 0.2)
        # Escalate the group, including children that ignored SIGTERM.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()

    async def cancel(self, run_id):
        run = get_run(self.settings.database, run_id)
        if run is None:
            fail('run_not_found', '任务不存在。', 404)
        if run.status in ACTIVE:
            update_run(self.settings.database, run_id, status='cancelling')
            await self.terminate(run_id)
            current = get_run(self.settings.database, run_id)
            if current.status in ACTIVE:
                process = self.processes.get(run_id)
                update_run(self.settings.database, run_id, status='cancelled', ended_at=now(),
                           exit_code=process.returncode if process else current.exit_code, error='用户取消了任务。')
        return get_run(self.settings.database, run_id)

    async def execute(self, run_id):
        directory = self.settings.data_dir / 'runs' / run_id
        process = None
        secret = b''
        failure_code = 'snapshot_validation_failed'
        try:
            run = get_run(self.settings.database, run_id)
            if run.status != 'queued':
                return
            update_run(self.settings.database, run_id, status='running', started_at=now(), stage='preparing')
            input_dir = await asyncio.to_thread(self.prepare_input, run)
            if get_run(self.settings.database, run_id).status != 'running':
                return
            config = self.configs.get(run_id)
            recipe = self.execution_recipes.get(run_id)
            if recipe:
                command = (self.real_command(input_dir, directory / 'output', run.language, run.topics) if config and self.real_command
                           else recipe.command_builder(input_dir, directory / 'output', json.loads(run.parameters_json)))
            else:
                command = stub_command(input_dir, directory / 'output', run.language, run.topics, run.scenario)
            if config:
                secret = config.api_key.encode()
            if recipe:
                failure_code = 'isolation_unavailable'
                command = sandbox_command(command, directory, (*recipe.read_paths(), Path(command[3])), network=recipe.network)
            process = await asyncio.create_subprocess_exec(
                sys.executable, '-B', '-u', str(Path(__file__).with_name('run_supervisor.py')), str(os.getpid()), json.dumps(command),
                cwd=directory, env=isolated_environment(directory), stdin=asyncio.subprocess.PIPE if config else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, start_new_session=True,
            )
            self.processes[run_id] = process
            if config:
                metadata = {'model': config.model, 'api_key': config.api_key, 'snapshot_id': run.snapshot_id,
                            'scope': run.scope, 'topics': run.topics, 'commit': COMMIT}
                process.stdin.write(json.dumps(metadata).encode())
                await process.stdin.drain()
                process.stdin.close()
            if get_run(self.settings.database, run_id).status != 'running':
                await self.terminate(run_id)
                return
            failure_code = 'recipe_execution_failed'
            async with asyncio.timeout(recipe.timeout_seconds if recipe else self.timeout):
                with (directory / 'run.log').open('ab') as log:
                    size = log.tell()
                    pending = b''
                    while chunk := await process.stdout.read(4096):
                        size += len(chunk)
                        if size > MAX_LOG:
                            raise ValueError('日志超过上限。')
                        pending += chunk
                        while b'\n' in pending:
                            line, pending = pending.split(b'\n', 1)
                            if secret:
                                line = line.replace(secret, b'[REDACTED]')
                            log.write(line + b'\n'); log.flush()
                            marker = line.decode('utf-8', errors='replace')
                            if marker.startswith('REPOLENS_STAGE:') and marker.split(':', 1)[1] in STAGES:
                                update_run(self.settings.database, run_id, stage=marker.split(':', 1)[1])
                    if pending:
                        log.write(pending.replace(secret, b'[REDACTED]') if secret else pending)
                    code = await process.wait()
            await self.terminate(run_id)
            self.save_usage(run_id, directory, secret)
            current = get_run(self.settings.database, run_id)
            if current.status != 'running':
                return
            if code != 0:
                update_run(self.settings.database, run_id, status='failed', exit_code=code, ended_at=now(), error=f'recipe_exit_nonzero：进程退出码 {code}，未登记成功产物。请查看日志；不会自动重试。')
                return
            failure_code = 'artifact_policy_violation'
            artifacts = self.collect_artifacts(run, directory)
            # No await between status check and terminal commit: cancellation cannot overwrite success or vice versa.
            with connect(self.settings.database) as db:
                db.execute('BEGIN IMMEDIATE')
                try:
                    for artifact in artifacts:
                        db.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)', artifact)
                    db.execute("UPDATE runs SET status='succeeded',stage='complete',ended_at=?,exit_code=0 WHERE id=? AND status='running'", (now(), run_id))
                    db.commit()
                except BaseException:
                    db.rollback(); raise
        except Exception as error:
            await self.terminate(run_id)
            self.save_usage(run_id, directory, secret)
            current = get_run(self.settings.database, run_id)
            if current and current.status == 'running':
                update_run(self.settings.database, run_id, status='failed', ended_at=now(), exit_code=process.returncode if process else None,
                           error=f'{"recipe_timeout" if isinstance(error, TimeoutError) else failure_code}：任务失败，未发布产物。请查看日志。')
        finally:
            # Also clear children that outlived a normally exiting entry point.
            await self.terminate(run_id)
            if process:
                current = get_run(self.settings.database, run_id)
                if current and current.status in ('cancelled', 'cancelling', 'interrupted'):
                    update_run(self.settings.database, run_id, exit_code=process.returncode)
            self.processes.pop(run_id, None)
            self.configs.pop(run_id, None)
            self.execution_recipes.pop(run_id, None)
            self.save_usage(run_id, directory, secret)

    def save_usage(self, run_id, directory, secret):
        usage = directory / 'model-data' / 'usage.json'
        try:
            if usage.is_symlink() or usage.parent.is_symlink() or not usage.is_file() or usage.stat().st_size > MAX_ARTIFACT:
                return
            raw = usage.read_text()
            if secret:
                raw = raw.replace(secret.decode(), '[REDACTED]')
            json.loads(raw)
            update_run(self.settings.database, run_id, model_usage=raw)
        except (ValueError, OSError):
            pass

    def collect_artifacts(self, run, directory):
        root = directory / 'output'
        recipe = self.execution_recipes.get(run.id)
        if root.is_symlink():
            raise ValueError('Artifact root link')
        # Check the entire tree before reading claims or writing verified derivatives.
        for file in root.rglob('*'):
            if file.is_symlink() or not file.resolve().is_relative_to(root.resolve()):
                raise ValueError('Artifact link or escaped path')
            if not file.is_dir() and (not file.is_file() or file.stat().st_nlink != 1):
                raise ValueError('Artifact must be an unlinked regular file')
        for required in recipe.required_artifacts if recipe else ('project/index.md',):
            if not (root / required).is_file():
                raise ValueError('Missing required artifact')
        claims = root / 'project' / 'folder-claims.json'
        if claims.is_file() and not claims.is_symlink() and claims.stat().st_size <= MAX_ARTIFACT:
            result = verify_claims(self.settings, run.snapshot_id, json.loads(claims.read_text()))
            (root / 'project' / 'verified-claims.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        entries = []
        total = 0
        for file in sorted(root.rglob('*')):
            if file.is_symlink():
                raise ValueError('Artifact link')
            if not file.is_file():
                continue
            if not file.resolve().is_relative_to(root.resolve()):
                raise ValueError('Artifact outside output root')
            if file.suffix not in (recipe.artifact_suffixes if recipe else ('.md', '.json')):
                raise ValueError('Undeclared artifact type')
            size = file.stat().st_size
            total += size
            if size > MAX_ARTIFACT or total > 4 * 1024 * 1024 or len(entries) >= 32:
                raise ValueError('Artifact limit')
            raw = file.read_bytes()
            raw.decode('utf-8')
            entries.append((str(uuid4()), run.id, file.relative_to(root).as_posix(), size, hashlib.sha256(raw).hexdigest()))
        return entries
