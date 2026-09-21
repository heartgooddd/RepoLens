# RepoLens

开源 AI 项目拆解与学习平台工作区。

## 从这里开始

**本地使用：[首次安装、双击启停、配置密钥、备份恢复与试用](docs/05-local-setup-and-trial.md)。**

macOS 安装好 Git、Python3.14、Node22.12+（22.x）后，双击根目录 **Install.command**，完成后双击 **Start.command**，打开 http://127.0.0.1:8000/；双击 **Stop.command** 停止。首次安装会从官方来源获取固定Commit的PocketFlow，并安装两个独立Python环境和前端锁定依赖，不依赖开发机器遗留的upstream。

默认不开启真实模型入口。密钥写入本机 `server/.env`；需要真实运行时，停止后从根目录执行 `REPOLENS_ENABLE_REAL_RUN=1 ./Start.command`，再从页面选择并启动。启动与查看历史不调用模型。备份须停服，包含一致性SQLite及引用文件；密钥不纳入备份，恢复只允许新目录。

- **下一步入口：[创作总指南](docs/00-creation-guide.md)**：按步骤推进，每一步都有可复制的 Codex 提示词、交付位置、验收条件和 Git 时机。
- [产品与页面蓝图](docs/01-product-blueprint.md)：目标用户、页面布局、用户流程和两种运行方式。
- [实施路线与目录操作说明](docs/02-delivery-roadmap.md)：M0–M6 里程碑、验收条件、文件夹分工和下一步操作。
- [系统架构与数据保存](docs/03-system-architecture-and-storage.md)：React、FastAPI、SQLite 与运行文件的关系，以及数据库接入时机。
- [Git 操作手册](docs/04-git-workflow.md)：首次初始化、阶段分支、提交、合并、可选 GitHub 上传和日常修改。
- [工作台视觉样稿](docs/mockups/01-workbench-concept.html)：可在浏览器切换输入页与工作台的设计概念，尚未连接后台；也可直接查看[输入页截图](docs/mockups/01-home-concept.png)和[工作台截图](docs/mockups/01-workbench-concept.png)。
- [PocketFlow 第一轮解析笔记](notes/00-pocketflow-first-pass.md)：当前上游样本的静态阅读记录。

当前功能已覆盖 **M5已登记操作配方及M6本地交付**。页面支持公开 GitHub 固定版本导入、真实地图、配方生成参数表单、运行日志/取消/退出码、历史结果与产物预览。首份配方是 `pocketflow-tutorial@1`；后台通过 macOS 沙箱执行固定入口，快照作为只读分析输入。M6技术结果见 [交付验收](evidence/m6/acceptance.md)；**3位真实用户试用仍为0/3，未完成，反馈迭代未完成**，不把自动化验证当用户反馈。

M3 从页面启动一次 `utils / 中文 / 3主题` 真实任务，模型 `deepseek/deepseek-v4-flash`，7次模型调用全部成功，无重试，API报告费用 **$0.0034756449**。数据库、输出、页面下载一致，后台重启后历史结果可重开。见 [真实验收与截图](evidence/m3/acceptance.md)、[实际生成索引](evidence/m3/real-output/index.md)、[任务配置与接口](docs/07-task-runner.md)。M5 沿用此实跑证据，本轮未发起付费模型请求；沙箱内 worker 与页面运行使用离线响应测试。

M4 实际远程读取官方 PocketFlow，固定 Commit `05b24cbbb0fe409c5e23c9791f0342f07524ffdc`；重复导入复用同一源码快照。模型结果缓存另按模型、提示词、配方版本和全部参数隔离。远程导入不会执行仓库代码，任意远程仓库也不会自动获得真实运行能力。见 [M4验收](evidence/m4/acceptance.md)和[导入说明](docs/09-github-import.md)。下一步为真实试用与证据驱动反馈迭代；所有提交只保存在本机。

## 开发方式：单独启动后台

在另一个终端运行：

