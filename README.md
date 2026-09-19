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

当前已完成规划、静态研究、M0 视觉样稿和本地 Git 基线；产品 `web/`、`server/` 与数据库尚未建立。已确定以 M0 样稿作为 M1 的视觉起点；下一步按创作总指南步骤 2 开始页面开发。

## 目录

- `docs/`：RepoLens 自身的产品蓝图与实施路线。
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
