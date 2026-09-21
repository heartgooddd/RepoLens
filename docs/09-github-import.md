# M4 公开 GitHub 导入与缓存

> 状态：2026-09-21 已实现并验收。只读取公开仓库，固定默认分支当时的 Commit，下载源码归档并静态扫描；不会 clone、checkout、安装依赖或执行仓库代码。

## 用户流程

首页输入完整的 `https://github.com/owner/repo`，后台创建远程导入任务。页面轮询并显示解析、下载、解包校验、扫描、保存和完成／失败；解析后同时展示 12 位 Commit。成功后进入项目地图，工作台显示规范化来源 URL 和完整 40 位 Commit。

接口：

- `POST /api/github-imports`：`{"repository_url":"https://github.com/owner/repo"}`，返回 `202 GitHubImportJob`。
- `GET /api/github-imports/{job_id}`：读取 `status / stage / progress / commit_sha / project_id / snapshot_id / cache_hit / error_*`。
- 活动状态是 `queued / running`；终态是 `succeeded / failed / interrupted`。后台重启不会把未完成导入伪装成成功。

只接受 GitHub HTTPS 仓库根地址；不接受登录信息、HTTP、其他站点、查询参数、fragment、branch、Issue 或文件页。`.git` 与尾部 `/` 会规范化为同一来源。

## 固定版本与边界

后台先从 GitHub API 读取公开仓库和默认分支，再解析 40 位 Commit；归档请求固定到该 Commit 的 `codeload.github.com` 地址，不直接请求用户输入的任意主机。未设置 Token 时使用 GitHub 公共额度；可在后台进程环境设置 `REPOLENS_GITHUB_TOKEN` 提高额度，Token 不进入 API、SQLite、日志或页面。

限制：

| 边界 | 上限 / 行为 |
|---|---|
| GitHub解析与归档下载 | 合计30秒；连接5秒、单次网络读取20秒。超时取消网络请求，尚未开始本地解包或保存 |
| 压缩归档 | 16 MiB |
| 归档条目 | 2,000 |
| 解包后普通文件总量 | 32 MiB |
| 最终保留源码 | 500 文件、8 MiB；单文件 1 MiB |
| 路径 | 一个仓库根；拒绝绝对路径、`..`、空段、链接、设备文件、重复／大小写冲突及文件目录冲突 |
| 内容 | 沿用 M2 白名单，只保留 UTF-8 文本；过滤环境文件、常见凭据、依赖、构建产物和二进制 |

实现不调用 `tar.extract*`；每个归档成员先验证，去掉唯一根目录后才读取，写盘时再次确认目标仍在 UUID 快照目录内。

## 两类缓存不能混用

源码快照缓存位于 `var/snapshots/<snapshot-id>/`，SQLite 用 `github_sources` 和 `github_snapshot_cache` 建立 `owner/repo + commit_sha → snapshot_id` 唯一映射。同一仓库同一 Commit 再导入时返回相同项目和快照，不重复下载；默认分支指向新 Commit 时，在同一项目下新增快照。

模型结果仍位于 `var/runs/<run-id>/`。`runs.result_cache_key` 由snapshot_id、快照版本、运行模式、模型服务商、模型名、提示词版本、语言、主题数、分析范围、情境和固定运行器版本共同计算。只有同一snapshot_id且产物哈希仍有效的成功真实`pocketflow`结果可复用；任何快照、模型或参数不同都会创建新任务。替身任务始终独立运行，不冒充模型结果缓存。

地图扫描、源码读取和运行任务都引用同一个 `snapshot_id`。运行前仍逐文件核对登记大小和 SHA-256，再把相同字节复制到任务输入目录；远程来源不会改变 M3 的受控执行入口，也不会把被分析仓库变成可执行入口。

## 错误

页面直接展示后台的稳定错误信息：`invalid_github_url`、`github_repository_not_found`、`github_rate_limited`、`github_timeout`、`github_unavailable`、`github_archive_too_large`、`invalid_github_archive`、`unsafe_archive`、`empty_directory`、`file_too_large`、`project_too_large`。失败任务不创建项目或不完整快照；可修改 URL 后重新提交。

实际边界、真实 PocketFlow 远程样本和完整验证见 [M4 验收](../evidence/m4/acceptance.md)。
