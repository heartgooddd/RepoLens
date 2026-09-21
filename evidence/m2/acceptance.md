# M2 真实仓库地图验收

日期：2026-09-21。开发起点：`69d5263`（步骤 4），分支 `feat/m2-repository-map`。本次完成步骤 5，验收通过后按 G2 提交、G3 快进合并本地 main；阶段分支保留，未上传远程。未开始 M3。

## 结论

**通过。** 页面可扫描已下载的 PocketFlow 已提交版本，也可通过浏览器目录选择上传相对路径和文件字节；真实快照、目录卡、源码证据进入 SQLite 和 `var/snapshots/`。刷新、首页重开和后台重启后数据仍在。演示工作台独立保留，真实运行按钮明确未接入。

- 后端：**35 项通过**，5.14 秒；包括真实进程重启、源码证据逐条核对、迁移、异常路径、体积边界和失败清理。
- 前端：`npm run build` 通过，含 TypeScript 检查；**12 项浏览器检查通过**，32.8 秒，涵盖 1440×1000 桌面、390×844 窄屏，以及 320 / 390 / 768 / 1440 宽度溢出检查。
- 截图：下方 **15 张**均来自本次实际 React + FastAPI 页面，不使用 M0 样稿或 M1 截图冒充联调结果。

## 操作路径与结果

| 路径 | 实际结果 |
|---|---|
| 输入页 → 扫描 PocketFlow → 真实工作台 | 读取本地 Git HEAD 并保存独立快照；显示真实快照标签、Commit、目录与文件 |
| 根目录 → main.py → `__main__ guard` | 跳到真实源码 L110–111，可见入口条件；函数 `main` 位于 L39 起 |
| 根目录 → flow.py | L12–19 可核对 `create_tutorial_flow`；L24–28 的 `>>` 连接表达式可点选 |
| 根目录 → nodes.py → FetchRepo | L22–29 可核对真实类定义；其他顶层定义也有行号 |
| utils → utils/call_llm.py → call_llm | L128–135 可核对函数定义；目录名推断单独标记，不当作已验证功能 |
| 目录选择 → 上传合成 src/start.py | 保存真实上传文件，页面显示函数 `launch` 与对应行号；`.env` 不上传、不进入快照 |
| 无定义的 notes.txt 所在目录 | 标为“职责待核实”，不由文件名编造职责 |
| 刷新 / 返回首页 → 已保存项目 → 重开 | URL 中的项目 ID 从 SQLite 读回，源码通过哈希校验 |
| 点击“查看独立演示模式” | 进入原 M1 演示，标签明确；模拟运行不写真实项目或调用模型 |

目录按点击逐级展开，避免大量文档子目录占满首屏。左侧目录、中间证据和源码、右侧固定运行窗口保留原有浅色青绿层次。窄屏纵向排列，顶部区域跳转可定位。长源码区域允许水平滚动，页面本身无横向溢出。

## 默认数据库的实际重启验证

不仅测试隔离数据库，也在本机 `var/repolens.sqlite3` 保存并验证：

- 来源 Commit：`05b24cbbb0fe409c5e23c9791f0342f07524ffdc`。
- 项目 ID：`9fc3751c-93e8-429a-bbdb-9383a7f7685e`。
- 快照 ID：`5a4a6d2b-049f-440d-8544-8c49fec62e8d`。
- 199 个保留文本文件、23 张目录卡；后台跳过 8 个排除／不支持的条目。
- 停止原 Uvicorn 进程，再用 README 命令启动；健康检查返回 schema_version=2。
- 重启前后完整项目 JSON（键排序）的 SHA-256 相同：`6b446fa0ef12dfb900f435749e0cdcb41df2ffe0e6cb7e2301dc79d032beae51`。
- 重启后 `flow.py` 读取成功，仍含 `fetch_repo >> identify_abstractions`。随后 Chrome 在 5173 页面刷新、重选 flow.py 成功，截图见下方“默认库重启后”。

