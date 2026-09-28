import type { Card, Snapshot } from '../api/projects'
import type { FolderId } from '../types'

const demoSteps: { id?: FolderId; kind: string; name: string; role: string }[] = [
  { kind: '输入', name: 'GitHub 地址 / 本地目录', role: '用户交给程序一份源码' },
  { id: 'main', kind: '入口', name: 'main.py', role: '接收参数并启动流程' },
  { id: 'flow', kind: '编排', name: 'flow.py', role: '排定六个处理阶段' },
  { id: 'nodes', kind: '执行', name: 'nodes.py', role: '分析源码并撰写章节' },
  { kind: '产物', name: 'Markdown 教程', role: '把结果整理为可阅读文件' },
]

const demoRoles: Record<FolderId, { input: string; action: string; output: string; note: string }> = {
  root: { input: '仓库地址或本地目录', action: '入口、流程和节点协同处理源码', output: 'Markdown 教程', note: '这是整体阅读路线；点击图中的位置可查看具体文件。' },
  main: { input: '仓库地址或本地目录、语言等参数', action: '校验输入，准备共享数据并启动流程', output: '交给 flow.py 的运行上下文', note: '程序从这里开始；它本身不负责撰写教程。' },
  flow: { input: 'main.py 准备的运行上下文', action: '连接获取、分析、排序、写作和合并节点', output: '交给 nodes.py 的阶段顺序', note: '这里决定先做什么、后做什么。' },
  nodes: { input: '源码及前一阶段的结果', action: '逐阶段提取主题、分析关系并写章节', output: '交给下一节点的中间结果与最终章节', note: '具体处理逻辑在这里；节点会调用 utils/ 的辅助函数。' },
  utils: { input: '仓库位置、源码和模型请求', action: '读取本地或 GitHub 文件，封装模型调用', output: '供 nodes.py 使用的源码文本和模型回答', note: '这是节点的支撑能力，不是单独的启动入口。' },
  docs: { input: '开发者的需求和设计意图', action: '记录预期输入、输出和处理流程', output: '供人核对实现的设计说明', note: '设计文档不参与运行；实际行为仍以源码为准。' },
}

export function DemoOverview({ onSelect, source = false }: { onSelect: (id: FolderId) => void; source?: boolean }) {
  return <section className="overview-board" aria-labelledby="demo-overview-title">
    <div className="visual-kicker">01 / 先看整体</div>
    <div className="overview-intro"><div><h2 id="demo-overview-title">一张图看懂 PocketFlow</h2><p>它把一份仓库源码，按六个阶段整理成适合阅读的 Markdown 教程。</p></div><span className="visual-badge">{source ? '当前快照 · 固定版本核对' : '固定样本 · 源码线索'}</span></div>
    <ol className="visual-flow" aria-label="PocketFlow 的主要处理路线">
      {demoSteps.map((step, index) => <li key={step.name} className={`visual-step ${index === 0 || index === demoSteps.length - 1 ? 'terminal' : ''}`}>
        {step.id ? <button type="button" onClick={() => onSelect(step.id!)} aria-label={`查看 ${step.name} 的作用`}><span className="step-kind">{step.kind}</span><strong>{step.name}</strong><span>{step.role}</span><span className="step-open">查看作用 ↗</span></button> : <div><span className="step-kind">{step.kind}</span><strong>{step.name}</strong><span>{step.role}</span></div>}
      </li>)}
    </ol>
    <div className="visual-support"><span className="support-label">辅助位置</span><button type="button" onClick={() => onSelect('utils')}><strong>utils/</strong><span>为节点提供文件读取和模型调用</span><span aria-hidden="true">↗</span></button><button type="button" onClick={() => onSelect('docs')}><strong>docs/</strong><span>保存设计说明，供人核对</span><span aria-hidden="true">↗</span></button></div>
    <p className="visual-caveat">箭头表示已从固定版本源码整理的主路线；docs/ 是说明材料，不参与执行。点击位置后可核对{source ? '当前快照的源码' : '文件'}与行号。</p>
  </section>
}

export function DemoFolderVisual({ id, onSelect, source = false }: { id: FolderId; onSelect: (id: FolderId) => void; source?: boolean }) {
  const role = demoRoles[id]
  return <section className="role-board" aria-labelledby="demo-role-title">
    <div className="visual-kicker">02 / 再看这个位置</div>
    <h3 id="demo-role-title">{id === 'root' ? '重要位置各做什么' : '它在流程中做什么'}</h3>
    <div className="role-rail" aria-label="输入、当前作用、产出">
      <div><span>接收什么</span><strong>{role.input}</strong></div>
      <div className="role-focus"><span>这里做什么</span><strong>{role.action}</strong></div>
      <div><span>交出什么</span><strong>{role.output}</strong></div>
    </div>
    <p className="role-note">{role.note}{source && ' 此图按固定 Commit 人工整理；下方可核对当前快照源码。'}</p>
    {id === 'root' && <div className="role-gallery" aria-label="重要文件和文件夹">
      {(['main', 'flow', 'nodes', 'utils', 'docs'] as FolderId[]).map(item => <button key={item} type="button" onClick={() => onSelect(item)}><strong>{item === 'utils' || item === 'docs' ? `${item}/` : `${item}.py`}</strong><span>{demoRoles[item].action}</span><small>查看源码依据 ↗</small></button>)}
    </div>}
  </section>
}

function under(path: string, folder: string) {
  return folder === '.' || path.startsWith(`${folder}/`)
}

