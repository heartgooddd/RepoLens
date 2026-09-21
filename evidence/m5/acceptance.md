# M5 已登记操作配方验收

日期：2026-09-22。分支 `feat/m5-action-recipes`，基线 `eea0629`，批准的设计提交 `ed4013c`。本记录区分真实项目支持依据、M5 运行器验证和离线测试产物。

## 交付范围

- 正式配方只有 `pocketflow-tutorial@1`，固定官方 PocketFlow Commit `05b24cbbb0fe409c5e23c9791f0342f07524ffdc`、`server/pocketflow/worker.py`、独立 Python 环境及精确依赖锁。
- 配方声明入口、来源、依赖检查、严格参数、cwd、默认/最大 900 秒超时、SIGTERM→0.2秒→SIGKILL 进程组停止和受限 Markdown/JSON 产物。
- 页面从 `GET /api/recipes` 生成表单，创建请求使用 `recipe_id + snapshot_id + parameters`。显示输入快照、配方版本、隔离/依赖状态、日志、退出码和产物预览；错误可重新读取。
- 迁移 006 保存配方身份、规范化参数 JSON 和隔离方式，旧运行记录保持可读。模型结果缓存额外绑定配方版本及全部参数；源码缓存不变。
- 可信代码注册表决定执行入口；用户上传和 GitHub 快照只能提供分析数据。未知入口/命令/额外或错误参数均在启动前拒绝；旧真实 API 也经过同一配方与沙箱。

## 证据分类

1. **真实第三方支持**：沿用 [M3 真实页面任务](../m3/acceptance.md)，任务 `1acf3d68-c857-4acf-89d9-bee17f98c512`，真实模型 `deepseek/deepseek-v4-flash`，7 次调用、费用 $0.0034756449。本轮没有付费模型请求。
2. **固定 worker 沙箱验证**：实际执行固定 PocketFlow 代码、真实子进程、SQLite 和产物流程；模型 HTTP 由现有 MockTransport 夹具替换，夹具额外阻止其他 HTTP 调用。证明登记及隔离后的执行链路，不能算第二次真实模型实跑。
3. **运行器通用能力**：内部第二份 `public=False` 配方使用自己的参数和入口，通过同一个生命周期生成固定文本；正式清单仍只有 PocketFlow。停止、超时、退出码、范围外访问等夹具均只证明运行器行为。
4. **网络检查**：沙箱内无密钥 `HEAD https://openrouter.ai/api/v1/models` 返回 200，进程退出码 0；只检查 DNS/TLS/出站能力，没有提交模型生成请求。

## 验证结果

| 验证 | 结果与证据 |
|---|---|
| 后端完整回归 | `server/.venv/bin/python -m pytest -q server/tests`：96 passed；2条既有Starlette测试依赖弃用警告；审查修正后的定向回归见下文 |
| 审查修正定向回归 | `server/.venv/bin/python -m pytest -q server/tests/test_recipes.py server/tests/test_isolation.py server/tests/test_runs.py server/tests/test_real_runs.py`：35 passed；包含新增的不同配方Commit元数据用例，无真实模型请求 |
| 类型与生产构建 | `cd web && npm run build`：通过，192 modules |
| 浏览器完整回归 | `cd web && npm run test:e2e`：26 passed，desktop/narrow各13项 |
| M5 页面样式/离线标识收尾 | `npm run test:e2e -- tests/recipes.spec.ts`：4 passed；服务端参数表单→启动→离线PocketFlow→预览→刷新历史，以及配方服务错误/恢复 |
| 依赖一致性 | 两个环境 `python -m pip check` 均返回 No broken requirements found；配方另校验PocketFlow锁定包版本 |
| 实际数据库迁移 | 连续两次 `cd server && .venv/bin/python -m app.migrate` 均返回版本6；M3成功任务与7个产物保留，配方字段仍为空，integrity_check=ok |
| 隔离文件范围 | 真实沙箱进程可读input、可写output；范围外读/写、input修改被PermissionError拒绝；假沙箱仅返回0无法通过能力自检 |
| 信号范围 | 沙箱内允许向自身/子进程发送信号，不允许向宿主父进程发送信号；使用无副作用的signal 0验证 |
| 固定入口隔离 | 只授权上游固定Commit的Python文件；普通快照无执行登记能力；依赖版本不匹配返回不可用 |
| 取消/超时 | 子进程忽略SIGTERM仍被SIGKILL清理；PID消失、终态正确、退出码保留、产物为空 |
| 非零退出 | 夹具返回37，运行记录保存37及recipe_exit_nonzero，无成功产物 |
| 产物边界 | 拒绝输出父目录软链接，检查发生在读取/派生写入前，input未被写入verified-claims；校验链接、类型、数量、体积、相对范围 |
| 缓存与历史 | 同配方/参数成功结果可复用；升级配方版本或改变任一额外参数改变缓存键；历史参数与结果保持不变 |

测试先观察到缺失 `/api/recipes`、无隔离模块、未保存配方字段、缓存缺额外参数、父目录软链接导致派生文件写入、假能力探测误通过等失败，再逐项实现/修复为绿色。新浏览器测试先因不存在配方表单而失败，后通过同一表单向后台提交规范参数。

## 页面截图（全部为离线模型夹具）

- [桌面：配方表单与离线结果](recipe-offline-desktop.png)
- [窄屏：配方、退出码与结果](recipe-offline-narrow.png)

截图来自真实前后端测试服务，模型名称显示 `fixture/offline-no-model-request`，配方说明标注测试服务/离线响应。界面保留真实运行操作路径，用于验证交互；截图中的固定正文、零费用和模型响应不是本轮真实模型产出。

## 平台与扩展边界

当前仅验收本机 macOS；非macOS、缺少sandbox-exec或能力检查失败时拒绝配方启动。系统手册已标记sandbox-exec deprecated。允许Python/系统运行库、证书和必要目录元数据读取；固定配方允许出站网络，不实施域名白名单、CPU/内存或运行时磁盘配额。

停止覆盖受管进程组及其中忽略SIGTERM的后代；不登记会自行setsid/双重fork脱离进程组、或委托外部守护进程的项目。此项是新增真实配方的接入约束，不能把当前进程组方案称为任意恶意程序容器。新项目须独立核查并实跑后才能加入支持清单，见 [新增配方开发操作](../../docs/10-action-recipes.md)。

## 交付检查

G3已执行：本地main从`eea0629`快进至实现及审查修正提交`ee2b6e7`，与阶段分支一致。合并后配方清单、版本来源和隔离冒烟验证7 passed；工作区干净，保留阶段分支，未推送远程。本条为合并后补记，不改变已验收代码。

实现、文档和筛选截图按G2精确提交；完整代码审查与修正后按G3快进合并本地main，保留阶段分支。不推送远程；数据库、快照、原始运行数据和密钥继续留在被忽略的var/。

双轴独立代码审查：规格轴无阻断问题，修正设计文档遗留“待实现”状态；规范轴发现其他配方可能继承PocketFlow来源Commit，以及产物限制重复定义。已修正为所选配方的Commit驱动持久化、worker元数据和缓存身份，并集中产物限制常量。新增不同Commit配方夹具先观察到3项失败，再验证修复；仍不代表新增第三方项目支持。