可在当前本机打开：[已保存的 PocketFlow 项目](http://127.0.0.1:5173/#/projects/9fc3751c-93e8-429a-bbdb-9383a7f7685e)。此链接依赖本机服务和被忽略的 `var/` 数据；其他电脑需自行导入生成自己的项目 ID。

## 异常与边界验收

| 情境 | 验证结果 |
|---|---|
| 空列表、仅环境文件、二进制内容 | 后台 422 `empty_directory`；前端过滤后为空时提示，不创建空项目 |
| `../`、绝对路径、盘符、反斜杠、空段、NUL | 后台 422 `invalid_path`，未写数据库或快照 |
| 重复／大小写冲突、文件与目录同名 | 422 `duplicate_path` / `path_conflict` |
| 单文件 >1 MiB | 413 `file_too_large`，浏览器也在上传前检查并显示提示 |
| 总内容 >8 MiB、请求体 >12 MiB | 413；请求体上限在 JSON 解析前检查 |
| 501 个上传条目 | 422 `invalid_request`；前端保留文件数超限时提前提示 |
| 修改或删除已保存源码 | 409 `snapshot_changed` / `snapshot_missing`，不把旧记录冒充当前文件 |
| 未登记文件 / 符号链接替换 | 404 / 409，拒绝读取 |
| 异常 Origin、非 JSON、错误 Base64 | 403 / 415 / 422，不回显上传内容 |
| 数据库写入模拟失败 | 元数据事务回滚，清理本次未成功登记的快照目录 |
| 从版本 001 升到 002、重复迁移 | 已有项目保留；重复执行无破坏；修改历史迁移或失败 SQL 均被验证拒绝／回滚 |

非法路径的浏览器验收只改写**发出的请求体**，仍由真实后台验证并返回错误，前端显示实际响应；没有伪造成功数据或错误响应。浏览器上传使用临时合成源码目录，页面中 `upload-*` 为该实际选择的目录名。

纯空目录在部分浏览器中不触发文件选择事件；无法把取消选择与纯空目录可靠区分，界面已给出说明。API 空输入与过滤后空输入均有明确状态。

## 实际截图

| 内容 | 桌面 | 窄屏 |
|---|---|---|
| 真实项目输入页 | [查看](real-home-desktop.png) | [查看](real-home-narrow.png) |
| PocketFlow 流程文件 | [查看](real-flow-desktop.png) | [查看](real-flow-narrow.png) |
| utils 定义与名称推断 | [查看](real-utils-desktop.png) | [查看](real-utils-narrow.png) |
| 浏览器上传后的真实项目 | [查看](uploaded-project-desktop.png) | [查看](uploaded-project-narrow.png) |
| 过滤后空目录提示 | [查看](empty-directory-desktop.png) | [查看](empty-directory-narrow.png) |
| 超大文件提示 | [查看](oversized-file-desktop.png) | [查看](oversized-file-narrow.png) |
| 后台非法路径错误 | [查看](invalid-path-desktop.png) | [查看](invalid-path-narrow.png) |

[默认库重启并刷新后的实际工作台](live-saved-project.png)。截图中的上游源码许可证见 [THIRD_PARTY_NOTICES](../../web/THIRD_PARTY_NOTICES.md)。

## 复现命令

环境沿用步骤 4：macOS Apple Silicon、Python 3.14.6、SQLite 3.53.3；前端 Node 22.23.0、Chrome。依赖锁文件未改变，本步无新增第三方包。

在 `server/`：

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m app.migrate
.venv/bin/python -m app.migrate
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

迁移两次均返回版本 2。后端测试在 `var/tests/` 的隔离目录执行，包含真实 Uvicorn 子进程停止和重启。已有两个依赖弃用提示仍存在：Starlette TestClient 的 HTTPX 适配和 AnyIO BlockingPortal 别名；未隐藏，均不影响本次结果。

在 `web/`：

```bash
npm run build
npm run test:e2e
npm run dev
```

浏览器测试自动使用 5174 前端与 8001 隔离后台，数据不污染默认开发库；普通开发使用 5173 和 8000。截图原始文件在忽略的 `web/test-results/`，本次挑选到此目录。Git 检查：`git diff --check`、暂存清单检查、`git check-ignore var/repolens.sqlite3 server/.venv/pyvenv.cfg`；本地文档链接已回读。

## 剩余限制

- 无阻塞 M2 验收的问题。职责说明为静态事实与名称线索，未提供模型语义总结、完整调用图或真实执行验证；M3 尚未开始。
- 只处理规定大小范围内的 UTF-8 文本，不保存二进制、未知格式或空目录。内置只读取已提交版本。目录上传不会携带符号链接对象；浏览器如何处理源目录中的链接依赖其实现。
- 过滤覆盖常见敏感文件名，不等于识别源码中的所有硬编码密钥。导入器不联网、不执行目标项目。
- 每次导入创建独立项目；重复导入复用、删除 UI、版本历史大规模分页和跨文件语义关系仍未提供。
- 文件与数据库跨介质写入在普通异常时回滚／清理；进程硬中断可能留下未登记的孤立快照目录。不会自动清理用户数据。
- 仅验证本机 Chrome 与窄屏模拟，不代表真机 Safari／Firefox 或云端多用户部署已验证。所有提交仅在本机；运行数据不随 Git 保存。
