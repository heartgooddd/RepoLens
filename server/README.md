# RepoLens 后台：真实仓库地图、GitHub 导入与任务服务

步骤4–8已完成：SQLite、受限目录／公开GitHub导入、静态扫描、源码读取、持久化任务和受控OpenRouter运行。GitHub导入先固定Commit再读取受限归档；远程源码不会执行。默认仍为无模型替身，显式开启后可选择已登记的真实模式。

## 环境与安装

本机验证：macOS Apple Silicon、Python **3.14.6**、SQLite **3.53.3**（Python 标准库所链接的版本）。使用 Python 3.14；其他 Python 版本尚未验收。FastAPI **0.141.1**、Uvicorn **0.53.0**、Pydantic **2.13.5**；测试用 pytest **9.1.1**、HTTPX **0.28.1**。直接依赖列在 `requirements.in`，完整依赖精确版本保存在 `requirements.lock`。

所有以下命令在 **server/** 执行。初次安装：

```bash
cd '/Users/Vibe coding/AI_product/AI Program/RepoLens/server'
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip check
```

已有 `.venv` 时直接使用，不需要重新创建，也不影响上游 PocketFlow 的环境。锁文件是本次完整安装环境的 `pip freeze`，不包含包哈希；升级时在独立环境解析 `requirements.in`，检查差异并重跑验证后更新锁文件。

## 迁移与启动

```bash
.venv/bin/python -m app.migrate
REPOLENS_ENABLE_REAL_RUN=1 .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- 后台：http://127.0.0.1:8000/api/health
- 可交互接口文档：http://127.0.0.1:8000/docs
- 机器可读字段定义：http://127.0.0.1:8000/openapi.json
- `Ctrl+C` 停止；再运行同一条 Uvicorn 命令即重启，数据仍使用同一文件。
- 每次启动在 FastAPI lifespan 中自动执行迁移；手动迁移用于检查或部署准备。已有版本不会重新执行。端口占用会报错，先核对占用进程。
- 仅监听本机回环地址。当前是无认证的本地单用户服务，不用于公开部署。CORS 仅允许本机 localhost / 127.0.0.1 的 5173、5174、4173、8000 端口；导入和任务写请求还会校验 Origin；创建请求必须 JSON Content-Type。前端通过 Vite 同源 `/api` 代理接入。

## 数据位置

默认路径由代码位置确定，与启动终端所在目录无关：

```text
RepoLens/var/
├── repolens.sqlite3             元数据与迁移历史
├── snapshots/<snapshot-id>/     已保存的源码快照
├── runs/<run-id>/               已保存的运行输入、日志和产物
└── tests/m2-*/                  自动验证的隔离数据，测试结束自动清理
```

每次成功导入建立独立快照目录并写 SQLite。测试在独立目录中导入本地 PocketFlow 或合成源码，不污染默认数据库；`tests/serve_e2e.py` 为浏览器测试在 8001 端口创建临时数据库。任务目录保存已登记快照的输入副本、日志、模型用量和对应模式的输出。

可通过环境变量 `REPOLENS_DATA_DIR` 指定**绝对**数据目录，数据库始终命名为 `repolens.sqlite3`；省略则使用根目录 `var/`。`.env.example` 是无密钥模板。数据目录和真实开关由进程环境读取；仅模型配置器显式读取 `server/.env` 的四个模型字段，不执行 shell 或通用 dotenv。不要将数据目录指向受 Git 跟踪的源码目录。项目标签是展示名称，不应存密钥或本机绝对路径。

`var/`、`.venv/`、缓存均被根目录 `.gitignore` 排除；迁移代码和依赖锁文件被跟踪。本地 Git 提交不备份数据库或快照。需要备份时先停服务，复制整个 `var/`，恢复时使用与数据库迁移版本匹配的代码。

## 模块与数据结构

| 位置 | 职责 |
|---|---|
| `app/main.py` | 生命周期、健康检查、导入、列表、详情与源码接口 |
| `app/importer.py`、`scanner.py` | 固定 Git 版本读取、上传校验、快照保存和静态证据提取 |
| `app/github_importer.py` | GitHub URL规范化、Commit解析、受限归档、进度任务和源码快照复用 |
| `app/import_policy.py`、`request_limits.py` | 排除规则、路径和体积边界、读取请求体前的上限 |
| `app/source.py` | 已登记文件的哈希校验与源码分段返回 |
| `app/models.py` | Pydantic 接口字段、路径和关联校验 |
| `app/repository.py` | 事务写入与读取；导入器的保存入口 |
| `app/db.py`、`app/migrate.py` | SQLite 连接、迁移执行器及 CLI |
| `migrations/001_repository_metadata.sql` | 初始表、索引、外键与约束 |
| `migrations/002_snapshot_files.sql` | 文件清单与名称推断字段，保留旧数据 |
| `migrations/003_runs.sql`、`004_run_model.sql` | 任务、产物与模型用量元数据 |
| `migrations/005_github_cache.sql` | GitHub来源／快照缓存、导入任务和模型结果缓存键 |
| `app/runner.py`、`bounded_llm.py`、`pocketflow/worker.py` | 固定入口、生命周期、受控模型调用与上游适配 |
| `tests/` | HTTP 合约、持久化、迁移及真实进程重启验证 |

关系：`projects → snapshots → folder_cards → evidence_refs`。`github_sources`按规范仓库关联项目，`github_snapshot_cache`按仓库和Commit唯一关联快照；`runs.result_cache_key`独立标识模型结果配置。源码缓存与运行产物不共用键。每个快照中的目录路径唯一；`snapshot_files`保存路径、字节数和SHA-256。

`create_project(database, ProjectDetail)` 是内部 Python 保存入口，一次事务写入完整聚合；不覆盖已有 ID，失败则全部回滚。导入器先验证所有内容，再复制到 UUID 快照目录，最后调用此入口；普通异常会清理失败快照，进程硬中断可能留下未登记的孤立目录，不会自动删除。

### 后续迁移规则

1. 后续从 `006_<name>.sql` 开始新增连续版本，版本连续；不要修改已执行的迁移。
2. 每条完整 SQL 语句以分号结束，最后一条结束后不添加独立注释；一行不写多条语句。不要在文件中写 `BEGIN/COMMIT/ROLLBACK`、`VACUUM` 等自行控制事务的语句。
3. 执行器在一个 `BEGIN IMMEDIATE` 事务中核对版本与 SHA-256、执行待应用的 SQL 并写 `schema_migrations`。SQL 或校验失败会回滚并阻止服务启动；不会删库重建。
4. 修改过的历史迁移、缺失版本、比代码新的数据库会被拒绝；恢复匹配代码或补充正确迁移。当前不提供自动降级。
5. `.venv/bin/python -m app.migrate` 可重复运行；新迁移要添加已有数据升级与失败回滚测试。

实现参考：[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)、[Python sqlite3 事务与连接](https://docs.python.org/3/library/sqlite3.html)。连接按操作打开并关闭，启用外键、10 秒锁等待，使用参数绑定；迁移避免 `executescript` 的隐式提交行为。

## API 请求与响应

共同约定：本地服务不要求密钥。导入、创建任务和取消任务使用 POST，其余端点为 GET。ID 为 UUID 字符串；时间为带 `Z` 的 UTC ISO 8601 字符串；路径用 `/`，根目录是 `.`。响应不返回本机绝对路径或直接读取源码内容。详细模型与必填字段同步生成在 `/openapi.json`。

### `GET /api/health`

无参数。实际读取迁移表和项目表，成功 `200`：

```json
{"status":"ok","database":"ok","schema_version":5}
```

数据库不可用返回 `503 {"detail":"Database unavailable"}`。启动迁移失败时服务不进入就绪状态。此接口检查元数据库可读，不代表源码文件存在或模型可运行。

### `GET /api/projects?limit=20&offset=0`

查询字段：`limit` 默认 20，范围 1–100；`offset` 默认 0，必须 ≥ 0。按 `created_at DESC, id DESC` 稳定排序。

```json
{"items":[],"total":0,"limit":20,"offset":0}
```

`items` 中每项包含下方 Project 的全部字段及 `snapshot_count: integer`；`total` 是所有项目数量，不是当前页长度。非法参数返回 `422`。

### `GET /api/projects/{project_id}`

路径参数 `project_id` 为 UUID。成功 `200` 返回：

```text
{
  project: Project,
  snapshots: [Snapshot { folder_cards: [FolderCard { evidence_refs: [EvidenceRef] }] }]
}
```

| 对象 | 字段与含义 |
|---|---|
| Project | `id: UUID`；`name: string` 名称；`source_type: builtin / local_upload / github / test_fixture`；`source_label: string` 来源展示标签；`created_at / updated_at: UTC datetime` |
| Snapshot | `id / project_id: UUID`；`revision: string` Commit 或内容版本标识；`commit_sha: string \| null` 40/64 位小写十六进制；`storage_path: string` 固定 `snapshots/<id>`，相对数据目录；`created_at: UTC datetime`；`folder_cards: array`；`files: array<{path, size_bytes, sha256}>` |
| FolderCard | `id / snapshot_id: UUID`；`path: string` 相对快照根目录；`title / description: string`；`claim_type: fact / inference / unverified`；`inference: string | null` 名称推断；`evidence_refs: array` |
| EvidenceRef | `id / folder_card_id / snapshot_id: UUID`；`file_path: string` 相对快照根目录；`line_start / line_end: integer` 从 1 起、两端包含、结束不小于开始；`symbol: string \| null`；`excerpt: string` 源码摘录 |

快照按创建时间倒序、ID 倒序；卡片按路径；证据按文件路径、开始行、ID。没有快照或卡片时返回空数组。详情返回所有快照元数据和已保留文件清单；源码分段接口见下方。大型版本历史的分页暂未实现。

- 合法 UUID 不存在：`404 {"detail":"Project not found"}`。
- ID 格式错误或查询校验错误：`422 {"detail":{"code":"invalid_request","message":"请求字段不合法，请检查来源、文件数量、路径和参数。"}}`；不回显上传文件内容。
- `source_type=github` 表示由M4公开GitHub导入器固定Commit后创建。

## 验证

```bash
.venv/bin/python -m pip check
.venv/bin/python -m app.migrate
.venv/bin/python -m app.migrate
.venv/bin/python -m pytest -q
```

测试使用 `var/tests/` 下随机隔离目录，不清空开发数据库。真实重启用两个先后启动的 Uvicorn 子进程，通过临时回环端口发 HTTP 请求，停止后清理测试文件。本机测试通过；测试进程使用 POSIX `pass_fds`，Windows 尚未适配。

服务启动后可手动检查：

```bash
curl http://127.0.0.1:8000/api/health
curl 'http://127.0.0.1:8000/api/projects?limit=20&offset=0'
```

实际结果、截图和限制见 [M2 验收](../evidence/m2/acceptance.md)；历史基础检查见 [步骤 4 记录](../docs/05-m2-foundation-check.md)。

## 导入与源码 API（步骤 5）

### `POST /api/projects/import`

必须 `Content-Type: application/json`。读取请求流上限 **12 MiB**、30 秒，之后才解析 JSON；不接收任意绝对目录、Git 命令或远程 URL。

只读内置样本请求：

```json
{"source":"builtin"}
```

实际读取固定的 `upstream/pocketflow-codebase-knowledge` Git HEAD，然后用该 Commit 枚举普通 blob。未提交修改不进入快照；链接和子模块跳过，不执行 Git hooks、目标脚本或联网下载。

上传请求（示例 `eA==` 是单个字符 x）：

```json
{"source":"upload","name":"我的项目","files":[{"path":"src/example.txt","content_base64":"eA=="}]}
```

`name` 1–200 字符；`files` 最多 500 项；`path` 是去掉所选根目录名的相对 POSIX 路径，禁止绝对路径、`..`、空段、反斜杠、控制字符、Windows 路径特殊字符等；路径上限 700 UTF-8 字节、20 层、每段 200 字节。拒绝重复／大小写冲突路径及文件和目录占用同名路径。浏览器传文件字节，不传本机绝对路径或符号链接对象。

- 每个保留文件 ≤ **1 MiB**，保留候选内容总量 ≤ **8 MiB**，目录 ≤ **500** 个；不解压归档。
- 排除 `.git/.hg/.svn`、依赖、虚拟环境、构建目录、`.ssh/.aws`、`var`，以及 `.env*`、常见凭据名、密钥后缀、数据库文件。前端先过滤以避免上传这些文件，后台独立重复校验。
- 仅保留允许扩展名的 UTF-8 文本：Python、Markdown、README、JSON/YAML/TOML、JS/TS、配置、CSS/HTML、SQL、shell 等（精确清单见 `import_policy.py`）。二进制、未知类型和空目录不会保存；空文本文件可以保留。
- 文件名过滤不是秘密内容扫描器；上传前需自行检查源码中没有硬编码密钥。

成功 `201`：`{detail: ProjectDetail, skipped_count: integer, note: string}`。此接口用于内置和本地上传；内容版本是保留路径与文件 SHA-256 组成的整体哈希。GitHub导入使用下方独立任务接口。

静态扫描不执行任何文件：提取 Python 顶层定义、精确的 `__name__ == "__main__"` 条件、`>>` 表达式，以及 README／部分配置原文，每个文件最多 12 段线索。`>>` 只标操作符存在，不保证它一定是流程；语法错误或无线索时不编造职责。名称推断存入独立 `inference` 字段并显式标“待核实”。

### `GET /api/snapshots/{snapshot_id}/source?path=flow.py&start=1&limit=80`

`id` 为 UUID；`path` 必须已登记在该快照；`start ≥ 1`；`limit` 1–200，默认 80。返回 `200 {path, sha256, line_start, line_end, total_lines, content}`，源码行号从 1 起，两端包含。不渲染 HTML 或执行源码；单次片段输出 ≤ 64 KiB。空文件返回 `total_lines=0`、`content=""`。读取前检查路径、链接及完整文件 SHA-256；只允许已保存文件。

### 错误状态

错误体统一 `{"detail":{"code":"...","message":"可显示给用户的中文提示"}}`；已有项目 404 / 健康检查 503 保留字符串 `detail`。

| 状态 | code / 情境 |
|---|---|
| 422 | `empty_directory`、`invalid_path`、`duplicate_path`、`path_conflict`、`invalid_encoding`、`invalid_request` |
| 413 | `file_too_large`、`project_too_large`、`request_too_large`、`source_slice_too_large` |
| 404 | `file_not_found` |
| 409 | `snapshot_missing`、`snapshot_changed` |
| 403 / 415 / 408 | `origin_rejected` / `invalid_content_type` / `upload_timeout` |
| 503 | `sample_unavailable`，本地样本不存在、不完整或读取超时 |

纯空目录通常不会让浏览器原生目录选择器返回 FileList，因此界面提供明确说明；收到空列表／过滤后为空时显示错误。非法路径由 API 再校验，失败时不创建项目。源码变化或丢失时要求重新导入，不将旧元数据冒充仍然存在的文件。

浏览器目录选择规则参考 [MDN webkitdirectory](https://developer.mozilla.org/en-US/docs/Web/API/HTMLInputElement/webkitdirectory)。当前未提供完整调用图或公开部署；M3提供受限真实模型运行与带引用的职责推断。

## GitHub 导入 API（步骤 8）

`POST /api/github-imports` 接受 `{"repository_url":"https://github.com/owner/repo"}` 并返回 `202` 导入任务；`GET /api/github-imports/{id}` 返回阶段、百分比、Commit、缓存命中、项目／快照ID和错误。详细状态、限制、缓存键和错误码见 [M4说明](../docs/09-github-import.md)。

后台只访问固定的 `api.github.com` 和 `codeload.github.com`；不 follow redirect，不 clone，不执行hooks或仓库文件。远程解析与归档下载合计30秒，超时后不会开始本地保存；压缩16MiB、2000条目、解包32MiB，之后继续应用M2的500文件／8MiB／单文件1MiB上限。归档逐成员验证且不调用通用extract。

无Token时使用GitHub公开API额度；可在进程环境设置 `REPOLENS_GITHUB_TOKEN`，不会写入数据库或页面。404、限流、超时、无效归档和越界路径均进入失败终态，不登记成功快照。验收见 [M4记录](../evidence/m4/acceptance.md)。


## 任务与产物 API（步骤 6–7）

完整字段、状态、错误码、目录、限制和配置见 [M3 任务服务说明](../docs/07-task-runner.md)。`GET /api/runner` 返回模式、真实开关、无密钥配置状态与运行限制；真实请求需要本机模型配置。

- `app/runner.py`：单进程／单活动任务，输入哈希核对、阶段、超时、取消、产物登记。
- `app/run_supervisor.py`：父后台进程丢失时停止任务进程组；POSIX 实现，Windows 未适配。
- `app/run_api.py`、`run_models.py`、`run_store.py`：任务创建／历史／状态／日志／取消／产物合约与存储。
- `app/pocketflow_adapter.py`：固定入口和参数数组，来源核对、环境筛选；按请求模式选择 `stub_worker.py` 或 `pocketflow/worker.py`。
- `app/claims.py`、`app/prompts/folder-responsibility-v1.md`：版本管理的职责提示词与引用校验；真实任务最后调用此提示词，并校验返回引用。
- `migrations/003_runs.sql`：任务、产物表及索引；重复迁移保留记录。
- `pocketflow/requirements.lock`：与 FastAPI 分开的 PocketFlow 环境依赖；见 [安装与来源](pocketflow/README.md)。

运行后台时只使用一个 worker；同一数据目录重复拥有者会被锁拒绝。重启不自动继续未完成任务，而标为 interrupted。步骤6历史验证为44项后台测试；步骤7全量为59项通过，，覆盖成功结果重开、失败、取消、超时、强制退出后进程组清理、重启恢复和产物校验；详细证据见 [步骤 6 验证](../evidence/m3/step-6-check.md)。


## OpenRouter 配置与小测试

已选择 `deepseek/deepseek-v4-flash`。填写被忽略的 `server/.env` 中 `OPENROUTER_API_KEY` 后，在 server/ 执行 `.venv/bin/python -m app.model_check`（仅检查），再执行 `.venv/bin/python -m app.model_check --smoke`（一次短请求）。缺密钥不联网，不打印密钥，不自动重试。

此CLI显式读取四个模型配置字段，运行它不会启用真实模式。后台任务服务使用同一配置读取器；真实选项需启动开关和页面明确选择。参数、请求限制、价格比较见 [OpenRouter 配置说明](../docs/08-openrouter-setup.md)，当前验证见 [准备记录](../evidence/m3/openrouter-precheck.md)。

## 真实任务配置（步骤 7）

完整字段、模式限制、价格／调用上限见 [任务说明](../docs/07-task-runner.md)；本机模型配置见 [OpenRouter 设置](../docs/08-openrouter-setup.md)。默认模式 `stub`，开启 `REPOLENS_ENABLE_REAL_RUN=1` 后允许请求 `mode=pocketflow`，仅固定上游快照 utils、中文、最多3主题。API不接受浏览器传入密钥或模型地址。`GET /api/runner` 返回配置布尔状态，不回传密钥。

迁移当前版本5，模型字段和旧记录的结果缓存键可空。真实结果缓存键包含snapshot_id、快照版本、模型、提示词和全部分析参数；只复用同一快照并在复用前重验产物。模拟模型验证使用假密钥和MockTransport，不消耗模型额度。真实验收证据见 [M3](../evidence/m3/acceptance.md)，缓存边界见 [M4](../evidence/m4/acceptance.md)。