function roleHint(path: string, snapshot: Snapshot) {
  if (path === '.') return readmeSummary(snapshot)?.slice(0, 90) || '项目整体功能待核实'
  const name = path.split('/').at(-1)?.toLowerCase() ?? ''
  const files = snapshot.files.filter(file => under(file.path, path))
  const has = (suffixes: string[]) => files.some(file => suffixes.some(suffix => file.path.toLowerCase().endsWith(suffix)))
  if (['web', 'frontend', 'client', 'ui'].includes(name) && has(['.tsx', '.jsx', '.html', '.css'])) return '可能负责页面渲染与交互'
  if (['server', 'backend', 'api'].includes(name) && has(['.py', '.ts', '.js'])) return '可能负责接口与数据处理'
  if (['docs', 'doc', 'documentation'].includes(name) && has(['.md', '.rst', '.txt'])) return '可能保存使用与设计说明'
  if (['test', 'tests', '__tests__', 'spec'].includes(name)) return '可能用于验证项目行为'
  if (['components', 'views', 'pages'].includes(name) && has(['.tsx', '.jsx', '.vue', '.svelte'])) return '可能包含页面或可复用界面'
  if (['scripts', 'bin'].includes(name)) return '可能包含安装或运行脚本'
  if (['utils', 'helpers', 'lib'].includes(name)) return '可能提供其他模块调用的工具'
  if (['assets', 'public', 'static'].includes(name)) return '可能存放页面使用的静态资源'
  if (['src', 'app'].includes(name)) return '可能是主要源码目录'
  return '具体职责需结合源码核实'
}

function readmeSummary(snapshot: Snapshot) {
  const root = snapshot.folder_cards.find(card => card.path === '.')
  const readme = root?.evidence_refs.find(ref => /^readme(?:\.[^/]*)?$/i.test(ref.file_path))
  const lines = readme?.excerpt.split('\n').map(line => line.trim()
    .replace(/^#{1,6}\s*/, '')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/[`*_>]/g, '').trim()) ?? []
  return lines.find(line => line.length >= 18 && !/^https?:\/\//.test(line))?.slice(0, 180)
}

function keyFolders(snapshot: Snapshot) {
  return snapshot.folder_cards.filter(card => card.path !== '.' && !card.path.includes('/'))
    .sort((a, b) => snapshot.files.filter(file => under(file.path, b.path)).length - snapshot.files.filter(file => under(file.path, a.path)).length)
    .slice(0, 6)
}

export function SnapshotOverview({ snapshot, name, onSelect }: { snapshot: Snapshot; name: string; onSelect: (path: string) => void }) {
  const folders = keyFolders(snapshot)
  const summary = readmeSummary(snapshot)
  return <section className="overview-board" aria-labelledby="snapshot-overview-title">
    <div className="visual-kicker">01 / 先看整体</div>
    <div className="overview-intro"><div><h2 id="snapshot-overview-title">{name} · 项目概览</h2><p>{summary || '当前快照没有可直接摘录的项目简介。先看目录位置，再通过源码核对具体功能。'}</p></div><span className="visual-badge">{summary ? 'README 文字线索' : '静态目录快照'}</span></div>
    <div className="structure-map" aria-label="项目根目录与主要文件夹的包含关系">
      <button type="button" className="structure-root" onClick={() => onSelect('.')}><span>项目根目录</span><strong>{name}</strong><small>{snapshot.files.length} 个保留文件 · 查看根目录 ↗</small></button>
      <div className="structure-branches">{folders.length ? folders.map(card => <button type="button" className="structure-node" key={card.path} onClick={() => onSelect(card.path)}><span>顶层目录</span><strong>{card.path}/</strong><small>{roleHint(card.path, snapshot)}</small><em>查看目录 ↗</em></button>) : <div className="structure-empty">快照中没有子目录；可从根目录的文件开始阅读。</div>}</div>
    </div>
    <p className="visual-caveat">最多显示保留文件较多的 6 个顶层目录；其他目录可在左侧展开。连线只表示包含关系，不表示代码调用或运行顺序；职责提示需进入目录核对源码。</p>
  </section>
}

export function SnapshotFolderVisual({ snapshot, card }: { snapshot: Snapshot; card?: Card }) {
  const path = card?.path ?? '.'
  const parent = path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '.'
  const directFiles = snapshot.files.filter(file => (file.path.includes('/') ? file.path.slice(0, file.path.lastIndexOf('/')) : '.') === path)
  const childFolders = snapshot.folder_cards.filter(item => item.path !== path && (item.path.includes('/') ? item.path.slice(0, item.path.lastIndexOf('/')) : '.') === path)
  return <section className="role-board" aria-labelledby="snapshot-role-title">
    <div className="visual-kicker">02 / 再看这个目录</div>
    <h3 id="snapshot-role-title">位置与职责线索</h3>
    <div className="role-rail structure-role" aria-label="上级目录、当前目录、直接内容">
      <div><span>上级位置</span><strong>{path === '.' ? '已导入的项目' : parent === '.' ? '根目录 /' : `${parent}/`}</strong></div>
      <div className="role-focus"><span>当前目录</span><strong>{path === '.' ? '根目录 /' : `${path}/`}</strong><small>{roleHint(path, snapshot)}</small></div>
      <div><span>直接包含</span><strong>{directFiles.length} 个文件 · {childFolders.length} 个子目录</strong></div>
    </div>
    <p className="role-note">上图展示保存的目录结构。职责短句是路径与文件类型线索；下方的定义、配置和源码片段用于核对实际作用。</p>
  </section>
}