```bash
cd '/Users/Vibe coding/AI_product/AI Program/RepoLens/server'
REPOLENS_ENABLE_REAL_RUN=1 .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 **http://127.0.0.1:8000/docs** 查看健康检查、项目导入、源码以及任务／日志／产物接口。新环境列表为空；本机已经保存本次验证的 PocketFlow 快照。`Ctrl+C` 停止；重启会继续使用同一 SQLite 数据库；成功结果可重开，未完成任务标记为“中断”，不自动续跑。前端仍按下方方式单独启动。

本机 Python 3.14.6 的独立虚拟环境已安装。首次在其他环境安装，在 `server/` 执行 `python3.14 -m venv .venv` 和 `.venv/bin/python -m pip install -r requirements.lock`。后台启动会自动迁移；也可执行 `.venv/bin/python -m app.migrate`。验证命令为 `.venv/bin/python -m pytest -q`。

PocketFlow 依赖另装在 `server/pocketflow/.venv/`，固定来源、Commit、许可证和安装命令见 [PocketFlow 环境说明](server/pocketflow/README.md)。替身任务只使用后台环境；真实任务使用PocketFlow隔离环境和固定适配入口。`REPOLENS_ENABLE_REAL_RUN=1` 开启真实选项，省略则仅替身；本机 `server/.env` 的模型配置读取方式见 [OpenRouter设置](docs/08-openrouter-setup.md)。密钥不显示、不提交；填写密钥不会自行启动任务。后台保持单进程，不添加 `--workers`。

实际数据库位于被忽略的 `var/repolens.sqlite3`，迁移与模型在 `server/`，数据不会随 Git 提交保存。详细依赖、接口字段、数据目录和迁移规则见 [后台 README](server/README.md)。

## 开发方式：单独打开页面

在终端运行：

```bash
cd '/Users/Vibe coding/AI_product/AI Program/RepoLens/web'
npm run dev
```

打开 **http://127.0.0.1:5173/**。直接进入示例工作台使用 http://127.0.0.1:5173/#/workspace 。保持终端运行；按 `Ctrl+C` 停止。端口固定为 5173，占用时会报错，不会悄悄换地址。

本机已安装依赖；首次在其他环境使用或锁文件变化后，先在 `web/` 执行 `npm ci`。开发时记录的环境为 Node.js 22.23.0、npm 10.9.8，依赖为 React 19.3.0、TypeScript 7.0.2、Vite 8.3.0，具体版本由 `web/package-lock.json` 锁定。Node 要求为 20.19+ 或 22.12+，见 [Vite 官方说明](https://vite.dev/guide/)。

1. 先启动后台，再启动前端。在首页粘贴完整公开 GitHub 仓库地址并点击“读取公开仓库”；也可点击“扫描 PocketFlow 样本”读取本地上游 Git HEAD，或点击“选择本地文件夹”上传选定目录。
2. 工作台显示“真实快照”。点击目录逐级展开，选择 `main.py`、`flow.py`、`nodes.py` 或 `utils` 内的文件，点击定义／入口行号查看已校验的源码。
3. 刷新页面，或停掉后台再启动，仍可打开相同项目 URL；首页“已保存的项目”也可重开。数据位于 `var/`，不是浏览器缓存。
4. 在真实工作台右侧选择“真实 PocketFlow”，确认 `utils / 中文 / 3主题`，点击“启动真实任务”。这会使用本机OpenRouter配置并产生费用；当前只允许固定PocketFlow快照，最多3主题。成功后点击“查看真实结果”，切换章节或下载。只查看历史不会再次调用模型。
   无模型验证请选择“替身验证”，可用成功／失败／慢速情境检查任务行为，输出明确标为固定内容。
5. 已有验收结果可直接打开 [PocketFlow真实项目](http://127.0.0.1:5173/#/projects/9fc3751c-93e8-429a-bbdb-9383a7f7685e)，点击“查看真实结果”，不必再启动。刷新后从“运行历史”重开结果。修改当前表单不改变历史任务参数。未成功任务不展示成功产物；后台关闭时活动任务会中断。
6. 想对比原有交互，点击“进入 PocketFlow 示例工作台 · 演示”或右侧“打开 M1 浏览器演示”。这个独立入口仍使用浏览器内预置数据。

真实地图通过同源 `/api` 代理连接 `127.0.0.1:8000`，默认前端地址仍是 5173；如需改后端地址，在启动 Vite 时设置 `REPOLENS_API_PROXY`（仅本机配置，不是用户仓库输入）。生产构建不自带 Python 后台或代理，外部部署尚未配置；本地 `npm run preview` 也配置了相同代理。

上传和GitHub归档仅保留支持的UTF-8文本文件，排除环境／常见凭据、依赖、构建和二进制资源；单文件≤1MiB、总保留内容≤8MiB、最多500个文件。GitHub远程解析／下载合计限制30秒，另限制16MiB压缩、2000条目和32MiB解包，并拒绝越界路径与链接。规则、请求和错误码详见 [后台 README](server/README.md)。目录名推断单独标注，证据不足的职责标为待核实。

演示模式的进度、日志和结果仍为预置数据，不调用模型；刷新会清空演示状态。窄屏用顶部区域按钮定位解释与运行窗口。

## 开发与检查

以下命令都在 `web/` 执行：

```bash
npm run typecheck
npm run build
npm run test:e2e
```

构建命令同时检查 TypeScript，产物位于被忽略的 `web/dist/`。浏览器测试使用本机 Google Chrome，自动启动隔离前后端及无网络模型响应夹具；测试数据位于 `var/tests/`，不修改开发数据库。其他电脑若未安装 Chrome，可先运行 `npx playwright install chrome`。当前验证见 [M5验收](evidence/m5/acceptance.md)；历史阶段证据仍分别保留。

构建后如需检查生产产物，运行 `npm run preview` 并打开 http://127.0.0.1:4173/ 。

## 目录

- `docs/`：RepoLens 自身的产品蓝图与实施路线。
- `web/src/pages/`：输入页与工作台；`web/src/components/`：文件夹、解释、表单、结果组件。
- `web/src/demo/`：固定演示样本与预置章节；`web/src/hooks/`：模拟运行状态；`web/tests/`：浏览器关键路径检查。
- `web/src/api/`：真实 API 客户端；`RepositoryPage` 展示真实工作台，演示数据继续独立保存。
- `server/`：FastAPI、本地／GitHub导入、静态扫描、SQLite迁移、源码接口、任务与产物服务；`server/app/prompts/` 存职责补充提示词。
- `server/pocketflow/`：固定上游版本与独立依赖环境说明、完整锁文件。
- `scripts/` 与根目录 `.command`：可复现安装、本机服务的受控启停；不执行用户导入的源码。
- `var/`：被忽略的数据库、快照和运行数据；不随 Git 提交。
- `upstream/`：候选上游项目目录；PocketFlow 已下载，其余目录保持为空。
- `notes/`：逐项目拆解笔记。
- `evidence/`：Commit、源码位置、运行日志与验证证据。

## 待选研究项目

| 文件夹 | 官方仓库 | 研究重点 |
|---|---|---|
| `upstream/pocketflow-codebase-knowledge/` | https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge | 最小完整代码分析管线 |
| `upstream/aider/` | https://github.com/Aider-AI/aider | Repo Map、符号关系与重要文件排序 |
| `upstream/deepwiki-open/` | https://github.com/AsyncFuncAI/deepwiki-open | 索引、缓存、失败恢复与产品化 |

## 当前选择

- 已下载：`upstream/pocketflow-codebase-knowledge/`
- 锁定 Commit：`05b24cbbb0fe409c5e23c9791f0342f07524ffdc`
- 许可证：MIT
- 第一轮静态解析记录：`notes/00-pocketflow-first-pass.md`
