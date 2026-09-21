# M2 步骤 4：后台与保存基础验证

日期：2026-09-21。起点：本地 `main` 的 `97b5038`；开发分支：`feat/m2-repository-map`。本步仅交付后台和保存基础，不代表 M2 真实仓库地图验收完成。

## 交付与环境

- `server/`：FastAPI 入口、Pydantic 字段、SQLite 保存层、版本化 SQL 迁移、完整依赖锁文件、自动化测试及启动说明。
- `server/.venv/`：独立环境，Python 3.14.6；SQLite 3.53.3；FastAPI 0.141.1、Uvicorn 0.53.0、Pydantic 2.13.5、pytest 9.1.1、HTTPX 0.28.1。
- `var/repolens.sqlite3`：实际本地数据库，版本 1，默认空项目列表；`var/snapshots/`、`var/runs/` 已创建。
- 数据库、测试临时快照、虚拟环境和缓存被现有 `.gitignore` 覆盖，无需修改忽略规则。API 字段和保存语义见 [后台 README](../server/README.md)。

## 实际命令与结果

以下命令在 `server/` 执行：

| 命令 | 实际结果 |
|---|---|
| `.venv/bin/python -m pip check` | `No broken requirements found.` |
| `.venv/bin/python -m app.migrate`（连续执行两次） | 两次均返回 `Schema version: 1`，路径为根目录 `var/repolens.sqlite3` |
| `.venv/bin/python -m pytest -q` | **15 passed**；两个第三方弃用提示，详见下方限制 |
| `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` | 启动完成；实际 HTTP 检查见下表 |

在根目录执行 `git check-ignore var/repolens.sqlite3 server/.venv/pyvenv.cfg server/app/__pycache__/main.cpython-314.pyc`，三个路径均命中忽略规则。`git diff --check` 无空白错误。

### 实际 HTTP 结果

| 请求 | 状态与返回 |
|---|---|
| `GET /api/health` | `200 {"status":"ok","database":"ok","schema_version":1}` |
| `GET /api/projects` | `200 {"items":[],"total":0,"limit":20,"offset":0}` |
| `GET /api/projects/00000000-0000-0000-0000-000000000000` | `404 {"detail":"Project not found"}` |
| `GET /docs` | `200 text/html` |
| `GET /openapi.json` | `200 application/json`，三个业务路径均存在 |

### 持久化与迁移的验证方式

1. 在 `var/tests/m2-*/` 的独立 SQLite 中写入项目 → 快照 → 文件夹卡 → 证据引用，并写一个真实合成 `hello.py` 快照文件。来源明确为 `test_fixture`，不是仓库扫描结果。
2. 启动第一份 Uvicorn **操作系统进程**，通过 HTTP 获取项目详情，与写入的全部字段逐项比较。
3. 完全停止第一份进程，再执行迁移，启动第二份 Uvicorn 进程；再次 HTTP 读取，结果与重启前一致，项目列表总数仍为 1，快照内容未变。
4. 另一个测试连续迁移三次，项目、快照、卡片、证据和迁移历史（含应用时间）均未变化，`integrity_check=ok`、`foreign_key_check=[]`。
5. 四个并发迁移调用仅应用一次版本 1。构造含错误 SQL 的版本 2，验证新表和迁移记录均回滚；修正版本 2 后升级成功，重复执行不破坏旧项目。
6. 已执行 SQL 被修改、旧代码面对新数据库时明确拒绝；重复卡片写入整次回滚；跨快照证据、非法行号、非法结论类型被数据库约束拒绝。绝对路径、`..` 等非法证据路径被模型拒绝。

其余检查覆盖空列表、分页、无效 UUID／查询参数、404、健康检查 503、CORS 允许来源及拒绝来源。测试数据结束后自动清理，不修改开发数据库。

## 剩余事项与边界

- 无阻塞本步交付的问题。前端未接入、扫描／上传未实现、模型与运行任务未实现；接下来按步骤 5 完成真实地图联调。
- 15 项测试出现两个依赖弃用提示：Starlette 提示其 TestClient 的 HTTPX 适配后续转用 HTTPX2；另一个提示来自 Starlette 使用的 AnyIO BlockingPortal 别名。当前锁定组合测试全部通过，后续升级依赖时处理，不隐藏警告。
- 验证环境为 macOS Apple Silicon / Python 3.14，未验收其他操作系统；真实重启测试使用 POSIX 文件描述符传递。当前只适合本机单用户运行。
- 详情返回全部快照元数据，大型版本历史分页留待真实数据规模出现时处理。内部写入仅保证结构和事务，源码真实性、文件过滤和大小限制由步骤 5 导入器负责。
- 本次按 G2 提交并保留 `feat/m2-repository-map`，不执行 G3 合并或远程上传。
