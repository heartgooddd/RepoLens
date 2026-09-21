# RepoLens 后台：M2 步骤 4

本步提供 SQLite 保存基础和读取 API。前端仍使用 M1 演示数据；没有导入、扫描、运行或模型接口。首次启动的项目列表为空，不自动插入示例项目。

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
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- 后台：http://127.0.0.1:8000/api/health
- 可交互接口文档：http://127.0.0.1:8000/docs
- 机器可读字段定义：http://127.0.0.1:8000/openapi.json
- `Ctrl+C` 停止；再运行同一条 Uvicorn 命令即重启，数据仍使用同一文件。
- 每次启动在 FastAPI lifespan 中自动执行迁移；手动迁移用于检查或部署准备。已有版本不会重新执行。端口占用会报错，先核对占用进程。
- 仅监听本机回环地址。当前是无认证的本地单用户服务，不用于公开部署。CORS 允许 `http://127.0.0.1:5173` 和 `http://localhost:5173` 的 GET 请求，前端接线留到步骤 5。

## 数据位置

默认路径由代码位置确定，与启动终端所在目录无关：

```text
RepoLens/var/
├── repolens.sqlite3             元数据与迁移历史
├── snapshots/<snapshot-id>/     未来导入的源码快照
├── runs/<run-id>/               未来运行日志和产物
└── tests/m2-*/                  自动验证的隔离数据，测试结束自动清理
```

本步创建前三项的基础目录；快照和运行内容尚未导入。测试会在独立目录中创建一个带 `hello.py` 的合成快照，明确标记 `source_type=test_fixture`，不污染默认数据库。

可通过环境变量 `REPOLENS_DATA_DIR` 指定**绝对**数据目录，数据库始终命名为 `repolens.sqlite3`；省略则使用根目录 `var/`。`.env.example` 是无密钥模板，程序不会自动加载 `.env`。不要将数据目录指向受 Git 跟踪的源码目录。项目标签是展示名称，不应存密钥或本机绝对路径。

`var/`、`.venv/`、缓存均被根目录 `.gitignore` 排除；迁移代码和依赖锁文件被跟踪。本地 Git 提交不备份数据库或快照。需要备份时先停服务，复制整个 `var/`，恢复时使用与数据库迁移版本匹配的代码。

## 模块与数据结构

| 位置 | 职责 |
|---|---|
| `app/main.py` | 生命周期、健康检查、项目列表与详情、CORS |
| `app/models.py` | Pydantic 接口字段、路径和关联校验 |
| `app/repository.py` | 事务写入与读取；下一步导入器的保存入口 |
| `app/db.py`、`app/migrate.py` | SQLite 连接、迁移执行器及 CLI |
| `migrations/001_repository_metadata.sql` | 初始表、索引、外键与约束 |
| `tests/` | HTTP 合约、持久化、迁移及真实进程重启验证 |

关系：`projects → snapshots → folder_cards → evidence_refs`。每个项目可有多个快照；每个快照中的目录路径唯一；证据的文件位置依附于同一快照中的文件夹卡，复合外键防止跨快照错配。删除父记录会级联删除子元数据，目前不暴露删除 API。事实、推断和待核实分开存储，不能用推断覆盖原始引用。

`create_project(database, ProjectDetail)` 是内部 Python 保存入口，一次事务写入完整聚合；不覆盖已有 ID，失败则全部回滚。本步不增加用于演示的公开写入 API。它保存元数据，不复制文件、不验证源码内容真实性；下一步导入器负责安全快照和证据提取。

### 后续迁移规则

1. 新增 `002_<name>.sql`、`003_<name>.sql`，版本连续；不要修改已执行的迁移。
2. 每条完整 SQL 语句以分号结束，最后一条结束后不添加独立注释；一行不写多条语句。不要在文件中写 `BEGIN/COMMIT/ROLLBACK`、`VACUUM` 等自行控制事务的语句。
3. 执行器在一个 `BEGIN IMMEDIATE` 事务中核对版本与 SHA-256、执行待应用的 SQL 并写 `schema_migrations`。SQL 或校验失败会回滚并阻止服务启动；不会删库重建。
4. 修改过的历史迁移、缺失版本、比代码新的数据库会被拒绝；恢复匹配代码或补充正确迁移。当前不提供自动降级。
5. `.venv/bin/python -m app.migrate` 可重复运行；新迁移要添加已有数据升级与失败回滚测试。

实现参考：[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)、[Python sqlite3 事务与连接](https://docs.python.org/3/library/sqlite3.html)。连接按操作打开并关闭，启用外键、10 秒锁等待，使用参数绑定；迁移避免 `executescript` 的隐式提交行为。

## API 请求与响应

共同约定：三个端点均为 `GET`，无请求体或密钥。ID 为 UUID 字符串；时间为带 `Z` 的 UTC ISO 8601 字符串；路径用 `/`，根目录是 `.`。响应不返回本机绝对路径或直接读取源码内容。详细模型与必填字段同步生成在 `/openapi.json`。

### `GET /api/health`

无参数。实际读取迁移表和项目表，成功 `200`：

```json
{"status":"ok","database":"ok","schema_version":1}
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
| Snapshot | `id / project_id: UUID`；`revision: string` Commit 或内容版本标识；`commit_sha: string \| null` 40/64 位小写十六进制；`storage_path: string` 固定 `snapshots/<id>`，相对数据目录；`created_at: UTC datetime`；`folder_cards: array` |
| FolderCard | `id / snapshot_id: UUID`；`path: string` 相对快照根目录；`title / description: string`；`claim_type: fact / inference / unverified`；`evidence_refs: array` |
| EvidenceRef | `id / folder_card_id / snapshot_id: UUID`；`file_path: string` 相对快照根目录；`line_start / line_end: integer` 从 1 起、两端包含、结束不小于开始；`symbol: string \| null`；`excerpt: string` 源码摘录 |

快照按创建时间倒序、ID 倒序；卡片按路径；证据按文件路径、开始行、ID。没有快照或卡片时返回空数组。详情本步返回所有快照元数据，源码树和文件内容接口留到步骤 5；大型版本历史的分页暂未实现。

- 合法 UUID 不存在：`404 {"detail":"Project not found"}`。
- ID 格式错误或查询校验错误：`422 {"detail":[{"loc":[...],"msg":"...","type":"..."}]}`（FastAPI 校验结构，可含 `input` 等字段）。
- `source_type=github` 只是预留数据枚举，不代表已具备远程导入。

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

实际结果、限制和日期见 [步骤 4 验证记录](../docs/05-m2-foundation-check.md)。
