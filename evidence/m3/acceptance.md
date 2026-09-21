# M3 步骤 7：真实流程验收通过

日期：2026-09-21。起点 `7b6a819`，在 `feat/m3-pocketflow-runner` 完成接入、验证和修复。真实任务通过；本步按 G2 保存代码与筛选证据，按 G3 快进合并到本机 main，不上传远程，不开始 M4。

## 1. 本次真实任务

| 项目 | 实际结果 |
|---|---|
| 配置 | OpenRouter；本机 Key 已配置，未输出密钥；没有重复短请求测试 |
| 请求模型与7次返回模型 | `deepseek/deepseek-v4-flash` |
| 任务 ID | `1acf3d68-c857-4acf-89d9-bee17f98c512` |
| 项目 ID | `9fc3751c-93e8-429a-bbdb-9383a7f7685e` |
| 快照 ID | `5a4a6d2b-049f-440d-8544-8c49fec62e8d` |
| 来源 | https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge |
| 上游 Commit | `05b24cbbb0fe409c5e23c9791f0342f07524ffdc`；MIT，Copyright (c) 2025 Zachary Huang；上游工作区未修改 |
| 参数 | `mode=pocketflow`，`scope=utils`，`language=zh`，`topics=3` |
| 输入 | 已登记快照中的4个utils文本文件；复制前核对字节数与SHA-256，未执行输入代码 |
| 时间 | 2026-09-21T14:26:15.529564Z → 2026-09-21T14:28:57.236355Z（北京时间22:26:15→22:28:57，约162秒） |
| 结果 | succeeded，exit_code=0；中文3章＋索引，另有职责、引用校验、用量3份JSON |
| 模型调用 | 7次，全部HTTP200且finish_reason=stop；无重试、无自动fallback |
| 用量 | 输入45317、输出7855、合计53172 token |
| 费用 | API报告合计 **$0.0034756449**；不含此前独立短请求费用，不作为未来价格保证 |
| 职责提示词 | `server/app/prompts/folder-responsibility-v1.md`；实际调用1次 |

本次只从页面点击一次“启动真实任务”，当前SQLite中只有1条pocketflow模式任务。模型7次调用依次为提取主题、分析关系、排列章节、写3章、职责引用。没有为失败或取消测试消耗真实模型额度。

实际结果副本：[索引](real-output/index.md)、[本地文件爬取器](real-output/01_本地文件爬取器_.md)、[远程仓库文件爬取器](real-output/02_远程仓库文件爬取器_.md)、[LLM调用器](real-output/03_llm调用器_.md)、[引用校验](real-output/verified-claims.json)、[模型用量](real-output/model-usage.json)。副本与已登记产物字节一致，未改写模型内容；`.gitattributes` 仅对 real-output 关闭换行转换与空白检查，保留模型原文中的行尾空白；来源快照信息由适配器在生成时补入索引。

原始输入、日志、响应与产物保留在被忽略的 `var/runs/1acf3d68-c857-4acf-89d9-bee17f98c512/`；数据库仍为 `var/repolens.sqlite3`。验收副本包含上游MIT源码引用，不是独立原创代码，许可证原文保留于固定上游 `LICENSE`，项目的[第三方声明](../../web/THIRD_PARTY_NOTICES.md)保留归属。

## 2. 页面与持久化验证

1. 真实项目页切换“真实 PocketFlow”，确认utils／中文／3主题，在页面点击启动。范围和语言锁定；替身仍是单独选项。
2. 页面显示真实处理中、实际阶段与持久日志，表单在运行时禁用；完成后打开真实结果。通过查看日志确认7次模型调用和FolderResponsibilities阶段。
3. 1440×1000桌面及390×844窄屏均打开4份Markdown，核对主标题和第一段代码块与磁盘内容；中文相对章节链接可切换，下载文件与磁盘字节一致，无页面异常、无全页横向溢出。
4. 预览未出现可执行HTML、script、iframe、远程图片或javascript链接。反恶意HTML覆盖由替身浏览器测试验证；真实模型输出也检查同样的DOM边界。
5. 只读核对SQLite与API任务字段、7个产物清单、字节数、SHA-256、正文完全一致；4个输入副本与原快照一致；SQLite用量、model-data和产物用量一致。
6. 正常停止旧后台（PID15399），启动新后台（PID18776）。重复只读校验结果完全一致；浏览器重新打开项目、历史任务和第一章成功，没有新增模型请求。
7. 3条职责引用均逐字匹配：`utils/call_llm.py:L128–158`、`utils/crawl_github_files.py:L11–18`、`utils/crawl_local_files.py:L6–12`。均标为推断；引用匹配不等于语义已确认。原M2静态事实未被覆盖。

证据：[数据库／API／文件核对](real-verification.json)、[桌面／窄屏与重启检查](real-browser-check.json)。

实际React页面截图（不是M0样稿或固定输出）：

