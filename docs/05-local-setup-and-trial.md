# 本地安装、启停、备份恢复与试用

本说明面向 macOS 本地单用户。技术交付与真实试用分别验收：技术结果见 [M6验收](../evidence/m6/acceptance.md)；真实用户目前 **0/3，未完成**，反馈迭代也未完成。自动化测试和开发者操作不计入真实用户数。

## 1. 首次安装：从 Git 检出开始

需要 macOS、Git、Python **3.14**（含 venv、ssl、sqlite3）、Node.js **22.12+ / 22.x** 和 npm。当前验收机器的版本为 Python 3.14.6、Node22.23.0/npm10.9.8。下载依赖和固定上游需联网；查看已有项目和历史结果不需要模型密钥。需要足够的磁盘空间同时容纳两个 Python 环境、前端依赖、运行数据及备份。

1. 把 RepoLens 的 Git 仓库检出到自己的普通文件夹，允许路径包含空格。仓库尚未公开发布，不使用虚构的 GitHub clone 地址；由交付者提供本地 Git 仓库或已授权的真实远程地址。不要把现有 `var/` 或 `server/.env` 发给试用者。
2. 缺少 Git 时按系统提示安装 Apple Command Line Tools，或运行 `xcode-select --install`。已有 Homebrew 可按 [Python3.14配方](https://formulae.brew.sh/formula/python@3.14)与[Node22配方](https://formulae.brew.sh/formula/node@22)使用 `brew install python@3.14 node@22`；其他来源按 [Python](https://www.python.org/downloads/macos/) 与 [Node.js](https://nodejs.org/en/download) 官方安装说明操作。Homebrew 的 Node22 为独立版本，必要时把 `$(brew --prefix node@22)/bin` 加入 PATH。脚本会检查版本，不自动安装系统包、不使用 sudo。
3. 在 Finder 双击根目录 **Install.command**。终端显示四阶段进度；第一次可能需要数分钟。等待“安装完成”，失败则按提示处理后重新执行。
4. 安装器从 [PocketFlow 官方仓库](https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge) 获取固定 Commit `05b24cbbb0fe409c5e23c9791f0342f07524ffdc`，保留 MIT LICENSE。来源保存在 `server/pocketflow/source.json`；完整 Git 检出位于被忽略的 `upstream/pocketflow-codebase-knowledge/`。不会运行上游安装脚本，也不会替换已有不匹配/修改过的目录。
5. 按两个 `requirements.lock` 分别准备 `server/.venv` 和 `server/pocketflow/.venv`，执行依赖检查；前端使用 `npm ci --ignore-scripts` 和生产构建。安装记录写入 `var/local-delivery/installation.json`。密钥文件缺失时仅创建空白私有配置，不覆盖已有配置。

`upstream/`、依赖、构建产物和运行数据不进入 Git，因此每个全新检出都必须安装。源码/锁文件变化或移动工作目录后再次安装；Python虚拟环境不可当作可搬移安装包。重复安装不会清空项目数据。安装前先停止本目录的应用和手工启动的开发后台。

双击脚本会依次查找 `~/.local/bin`、Apple Silicon/Intel Homebrew的 `opt/node@22/bin`、`/opt/homebrew/bin`、`/usr/local/bin` 及原 PATH。若用户目录中已有其他版本 Node，调整自己的工具入口或移走冲突入口后再重试。不要替换系统 Python。

## 2. 启动和停止

- 双击 **Start.command**。依赖、固定入口、隔离能力、安装状态及端口检查通过后，自动打开 **http://127.0.0.1:8000/**。构建后的页面与 API 由同一服务提供，无需另外开 Vite。
- 保持启动终端窗口；按 `Ctrl+C` 或双击 **Stop.command** 停止。停止会等待后台清理活动任务；未完成任务不会自动恢复或被伪装为成功。已保存项目与历史产物保留。
- 重复启动会提示已有启动器；端口8000被其他程序占用时拒绝启动，不自动换端口，也不终止未知进程。Stop通过私有随机令牌控制连接停止自己的服务，不按旧PID或端口杀进程。
- 后台与停止控制连接均仅绑定 `127.0.0.1`。这是无登录的单机工具，不适合局域网共享、公网反向代理或多worker部署。不要改为 `0.0.0.0`。
- 主日志：`var/local-delivery/service.log`；任务日志：所选数据目录的 `runs/<id>/run.log`。启动窗口给出准确路径。

开发命令仍可使用：在 `server/` 运行 `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`，在 `web/` 运行 `npm run dev` 后打开5173。不要与双击交付版本同时占用8000。构建交付的测试命令为 `cd web && npx playwright test -c playwright.delivery.config.ts`（须已有启动器运行，测试会导入样本并创建无模型替身任务）。

## 3. 配置密钥与运行边界

打开本机 `server/.env`，填入 `OPENROUTER_API_KEY=你的密钥`；不要发到聊天、截图或提交 Git。可选 `OPENROUTER_MODEL` 等字段见 [完整配置说明](08-openrouter-setup.md)。环境变量优先于文件；配置文件只读取允许的键值，不作为shell脚本执行。

默认双击启动器不启用真实模型入口，地图、源码、替身任务及历史结果均可用。要启用，在配置密钥并停止服务后，从根目录执行 `REPOLENS_ENABLE_REAL_RUN=1 ./Start.command`。安装、启动、健康检查和打开历史均不会自动调用模型；还必须在页面选择“真实 PocketFlow”并点击“启动真实任务”才会发送 utils 快照内容到 OpenRouter并计费。目前只有固定PocketFlow版本、中文、最多3主题获得支持。

不想允许真实请求，可在终端从根目录执行 `REPOLENS_ENABLE_REAL_RUN=0 ./Start.command`。上游/上传文件仅作为分析输入，不会因导入获得执行权限。macOS隔离能力检查失败即拒绝，不静默降低安全边界。

## 4. 数据位置和备份

默认数据目录为根目录 `var/`，与启动位置无关。数据库 `repolens.sqlite3` 索引源码快照、文件夹卡、运行历史和产物。实际引用文件在 `snapshots/` 与 `runs/`，**只复制数据库不能完整备份**。

1. 双击 Stop.command，等待停止完成。手工启动的开发后台也必须 `Ctrl+C` 停止。
2. 在 Finder 创建自己的备份父文件夹。从 RepoLens 根目录先进入server，再运行备份；把绝对路径换成你自己的、尚不存在的备份目录：

```bash
cd server
.venv/bin/python -m app.backup create '/Users/你的用户名/RepoLens备份/2026-09-22'
```

命令使用默认根目录var；若此前使用自定义数据目录，需在命令前指定同一个 `REPOLENS_DATA_DIR='/绝对路径/数据目录'`。目标父目录必须已存在，目标目录必须不存在。

备份持有与后台相同的数据锁，并兼容旧运行器锁；后台占用时拒绝。它使用 [SQLite backup API](https://www.sqlite.org/backup.html) 生成一致性数据库，复制已登记源码以及历史运行输入、输出、日志和用量记录；检查引用文件哈希、外键、迁移和数据库完整性。备份包含manifest版本、代码Commit、迁移版本及每个文件大小/SHA-256。

不包含：`server/.env`、进程环境密钥、依赖、upstream、测试数据、安装器状态、运行临时home/tmp、provider原始缓存及未登记的孤立目录。复制期间请勿手工修改数据，也不要运行绕过应用锁的自编数据库工具。不要删除 `.data.lock` 或 `.runner.lock` 文件试图“解锁”。

备份是普通目录，可能包含私有源码与模型结果，**不加密**。保存在自己控制的加密磁盘/可靠位置，不上传公共仓库。限额为100000文件、单文件512MiB、合计8GiB；超限、链接、缺文件或哈希不匹配会拒绝，不生成“成功”备份。

## 5. 恢复与验证

恢复前停止服务；使用同一交付版本或明确兼容迁移的代码。当前恢复严格核对当前迁移版本，不自动运行外部备份内的代码或SQL。旧版数据需先在原目录按升级流程启动迁移并重新备份。

从 `server/` 执行：

```bash
.venv/bin/python -m app.backup restore '/Users/你的用户名/RepoLens备份/2026-09-22' '/Users/你的用户名/RepoLens恢复数据'
```

目标必须是**尚不存在的新目录**，即使空目录也拒绝覆盖。先验证清单、路径、链接、SHA-256和数据库引用，再原子发布；失败不替换现有var。恢复不带密钥，需要在本机重新配置。不要覆盖正在运行的数据。

回到根目录，以恢复目录启动：

```bash
REPOLENS_DATA_DIR='/Users/你的用户名/RepoLens恢复数据' ./Start.command
```

在首页重开原项目，点源码行号确认文件可读，从运行历史打开成功产物，刷新再检查一次。仅查看结果不会调用模型。要日常双击使用该恢复目录，可在确认恢复正确且停止服务后，把原 `var/` 在Finder中改名为保留副本，再把恢复目录复制为根目录 `var/`，重新运行Install.command生成安装记录。不要在验证前删除原数据。

## 6. 常见问题

| 提示或现象 | 处理 |
|---|---|
| 缺Python/Node/npm/Git或版本不匹配 | 完成第1节系统工具安装；注意Finder PATH与终端可能不同 |
| 下载/安装超时 | 检查GitHub、PyPI、npm网络；重试Install，不改为随机Commit或未锁定依赖 |
| 已有上游来源/Commit不匹配或有修改 | 先另存个人修改，再手动移走该目录，重跑安装；安装器不会替你丢弃修改 |
| 未安装、源码/锁文件/目录变化 | 停止后重跑Install.command；不要复制他人的venv |
| 端口占用、数据目录被使用 | 停止已识别的旧服务；不要盲杀进程或删除锁文件 |
| 密钥缺失 | 按第3节配置；地图、历史和无模型替身不受影响 |
| 隔离检查未通过 | 检查当前macOS及sandbox-exec；不支持的平台不绕过隔离 |
| 备份拒绝/恢复目标已存在 | 看具体错误；选择新目录，核对原文件完整性，不手工修改manifest“修复”哈希 |
| macOS阻止打开.command | 先确认来源可信，再按[Apple操作说明](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unknown-developer-mh40616/mac)允许本文件；不全局关闭Gatekeeper |

## 7. 三个真实用户任务

招募3位目标用户，使用自己的本地安装或明确记录主持人协助。每人独立完成以下任务，先不演示答案：

1. **找出文件夹用途**：打开PocketFlow，说明 `utils` 的作用，指出哪些描述是源码事实、推断或待核实。记录是否找到、理由和误解。
2. **从页面完成一次运行**：选择模式与参数，启动、观察状态并打开结果。无预算先用明确标识的替身；若做真实运行，应由用户配置密钥、理解数据发送与费用后单独同意。记录模式，不能把替身完成称为模型效果验证。
3. **找到解释的源码依据**：从解释跳到一个文件/符号/行号，说明它如何支持或不能支持那条结论；记录是否理解Commit与快照一致性。

使用 [观察记录模板](../evidence/m6/trial-observation-template.md)。记录原话、耗时、完成/求助/失败、截图或日志位置，不补造反馈。至少3份真实记录及一次有前后证据的反馈迭代后，才能标记“M6全部完成”；技术通过只说明当前环境可交付。
