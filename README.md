# RepoLens

开源 AI 项目拆解与学习平台工作区。

## 从这里开始

- **下一步入口：[创作总指南](docs/00-creation-guide.md)**：按步骤推进，每一步都有可复制的 Codex 提示词、交付位置、验收条件和 Git 时机。
- [产品与页面蓝图](docs/01-product-blueprint.md)：目标用户、页面布局、用户流程和两种运行方式。
- [实施路线与目录操作说明](docs/02-delivery-roadmap.md)：M0–M6 里程碑、验收条件、文件夹分工和下一步操作。
- [系统架构与数据保存](docs/03-system-architecture-and-storage.md)：React、FastAPI、SQLite 与运行文件的关系，以及数据库接入时机。
- [Git 操作手册](docs/04-git-workflow.md)：首次初始化、阶段分支、提交、合并、可选 GitHub 上传和日常修改。
- [工作台视觉样稿](docs/mockups/01-workbench-concept.html)：可在浏览器切换输入页与工作台的设计概念，尚未连接后台；也可直接查看[输入页截图](docs/mockups/01-home-concept.png)和[工作台截图](docs/mockups/01-workbench-concept.png)。
- [PocketFlow 第一轮解析笔记](notes/00-pocketflow-first-pass.md)：当前上游样本的静态阅读记录。

当前已完成步骤 4：`feat/m2-repository-map` 已建立 FastAPI、SQLite 保存与迁移基础，验证记录见 [M2 基础检查](docs/05-m2-foundation-check.md)。本步保留 M2 分支，尚未合并 main。M1 React 演示页面已在本地 `main` 验收，实际截图见 [M1 验收记录](evidence/m1/acceptance.md)。页面仍使用演示数据；真实仓库导入和前后端联调留到步骤 5。

## 启动后台（M2 基础）

在另一个终端运行：

```bash
cd '/Users/Vibe coding/AI_product/AI Program/RepoLens/server'
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 **http://127.0.0.1:8000/docs** 查看并试用健康检查、项目列表和项目详情接口。默认列表为空。`Ctrl+C` 停止；重启会继续使用同一 SQLite 数据库。前端仍按下方方式单独启动。

本机 Python 3.14.6 的独立虚拟环境已安装。首次在其他环境安装，在 `server/` 执行 `python3.14 -m venv .venv` 和 `.venv/bin/python -m pip install -r requirements.lock`。后台启动会自动迁移；也可执行 `.venv/bin/python -m app.migrate`。验证命令为 `.venv/bin/python -m pytest -q`。

实际数据库位于被忽略的 `var/repolens.sqlite3`，迁移与模型在 `server/`，数据不会随 Git 提交保存。详细依赖、接口字段、数据目录和迁移规则见 [后台 README](server/README.md)。

## 打开页面

在终端运行：

```bash
cd '/Users/Vibe coding/AI_product/AI Program/RepoLens/web'
npm run dev
```

打开 **http://127.0.0.1:5173/**。直接进入示例工作台使用 http://127.0.0.1:5173/#/workspace 。保持终端运行；按 `Ctrl+C` 停止。端口固定为 5173，占用时会报错，不会悄悄换地址。

本机已安装依赖；首次在其他环境使用或锁文件变化后，先在 `web/` 执行 `npm ci`。开发时记录的环境为 Node.js 22.23.0、npm 10.9.8，依赖为 React 19.3.0、TypeScript 7.0.2、Vite 8.3.0，具体版本由 `web/package-lock.json` 锁定。Node 要求为 20.19+ 或 22.12+，见 [Vite 官方说明](https://vite.dev/guide/)。

1. 点击“进入 PocketFlow 示例工作台”，选择左侧目录或入口文件。
2. 点击中间的文件卡片，查看预置源码片段；“在 GitHub 查看这个版本”会打开外部源码页面。
3. 在右侧调整语言、最大主题数和演示情境，点击“开始演示运行”。
4. 成功后点击“查看演示结果”，切换预置章节；失败情境会模拟超时，可重试成功演示。也可停止或清空本次演示。

所有说明、进度、日志和结果均为演示数据。语言与主题数只控制预置章节的展示；页面没有 API、模型调用或文件写入。刷新或返回输入页会清空工作台状态，浏览器前进/后退可切换两个页面。窄屏用顶部区域按钮直达解释与运行窗口。

## 开发与检查

以下命令都在 `web/` 执行：

```bash
npm run typecheck
npm run build
npm run test:e2e
```

构建命令同时检查 TypeScript，产物位于被忽略的 `web/dist/`。浏览器测试使用本机 Google Chrome，自动在 `127.0.0.1:5174` 启动测试服务器，覆盖桌面与窄屏；该端口需空闲。其他电脑若未安装 Chrome，可先运行 `npx playwright install chrome`。测试临时截图与失败轨迹在被忽略的 `web/test-results/`；当前验收证据见 [M1 验收记录](evidence/m1/acceptance.md)，早期开发记录见 [步骤 2 检查](evidence/m1/step-2-check.md)。

构建后如需检查生产产物，运行 `npm run preview` 并打开 http://127.0.0.1:4173/ 。

## 目录

- `docs/`：RepoLens 自身的产品蓝图与实施路线。
- `web/src/pages/`：输入页与工作台；`web/src/components/`：文件夹、解释、表单、结果组件。
- `web/src/demo/`：固定演示样本与预置章节；`web/src/hooks/`：模拟运行状态；`web/tests/`：浏览器关键路径检查。
- `server/`：FastAPI、SQLite 模型、迁移、读取接口与持久化测试。
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
