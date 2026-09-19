# RepoLens Git 操作手册

> 配合 [00 创作总指南](00-creation-guide.md)使用。G0 已在当前 RepoLens 目录完成，本地 `main` 保存了规划基线；尚未上传远程仓库。其余命令供后续阶段按需执行。

## 先分清这些操作

| 命令 | 在做什么 | 何时使用 |
|---|---|---|
| `git init` | 为 RepoLens 建立本地版本记录 | 开始产品开发前，只做一次 |
| `git status` / `git diff` | 查看已有改动 | 每次开始与结束工作时 |
| `git switch -c` | 从当前版本新建开发分支 | 每个里程碑第一次开工 |
| `git add` | 挑选本次要保存的文件 | 本步验证后、提交前 |
| `git commit` | 在本机保存一个版本 | 一个可解释的小步骤完成后 |
| `git merge --ff-only` | 把通过验收的阶段推进到 main | 里程碑验收通过后 |
| `git push` | 把本地提交传到指定 GitHub 仓库 | 远程账号、地址和可见性已确定后 |

修改文件与提交文件是两个动作。提交在本机完成；上传 GitHub 需要独立的远程地址与授权。[Git 初始化文档](https://git-scm.com/docs/git-init)、[Git 推送文档](https://git-scm.com/docs/git-push)。

所有命令在当前根目录执行。每次打开一个新终端先运行：

```bash
cd '/Users/Vibe coding/AI_product/AI Program/RepoLens'
pwd
```

输出应是上面的 RepoLens 路径。`upstream/pocketflow-codebase-knowledge/` 有它自己的 Git 仓库；给 RepoLens 提交时不要进入该目录。

## G0：首次初始化与保存规划基线（步骤 1）

### 1. 先检查是否已经初始化

```bash
git rev-parse --show-toplevel
```

若提示当前不是 Git 仓库，且已确认工作目录正确，继续首次初始化。若已经输出 RepoLens 根目录，直接检查 `git status` 和 `git log -1`，沿用已有状态；若输出父目录，先核对仓库归属，不直接在其中建立另一套仓库。

### 2. 创建根目录 `.gitignore`

这部分是文件内容，不是终端命令。让 Codex 创建；若已有此文件，合并规则并保留现有内容。

```gitignore
/upstream/
/var/
**/node_modules/
/web/dist/
**/.venv/
**/__pycache__/
*.py[cod]
**/.pytest_cache/
**/.mypy_cache/
**/.ruff_cache/
**/.env
**/.env.*
!**/.env.example
*.pem
*.key
.DS_Store
```

`.env.example` 只放变量名和无密钥示例。`package-lock.json`、后端依赖锁文件、数据库迁移代码、产品模型提示词需要提交。实际 SQLite 数据库和原始运行产物位于被忽略的 `var/`。

### 3. 初始化并确认身份

仅当根目录还没有仓库时执行：

```bash
git init -b main
git config --get user.name
git config --get user.email
git check-ignore upstream/pocketflow-codebase-knowledge/README.md var/repolens.sqlite3
```

最后一条应输出两个被忽略的路径。姓名或邮箱无输出时，先由用户提供真实提交身份；需要配置时使用当前仓库的 `git config --local user.name` 和 `git config --local user.email`，由 Codex 填入用户给定的值。本手册不提供可误用的虚构身份。

### 4. 检查并建立第一次提交

以下路径已存在或由本步创建。执行前让 Codex 更新本步状态；只把本次确定的资料纳入提交。

```bash
git status --short
git add -- .gitignore README.md docs notes
git diff --cached --stat
git diff --cached --name-only
git diff --cached --check
```

确认清单只有规划、样稿、研究笔记等预期内容，没有上游仓库或密钥，再执行：

```bash
git commit -m "docs: establish RepoLens planning baseline"
git status --short
git log -1 --oneline
```

预期：出现首个提交；没有未处理的本次改动。若仓库还有用户的无关改动，单独说明并保留。身份错误或检查失败时修正后重试该步，不重新运行整套初始化。

## G1：每个里程碑开始时建立分支

前提：上一个阶段已合并到 main，准备开始下一阶段。先看清当前改动；有尚未完成的阶段就继续该分支，不切换或覆盖它。

```bash
git status --short --branch
git branch --list
git log -3 --oneline
```

确认可以开始新阶段后，只运行对应阶段的这一组命令：

| 阶段 | 先切到主线 | 第一次创建分支 |
|---|---|---|
| M1，步骤 2 | `git switch main` | `git switch -c feat/m1-web` |
| M2，步骤 4 | `git switch main` | `git switch -c feat/m2-repository-map` |
| M3，步骤 6 | `git switch main` | `git switch -c feat/m3-pocketflow-runner` |
| M4，步骤 8 | `git switch main` | `git switch -c feat/m4-github-import` |
| M5，步骤 9 | `git switch main` | `git switch -c feat/m5-action-recipes` |
| M6，步骤 10 | `git switch main` | `git switch -c feat/m6-local-delivery` |

恢复工作时用 `git switch feat/m1-web` 这类不带 `-c` 的命令，且先确认工作区改动可以保留在正确分支。分支已存在时不要用强制重建选项。[Git 分支切换文档](https://git-scm.com/docs/git-switch)。

## G2：每个小步骤完成后提交

先执行相关构建、功能验证并记录结果；提交不代替验证。以下是所有提交共用的检查：

```bash
git status --short
git diff --stat
git diff --check
```

下面按实际步骤选暂存范围。只有目录已存在且其中改动全属于本步时，才使用整目录命令；混有用户改动时，改为 `git add --` 后逐个填写本步的实际文件，或用 `git add -p` 选择片段。

| 步骤 | 通常的暂存命令 | 提交消息建议 |
|---|---|---|
| 2，M1 页面 | `git add -- .gitignore web docs README.md` | `feat: build RepoLens web workspace` |
| 3，M1 验收 | `git add -- web docs README.md evidence/m1` | `fix: complete M1 interaction acceptance` |
| 4，M2 数据基础 | `git add -- .gitignore server docs README.md` | `feat: add API and SQLite persistence` |
| 5，M2 联调 | `git add -- web server docs README.md evidence/m2` | `feat: connect repository map to persisted data` |
| 6，M3 任务 | `git add -- .gitignore web server docs README.md` | `feat: add PocketFlow task lifecycle` |
| 7，M3 实跑 | `git add -- web server docs README.md evidence/m3` | `feat: verify PocketFlow generation from the UI` |
| 8，M4 导入 | `git add -- web server docs README.md evidence/m4` | `feat: import pinned GitHub snapshots` |
| 9，M5 配方 | `git add -- web server docs README.md evidence/m5` | `feat: register verified project actions` |
| 10，M6 交付 | `git add -- .gitignore scripts web server docs README.md evidence/m6` | `feat: package local delivery and trial workflow` |

若本步新建许可证说明或其他根目录文件，也要按实际路径补入。暂存后检查：

```bash
git diff --cached --stat
git diff --cached --name-only
git diff --cached --check
```

检查内容时不要将疑似密钥打印或复制到聊天。确认暂存内容都是本步预期改动，再提交。例如步骤 2：

```bash
git commit -m "feat: build RepoLens web workspace"
git log -1 --oneline
git status --short
```

其他步骤用表中对应消息。若只有文档或验收记录发生变化，提交消息按实际内容调整；没有改动就不提交。不要通过空提交把步骤伪装成已经完成。

## G3：里程碑验收通过后合并 main

步骤 3、5、7、8、9、10 用此流程。前提：相关代码和验收记录已经提交，当前工作区没有未处理改动。以 M1 为例：

```bash
git status --short --branch
git switch main
git merge --ff-only feat/m1-web
git log -3 --oneline
git status --short --branch
```

其他里程碑只替换合并行：

| 阶段 | 对应合并命令 |
|---|---|
| M2 | `git merge --ff-only feat/m2-repository-map` |
| M3 | `git merge --ff-only feat/m3-pocketflow-runner` |
| M4 | `git merge --ff-only feat/m4-github-import` |
| M5 | `git merge --ff-only feat/m5-action-recipes` |
| M6 | `git merge --ff-only feat/m6-local-delivery` |

`--ff-only` 适用于当前按阶段顺序开发的方式；两边历史分叉时会拒绝合并。遇到拒绝，先查看 `git log --oneline --graph --all -15`，由 Codex 核对差异再处理，不用强推或重置覆盖历史。阶段分支可先保留。[Git 合并文档](https://git-scm.com/docs/git-merge)。

合并完成的预期结果：当前在 main，能够启动刚验收的版本，状态与路线图一致。

## G4：上传 GitHub（可选）

只有用户指定远程仓库或明确要求创建后才执行。`git init`、`git commit` 不会自动帮你创建 GitHub 仓库。第一次上传前检查：

```bash
git status --short --branch
git remote -v
git log --oneline main -5
git ls-files
```

由 Codex 核对整段待上传历史和文件清单。`upstream/`、`var/`、密钥不应被追踪；`.gitignore` 不会清除已经提交的历史，发现误提交应先处理。

**没有 origin：**用户先提供真实仓库地址。执行 `git remote add origin` 时后接该真实地址；地址未知时不提供可直接运行的占位命令。仓库已有内容时先 fetch 并比较历史；不要按空仓库处理。

**已有 origin：**先确认它就是用户指定目标，不静默改成另一个仓库。目标为空或历史一致、且用户已授权上传后：

```bash
git push -u origin main
git rev-parse main
git ls-remote origin refs/heads/main
```

核对本地与远程 main 的提交编号相同。后续 main 有新的已验收提交时可执行 `git push origin main`；远程有别人的新提交时先比较再整合，不强推。

代码上传完成后，网页仍需独立部署；数据库和 `var/` 也不会被这条命令备份。

## G5：已完成阶段的日常修改

已有项目后再修改视觉、文档或修复问题，用独立小分支。示例：修复运行错误提示。先核对工作区，确认可以开始新改动后执行：

```bash
git switch main
git switch -c fix/run-error-message
```

完成修改和相应验证，按照 G2 精确暂存并提交：

```bash
git commit -m "fix: clarify run failure messages"
git switch main
git merge --ff-only fix/run-error-message
```

分支名应描述本次实际任务。若分支已存在且该任务未完成，恢复已有分支；若是新的同类修复，使用不同的具体名字。

## G6：想看旧版本，或怀疑做错了

先做只读检查：

```bash
git status --short --branch
git log --oneline --graph --all -15
git diff
```

把问题和想恢复的效果告诉 Codex，由它核对相关提交。已提交的错误通常可以用一条新的修复提交纠正；本指南不要求用清空工作区或强制覆盖历史的命令。没有被追踪的运行数据库和输出文件要靠产品的数据备份流程恢复。