- [真实任务启动前](real-ready.png)
- [真实任务处理中](real-running.png)
- [真实结果·桌面](real-result-desktop.png)
- [真实结果·窄屏](real-result-narrow.png)
- [后台重启后重开历史章节](real-history-reopened.png)

## 3. 无网络异常验证与回归

| 验证 | 实际结果／边界 |
|---|---|
| 后台全量 | 59 passed，15.49秒；包括模型预检9项和真实适配器6项 |
| 最后客户端字段修正后 | `test_real_runs.py` 6 passed，2.50秒 |
| 已有桌面／窄屏浏览器路径 | 16 passed，约1.3分钟；成功、失败、取消、历史、上传边界、安全Markdown |
| 新增缺密钥页面状态 | 2 passed，7.7秒；模拟配置缺密钥时按钮禁用、可重新读取、未创建任务 |
| 实际上游入口＋模拟模型 | 固定main.py运行成功并重启读回；401只发1次不重试；慢请求取消；4主题超3上限时停止；截断输出／输入超限拒绝 |
| 缺密钥API | 返回409 model_config_missing，无任务和模型请求 |
| 失败／取消页面 | 使用固定替身；状态持久，无成功产物，不冒充真实服务商错误 |
| 构建 | TypeScript与Vite构建通过 |
| 依赖 | 后台与PocketFlow两个隔离环境 pip check 均通过 |
| 迁移 | 版本004，连续运行两次仍为4；历史项目和任务保持可读 |

缺密钥页面实际截图：[桌面配置夹具](missing-key-fixture-desktop.png)、[窄屏配置夹具](missing-key-fixture-narrow.png)。这两张使用模拟配置状态，不是真实模型失败截图。

异常路径使用假密钥、MockTransport、固定输出，未用真实余额制造错误。真实入口测试在子进程里运行固定上游main.py并拦截联网；并非只测状态字符串。进程中断／强制退出回归沿用任务监督进程测试；本次真实任务在成功后做后台重启验收。

执行命令：

```bash
# server/
.venv/bin/python -m app.model_check  # 仅配置检查，没有 --smoke
.venv/bin/python -m pytest -q --tb=short
.venv/bin/python -m pytest -q tests/test_real_runs.py --tb=short
.venv/bin/python -m pip check
pocketflow/.venv/bin/python -m pip check
.venv/bin/python -m app.migrate
.venv/bin/python -m app.migrate

# web/
npm run test:e2e
npm run test:e2e -- --grep '真实模式缺少密钥'
npm run build

# 根目录：只读复核既有真实任务，不创建新任务
server/.venv/bin/python evidence/m3/verify_saved_run.py
```

实际页面验收通过Playwright控制本机Chrome完成；正式运行在5173／8000，自动回归在5174／8001独立数据目录。`real-browser-check.json`记录逐个文件的比较项。环境为macOS Apple Silicon、Python3.14.6、Node22.23.0；锁文件保持既有版本。测试有Starlette关于HTTPX与anyio的弃用警告，不影响当前结果；升级另行处理。

## 4. 本步修复与能力范围

- 接通配置、固定入口、无重试的OpenRouter调用、真实阶段与调用用量、SQLite模型字段、版本化职责提示词、真实结果标签。
- 修正上游小范围提示“top 5-3”，并增加主题数量校验；不修改上游工作树。
- 密钥经stdin传递，不放命令行、进程继承环境、日志或证据。仅配置状态提供给页面。
- 支持中文文件名的内部Markdown链接，引用区展示行号与原文；缺密钥时提供重新读取入口。
- 本步已无阻塞；通过的是固定PocketFlow utils小样本的页面真实生成闭环，任意仓库真实生成、远程导入、多用户和Windows仍未实现。

## 5. 内容质量与剩余事项

1. 生成教程是模型推断，不能当作经过执行验证的使用说明。人工抽查发现第一章“遍历文件并过滤”的简化片段把`continue`放在模式内层循环，不能等价替代真实代码的`excluded=True/break`逻辑（源码L78–82）；第三章“目前支持三种”是对示例提供商的过度概括，实际使用通用兼容接口。原结果保留，页面标明模型推断，后续需建立内容质量评测。
2. 两条职责引用只引用函数签名，虽逐字匹配，但不足以独立证明说明中的所有行为；不能将引用匹配计为语义正确率。增加语义证据校验留作后续工作，不重复调用模型修饰这次验收。
3. Mermaid目前显示代码块；外链和图片禁用，长代码块在卡片内滚动。下一轮体验改进可再评估图渲染。
4. 当前仅本机单用户、单后台、一个活动任务；虚拟环境不等于OS沙箱。取消不会保证撤销服务商已接收请求的计费。
5. 本步结束，下一阶段是步骤8／M4，但没有启动。Git仅本地保存；运行数据和Key不进入提交。

历史：[初次缺配置预检](preflight-history.md)、[OpenRouter短请求](openrouter-precheck.md)、[步骤6替身验收](step-6-check.md)。
