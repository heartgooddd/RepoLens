# M6 本地技术交付验收

日期：2026-09-22。分支 `feat/m6-local-delivery`，基线 `4795ef9`。本记录仅覆盖技术交付，不代表真实用户试用已完成。

## 两条独立状态

- 技术交付：**通过**。干净检出安装、固定上游准备、双击入口、页面运行和数据恢复已验证；回归及审查记录如下。
- 3位真实目标用户试用：**0/3，未完成**。尚无真实反馈，反馈迭代未完成。[观察模板](trial-observation-template.md)为空模板，不是试用证据。

## 环境与来源

macOS26.6.2（25G83）、Apple Silicon arm64；Python3.14.6、Node22.23.0/npm10.9.8。安装清单是两个requirements.lock和web/package-lock.json。PocketFlow来自`server/pocketflow/source.json`内固定官方HTTPS地址，Commit `05b24cbbb0fe409c5e23c9791f0342f07524ffdc`，LICENSE保留。只承诺当前macOS环境，尚未验证其他机器/Windows/Linux的完整交付。

## 干净检出重现

从本地已提交Git内容 `0658e39` 克隆到被忽略的 `var/m6-acceptance/Clean checkout with spaces/`，并同步只含停止输入校验修正的`6e835c3`。克隆开始时没有upstream、两个venv、node_modules、dist或server/.env；不是复制开发目录。执行该检出的 `./Install.command`，实际从官方GitHub获取固定Commit，独立安装两个环境、前端依赖并构建，返回“安装完成”。未借用原项目的upstream或venv；包管理器缓存不清空，仍按锁文件正常安装。

重复执行同一Install.command成功；两次安装都核对来源/HEAD。用 `git remote get-url origin`、`git rev-parse HEAD` 在新upstream复查，与固定来源一致。干净检出 `git status --short` 为空，未复制原密钥。测试夹具本地Git仓库仅证明重复安装和拒绝修改逻辑，官方远程准备另由本条真实验证。

## 启动、停止与页面

- 用macOS `open Start.command`/`open Stop.command`通过与Finder双击相同的LaunchServices路径打开交付入口；启动终端与浏览器打开，健康检查schema6。另直接执行 `.command`核对终端行为。
- `lsof`确认API/前端只在127.0.0.1:8000监听。构建页面与API同源提供；源码、.env、数据库不能通过静态路径访问，未知API保持JSON404。
- 重复启动被拒绝，不杀旧进程；占用端口不会被“清理”；其他检出的Stop.command找不到自己的控制连接时拒绝，不停止此服务。
- 页面验收在上述全新安装的服务上执行 `npx playwright test -c playwright.delivery.config.ts`：本地样本导入→flow.py源码依据→页面替身任务→结果预览→刷新历史，1 passed；恢复专用用例因模式不同明确skip。没有模型请求。
- 默认真实入口关闭；显式`REPOLENS_ENABLE_REAL_RUN=1`才允许页面选择真实任务，仍需本机密钥和用户启动。安装/启动不会自动生成或扣费。
- 真控制连接收到null、数组、错误token、非ASCII token都返回denied，后台健康仍为200。停止信号只发给启动器自己的Popen子进程。
- 在独立临时数据目录对本工具新建的启动器进程执行SIGKILL，后台监护逻辑使其退出，8000关闭，数据锁重新可获取；没有按端口/PID模糊匹配杀未知进程。

## 一次实际备份与恢复

先确认原后台是本仓库server目录的Uvicorn，且原数据库无活动任务，再正常SIGTERM停服。从server目录执行：

```bash
.venv/bin/python -m app.backup create '../var/m6-acceptance/Saved data backup'
.venv/bin/python -m app.backup restore '../var/m6-acceptance/Saved data backup' '../var/m6-acceptance/Restored data'
```

结果均成功。备份435文件、6,019,267字节、schema6；恢复保留2项目、3任务。M3真实任务 `1acf3d68-c857-4acf-89d9-bee17f98c512` 的7个产物全部存在。没有覆盖原var，恢复到独立新目录，密钥不复制。

