# M3 步骤 6：任务开发与替身联调验证

- 日期：2026-09-21。
- 起点：干净的本地 `main`，`180e50dc11ac43e86275d59d4899b441fbf11df1`。
- 分支：按 G1 新建 `feat/m3-pocketflow-runner`；本步按 G2 提交，**不合并 main**，未上传远程。
- 结论：步骤 6 通过。M3 整体仍待步骤 7 真实运行；本记录与截图全部是固定替身输出，**没有发送真实模型请求**。

## 实现与来源

官方 PocketFlow 来源、Commit、许可证和环境详见 [依赖说明](../../server/pocketflow/README.md)。Commit 为 `05b24cbbb0fe409c5e23c9791f0342f07524ffdc`，MIT；上游 `git status --porcelain` 为空。Python 3.14.6，后台与 PocketFlow 各有独立虚拟环境；原始上游源码保持不变，完整 PocketFlow 环境锁文件纳入 Git。

任务使用固定替身子进程，分析输入来自已登记快照，先核对哈希再复制；命令不经过 shell。数据库版本 003 保存任务与产物索引，日志及输出留在被忽略的 `var/runs/`。配置、API 字段、状态与限制见 [任务服务说明](../../docs/07-task-runner.md)。

## 验证命令与结果

**server/**：

```bash
.venv/bin/python -m pytest -q tests/test_runs.py --tb=short
.venv/bin/python -m pytest -q
.venv/bin/python -m app.migrate
.venv/bin/python -m app.migrate
pocketflow/.venv/bin/python -m pip check
```

- 聚焦任务测试 9 项通过；补充畸形目录引用检查后，该引用测试单独再次通过（1 项）；全量 **44 项通过**（12.85 秒），含此前 M2 的迁移、持久化、导入与路径边界。
- 两次迁移均返回 schema version 3；没有删除或覆盖旧项目及任务。
- PocketFlow `pip check`：No broken requirements found。
- 另通过适配器生成固定入口数组，取前 4 项后追加 `--help`，在 `var/runtime-check/`、筛选后的环境下执行，返回 0；检查帮助包含 `--dir`、`--max-abstractions`。仅参数帮助，未调用生成管线。
- pytest 有 2 条测试依赖弃用提示：Starlette 的 HTTPX TestClient 适配、AnyIO BlockingPortal 别名；本步未因这些提示变更依赖，不影响结果。

**web/**：

```bash
npm run build
npm run test:e2e
```

- TypeScript 与生产构建通过；新增 `react-markdown 10.1.0`，package-lock 保存，构建约 381 kB JS／119 kB gzip。
- **16 项 Chrome 浏览器检查通过**（1.3 分钟），覆盖桌面 1440×1000、窄屏 390×844，另保留 M2 的 320／768 宽度溢出检查。任务测试使用隔离后端真实 HTTP + SQLite + 子进程，不 mock 任务响应。
- 本地运行器一次只允许一个活动任务，因此浏览器测试串行使用 1 worker；不与用户开发数据库共用数据。
- 原有 M1 演示和 M2 地图回归通过。Node 控制台有 NO_COLOR/FORCE_COLOR 提示，非页面错误。

## 关键检查

| 情境 | 实际结果 |
|---|---|
| 成功 | 记录 queued→running→succeeded，六阶段写入日志，index.md、章节及引用产物登记；退出码 0 |
| 失败 | 固定情境在 AnalyzeRelationships 返回退出码 23；status=failed，无成功产物 |
| 取消 | 慢速替身可停止进程组，status=cancelled；后续读取与重复取消保持终态 |
| 超时 | 测试将超时设为 0.15 秒，任务失败且不发布产物；产品默认 180 秒 |
| 并发创建 | 已有活动任务返回 409 runner_busy |
| 后台正常退出 | 活动任务标 interrupted；重新启动可读到终态，不自动续跑 |
| 后台硬退出 | SIGKILL 测试隔离 API 进程；监督进程终止所属进程组，重新启动将遗留任务标 interrupted |
| 成功后重启 | 完整 Run 响应读回一致，产物仍能校验与读取 |
| 来源和参数 | 不存在快照、非法目录、越界主题数、任意 command／mode、跨来源写请求和过大请求被拒绝 |
| 快照／产物被修改 | 哈希或缺失检查失败；不使用变化的源码、不返回变化的产物 |
| 职责引用 | 文件、哈希、行号、引用逐字匹配才标推断；伪造引用和越界文件标待核实，原始事实未覆盖 |
| Markdown | 原始 script 未执行，危险链接没有可执行 href，远程图片没有请求；已登记章节能切换，附件可下载 |
| 历史参数 | 改表单不改变旧任务；刷新后仍可查看原任务语言／主题数和固定输出 |

首次任务测试暴露了时间字段类型与共用序列化器不匹配，改为带时区日期类型后上述测试全部通过。一次本机截图辅助脚本在截图完成后用相对 URL 做 API 读取（未设 baseURL），导致 Invalid URL；改为绝对本机 API 地址读回通过，未重新创建任务。此为辅助脚本错误，不是产品 API 错误。

## 本机 PocketFlow 快照检查

没有重新导入或覆盖 M2 的项目数据：

- 项目：`9fc3751c-93e8-429a-bbdb-9383a7f7685e`。
- 快照：`5a4a6d2b-049f-440d-8544-8c49fec62e8d`。
- 本步替身任务：`f8190626-c5ad-4b43-8a4a-6f25d932bd89`，utils / zh / 3，mode=stub，succeeded，4 个产物。
- index.md SHA-256：`26e307c1d4e007bfb1f11f46b5ea372ec346c60ab090f20b9d61185794e8ebac`。
- 经页面创建、打开结果；停止开发后台，再用 README 命令重启，Run 完整响应与重启前相等，index.md 哈希一致；Chrome 重新进入同一项目后可打开结果。
- 本机复查入口：http://127.0.0.1:5173/#/projects/9fc3751c-93e8-429a-bbdb-9383a7f7685e 。这些 ID 只适用于本机当前 var 数据，不随 Git 分发。

## 实际页面截图

全部为本次运行 React 实现的截图，不使用 M0 样稿。自动测试中的两文件合成项目只验证任务流程；另有本机真实 PocketFlow 快照上的替身输出截图。已人工查看桌面与窄屏结果，未见内容重叠或横向溢出；窄屏为纵向布局，用顶部区域按钮定位运行窗口。

| 状态 | 桌面 | 窄屏 |
|---|---|---|
| 未运行表单 | [桌面](desktop-task-ready.png) | [窄屏](narrow-task-ready.png) |
| 替身处理中 | [桌面](desktop-task-running.png) | [窄屏](narrow-task-running.png) |
| 固定结果与待核实引用 | [桌面](desktop-task-result.png) | [窄屏](narrow-task-result.png) |
| 失败 | [桌面](desktop-task-failed.png) | [窄屏](narrow-task-failed.png) |
| 取消 | [桌面](desktop-task-cancelled.png) | [窄屏](narrow-task-cancelled.png) |

本机样本：[PocketFlow utils 固定输出](pocketflow-utils-result.png)、[后台重启后重新打开](pocketflow-after-restart.png)。

## 剩余事项（步骤 7）

1. 确定实际模型服务、模型名称、本机密钥配置方式；只检查配置状态，不展示密钥。步骤 6 不配置也不读取模型密钥。
2. 接通已准备的固定 PocketFlow 入口、真实阶段输出解析和受限模型环境；职责补充提示词实际调用、路径映射与结果登记也需接通。当前仅模板、引用校验和替身数据，不宣称模型职责补充已经可用。
3. 在用户授权范围内做一次 utils／中文／最多 3 主题真实请求，核验输出、提供商错误、取消与历史重开。真实结果质量和调用费用本步没有验证。
4. 当前面向本机单用户、单后台、单活动任务，使用 POSIX 进程组；虚拟环境不是操作系统沙箱。Windows／多用户／公开部署不在本步验收范围。

步骤 6 没有剩余阻塞；不得将本记录当作步骤 7 真实运行验收或 M3 合并依据。
