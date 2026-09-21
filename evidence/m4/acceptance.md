# M4 公开 GitHub URL 导入验收

验收日期：2026-09-21。结论：**通过**。本轮只下载并静态读取公开源码，没有执行远程仓库代码，没有发起真实模型请求。原始运行数据使用 `var/tests/` 临时目录并在验证后清理；本文件只记录可复核结果。

## 真实远程样本

- 来源：`https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge`。
- GitHub API 实际解析默认分支后固定 Commit：`05b24cbbb0fe409c5e23c9791f0342f07524ffdc`，与项目已选上游版本一致。
- 第一次真实导入：POST `202`；约 3.8 秒进入 `complete / 100%`；保留 199 个 UTF-8 文本文件、23 个目录卡，过滤 8 个条目。
- `main.py` 通过源码 API 读回，返回 SHA-256 与快照文件清单一致。
- 第二次用带 `.git/` 的等价 URL 导入：POST `202`，解析同一 Commit 后 `cache_hit=true`；项目 ID、快照 ID 不变，项目总数 1、快照数 1，第二次没有请求 codeload 归档。
- 真实无效 URL（追加 `/issues`）同步返回 `422 invalid_github_url`。实际请求一个明确不存在的 GitHub 仓库，任务返回 `failed / github_repository_not_found`，项目总数仍为 0。

真实验证使用临时 UUID，因此 ID 不作为产品固定入口；关键结果由自动测试覆盖，避免依赖一次性运行记录。

## 自动边界验证

`server/tests/test_github_import.py` 覆盖：

- 错误 URL：空值、短写、HTTP、非 GitHub、缺少 repo、Issue 子路径、登录信息、query 和 fragment 均在建任务前拒绝。
- 不存在仓库：模拟和真实网络两条路径均得到稳定错误，未建项目或快照。
- 限流：GitHub `403 + x-ratelimit-remaining: 0` 映射为 `github_rate_limited`；页面保留 URL 并允许重试。
- 重复导入：同一规范仓库和 Commit 复用唯一源码快照，归档只下载一次。
- 版本变化：默认分支从测试 Commit A 变为 B 时，复用项目但新增快照；详情按时间显示 B、A，源码 API 读取 B 的内容。
- 大小、数量和超时：压缩包16MiB、2,000条目、解包32MiB、保留内容500文件／8MiB／单文件1MiB；GitHub解析与归档下载合计30秒。延迟网络夹具确认超时会取消请求，等待原慢请求时长后仍无项目或快照写入。
- 路径范围：多根、绝对／`..`、链接、特殊文件、重复或冲突路径均不能写出 UUID 快照目录。恶意 `../../escape.py` 夹具未在数据目录外生成文件。
- 同一快照：远程快照启动替身运行后，`runs.snapshot_id` 与地图快照相同；运行输入 `main.py` 字节与快照字节一致。

## 源码缓存与结果缓存

- 迁移 005 新增 `github_sources`、`github_snapshot_cache`、`github_import_jobs`，将仓库/Commit 缓存与导入进度持久化。
- `runs.result_cache_key` 包含snapshot_id、快照版本、provider、model、prompt version及全部分析参数。逐字段变化测试均产生不同键，两个同Commit但不同snapshot_id不会互用run。
- 真实 PocketFlow 夹具验证：完全相同的成功请求返回 HTTP `200`、`X-RepoLens-Result-Cache: hit` 和原 run ID；仅更换模型名后返回 `201`、新 run ID 和不同缓存键。缓存复用前重新校验所有产物路径、大小和 SHA-256。
- 固定替身不使用模型结果缓存；相同参数仍产生独立任务和完整进度。

## 页面与回归

- 首页 URL 输入已开放；展示解析、下载、解包、扫描、保存的真实任务阶段、百分比、固定 Commit、错误和缓存命中说明。
- 成功后工作台展示规范来源 URL、完整 Commit 和“扫描与运行共用此快照”；多版本可切换。
- `web/tests/github-import.spec.ts` 在桌面和 390px 窄屏验证进度、最终地图及限流错误。既有项目地图、上传、运行、演示、键盘和响应式路径一并回归。
- 生产构建执行 TypeScript 检查并成功生成 Vite 产物。

## 最终门禁结果

- `server/.venv/bin/python -m pytest -q server/tests`：**79 passed**；仅2条来自测试客户端依赖的弃用 warning，无测试失败。
- `npm run build`：TypeScript检查与Vite生产构建通过，190个模块完成转换。
- `npm run test:e2e`：**22 passed**，覆盖desktop与390px narrow的GitHub导入、地图、上传、任务和演示路径。
- 后台与PocketFlow两个虚拟环境分别执行`pip check`：均为`No broken requirements found`。
- 开发数据库连续两次执行迁移：均返回schema version 5；`git diff --check`通过。
- 一次门禁命令曾从仓库根目录误调用`python -m app.migrate`，因模块路径不在cwd而未启动迁移；随后在`server/`正确目录连续重跑两次通过。此项不是数据库或迁移失败。

## G2 后双轴审查修正

- 工程标准审查发现GitHub导入器复制了`repository.py`的事务写入逻辑；已把GitHub来源、项目和快照的原子写入收回repository边界，并复用同一组聚合插入函数。
- 需求审查发现结果键缺少snapshot_id、扫描阶段早于实际扫描，以及总超时包住不可取消工作线程三项问题。已分别补回归测试：缓存键绑定snapshot_id；扫描线程运行时任务保持`scanning / 75%`；30秒只覆盖可取消的远程解析／下载，慢网络超时后等待原请求时长仍无任何项目或快照写入。
- 修正后再次真实远程导入官方PocketFlow：`succeeded`，Commit仍为`05b24cbbb0fe409c5e23c9791f0342f07524ffdc`，199文件、23目录；等价URL重复导入仍命中同一snapshot。
- 修正后重新执行后台79项、前端build与双视口浏览器22项，全部通过。

## 已知边界

- 仅支持公开 GitHub 仓库的默认分支当前 Commit；不支持私有仓库、GitHub Enterprise、自选 branch/tag/Commit、submodule 内容或 Git LFS 对象。
- 未配置 `REPOLENS_GITHUB_TOKEN` 时受 GitHub 公共 API 额度限制；限流不会自动重试。
- 当前仍是本机单进程服务；导入任务串行。后台重启把活动导入标为 interrupted，不自动续跑。
- M3 真实 PocketFlow 运行仍只允许已核对的 PocketFlow Commit、`utils / 中文 / 最多3主题`；任意远程仓库只能浏览和替身验证，不能执行其代码。