新检出的启动器通过REPOLENS_DATA_DIR指向恢复目录。恢复专用Playwright用例传入原项目`9fc3751c-93e8-429a-bbdb-9383a7f7685e`和M3任务ID：打开项目→读取flow.py已校验源码→选择原历史任务→打开真实Markdown，1 passed；新任务用例明确skip，监听到的新POST /api/runs为0。这是重开旧真实结果，不是本轮真实模型生成。

运行恢复服务时尝试备份，返回“RepoLens 数据目录正在使用，请先停止后台服务再继续”，未发布目标。自动测试另覆盖SQLite已提交WAL、历史API内容一致、链接/硬链接/FIFO、路径穿越、重复清单键、哈希/迁移/外键/触发器篡改、缺引用、目录冲突、超限及既有空目标拒绝。

## 自动检查与审查

| 检查 | 命令/结果 |
|---|---|
| 完整后端 | `server/.venv/bin/python -m pytest -q server/tests --tb=short`：合并后137 passed（含最终venv校验回归）；2条既有Starlette测试依赖弃用警告 |
| 构建 | `cd web && npm run build`：成功，192 modules |
| 完整浏览器回归 | `cd web && npm run test:e2e`：26 passed，桌面/窄屏各13项；仅既有NO_COLOR/FORCE_COLOR提示 |
| 本地工具收尾 | `server/.venv/bin/python -m pytest -q server/tests/test_local_tools.py`：19 passed；含Homebrew Node22路径及现有venv错误Python版本拒绝 |
| 数据/本地工具定向回归 | test_delivery.py + test_local_tools.py：38 passed |
| 安装与恢复交付页面 | 全新安装1 passed，恢复模式1 passed；各自skip另一种模式，无模型请求 |
| 数据模块规格/质量审查 | 两个独立审查均无阻断发现；21个数据维护用例覆盖主要边界 |

启动器审查发现并修正：默认真实开关应保留关闭、TIME_WAIT导致即时重启失败、畸形JSON/非ASCII停止token导致未鉴权退出。均先观察回归失败，再修正为绿；实际TCP控制连接也验证拒绝。首次安装实际发现Path.open不支持opener、Finder选错Node版本，已修正并增加回归。

最终规格复核无阻断发现；最终质量复核指出现有venv也必须核验实际Python版本，已在两个环境的pip安装前加入3.14/必要模块检查，错误时保留原环境并提示另存后重建。两个错误版本回归先失败后通过，当前目录再次Install.command成功，复核关闭该项。以上审查不替代真实用户反馈。

## 截图

- [干净检出：页面替身运行及刷新历史](local-delivery.png)，固定替身内容，不是模型生成质量证据。
- [恢复目录：M3真实历史结果](restored-m3-result.png)，旧结果重开，不是新调用。

## 交付边界

安装脚本不自动安装系统包，不运行上游安装脚本，不覆盖有修改的上游；Python锁为精确版本但尚不带包哈希。备份是未加密目录，默认最大8GiB/100000文件，可能含私有源码和模型输出，需妥善保管。当前迁移版本须匹配；服务停服、手工不改数据是文件一致性前提。无多用户认证，不对公网提供服务；macOS沙箱仍受M5登记入口/进程组准入限制。

原数据及验收副本保留在被忽略的var/，密钥不提交。G2精确提交技术代码、文档和筛选截图；技术通过后G3快进合并本地main、保留阶段分支，不push。真实试用与反馈迭代继续未完成。

### G3 回执

本地main已从`4795ef9`快进至实现与审查修正提交`0250f0c`；合并后完整后端137 passed，最终安装后的主目录启动/健康检查/停止再次通过。原数据仍为2项目、3任务，无新模型任务。代码树与阶段分支一致；本回执仅补记文档。服务已停止，工作区干净，阶段分支保留，未推送远程。
