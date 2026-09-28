import { useState } from 'react'
import type { Architecture, ArchitectureConnection, ArchitectureEvidence, ArchitectureModule, Card, Snapshot } from '../api/projects'
import type { FolderId } from '../types'

type Character = 'repo' | 'gate' | 'engine' | 'tool' | 'document' | 'window' | 'database'

function Mascot({ kind, small = false }: { kind: Character; small?: boolean }) {
  return <span className={`map-mascot mascot-${kind} ${small ? 'mascot-small' : ''}`} aria-hidden="true">
    <svg viewBox="0 0 88 88" fill="none">
      <path className="mascot-arm" d="M16 47 5 41m67 6 11-6M29 72l-5 10m35-10 5 10" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
      {kind === 'repo' || kind === 'tool' ? <path className="mascot-body" d="M13 31c0-7 5-12 12-12h10l7 7h20c8 0 13 5 13 13v26c0 8-5 13-13 13H26c-8 0-13-5-13-13V31Z" />
        : kind === 'document' ? <path className="mascot-body" d="M22 9h31l15 15v43c0 8-5 12-13 12H32c-7 0-12-4-12-12V21c0-7 3-12 2-12Z" />
        : kind === 'window' ? <rect className="mascot-body" x="10" y="18" width="68" height="57" rx="12" />
        : kind === 'database' ? <path className="mascot-body" d="M16 27c0-9 12-15 28-15s28 6 28 15v36c0 9-12 15-28 15S16 72 16 63V27Z" />
        : kind === 'engine' ? <path className="mascot-body" d="M44 8 51 16l11-2 3 11 11 5-5 11 5 10-11 5-3 11-11-2-7 9-8-9-11 2-3-11-10-5 4-10-4-11 10-5 3-11 11 2 8-8Z" />
        : <path className="mascot-body" d="M22 10h44v66H22c-8 0-12-5-12-13V23c0-8 4-13 12-13Z" />}
      {kind === 'window' && <path d="M11 34h66M22 26h2m7 0h2" stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity=".5" />}
      {kind === 'document' && <path d="M53 10v16h15M31 47h27m-27 8h20" stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity=".45" />}
      {kind === 'database' && <path d="M17 27c0 9 12 15 27 15s27-6 27-15M17 47c0 9 12 15 27 15s27-6 27-15" stroke="currentColor" strokeWidth="3" opacity=".35" />}
      <circle cx="35" cy="45" r="2.8" fill="#203c3a" /><circle cx="53" cy="45" r="2.8" fill="#203c3a" />
      <path d="M38 55q6 7 12 0" stroke="#203c3a" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="26" cy="53" r="4" fill="#f59c9b" opacity=".75" /><circle cx="62" cy="53" r="4" fill="#f59c9b" opacity=".75" />
    </svg>
  </span>
}

function Identity({ name, summary, source, facts }: { name: string; summary: string; source: string; facts: [string, string][] }) {
  return <section className="project-identity" aria-label="项目名称与简介">
    <div className="identity-main"><div className="visual-kicker">01 / 先认识项目</div><h1>{name}</h1><p>{summary}</p>
      <div className="identity-facts">{facts.map(([label, value]) => <span key={label}><b>{label}</b>{value}</span>)}</div>
      <small>{source}</small>
    </div>
    <div className="identity-art"><span className="identity-spark spark-one">✦</span><span className="identity-spark spark-two">✳</span><Mascot kind="repo" /><span className="identity-art-label">PROJECT</span></div>
  </section>
}

const demoRoles: Record<FolderId, { name: string; kind: Character; layer: string; input: string; action: string; output: string; links: string; note: string }> = {
  root: { name: '整个项目', kind: 'repo', layer: '系统全景', input: 'GitHub 地址或本地目录', action: '读取源码 → 理解结构 → 组织章节 → 生成教程', output: 'Markdown 教程', links: '入口、编排、处理节点和工具共同工作', note: '选择上方任一角色，可看到它在体系中的位置，再向下核对源码。' },
  main: { name: 'main.py', kind: 'gate', layer: '入口层', input: '仓库地址或本地目录、语言和输出参数', action: '检查输入，建立共享数据并启动教程流程', output: '交给 flow.py 的运行上下文', links: '连接用户输入与 flow.py', note: '它负责开门和启动，不负责写教程正文。' },
  flow: { name: 'flow.py', kind: 'engine', layer: '编排层', input: 'main.py 建立的上下文', action: '按顺序连接六个处理节点', output: '确定 nodes.py 中各节点的运行次序', links: '连接 main.py 和 nodes.py', note: '流程顺序来自节点连接；具体处理发生在 nodes.py。' },
  nodes: { name: 'nodes.py', kind: 'engine', layer: '处理层', input: '源码与上一阶段留下的共享数据', action: '采集、理解、排序、写作并合并教程', output: '各阶段中间结果和最终 Markdown', links: '使用 utils/，按 flow.py 的顺序运行', note: '六个节点是流程的工作站；不是六个独立的启动入口。' },
  utils: { name: 'utils/', kind: 'tool', layer: '支撑层', input: '仓库位置、文件路径和模型请求', action: '抓取 GitHub 或本地文件，封装模型调用', output: '供节点使用的源码文本与模型回答', links: '由 nodes.py 调用，不单独启动整条流程', note: '它像工具箱：提供能力，但不决定教程的处理顺序。' },
  docs: { name: 'docs/', kind: 'document', layer: '展示与参考层', input: '项目设计与已生成的教程样例', action: '保存设计手册、站点索引和示例教程', output: '供人阅读和展示的文档站点', links: '位于运行主链之外，可对照实际实现', note: '程序生成的新教程默认写入 output/，并非直接写进 docs/。' },
}

const demoStages: { no: string; title: string; action: string; result: string; character: Character }[] = [
  { no: '01', title: '收集源码', action: '按规则读取 GitHub / 本地文件', result: '文件清单', character: 'repo' },
  { no: '02', title: '找核心概念', action: '提炼重要对象及对应文件', result: '概念卡', character: 'engine' },
  { no: '03', title: '画出关系', action: '概括项目目标和概念互动', result: '简介＋关系线', character: 'database' },
  { no: '04', title: '定阅读路线', action: '按理解顺序排列概念', result: '章节顺序', character: 'gate' },
  { no: '05', title: '写入门章节', action: '结合源码撰写 Markdown', result: '章节草稿', character: 'document' },
  { no: '06', title: '装订教程', action: '合并目录、图解和章节', result: 'index.md＋各章', character: 'tool' },
]

export function DemoOverview({ onSelect, selected = 'root', source = false }: { onSelect: (id: FolderId) => void; selected?: FolderId; source?: boolean }) {
  return <div className="project-story">
    <Identity name="PocketFlow 项目地图" summary="这个仓库是基于 Pocket Flow 框架构建的代码库教程生成器。输入 GitHub 地址或本地目录后，它提取核心概念、关系和阅读顺序，生成带图解的 Markdown 入门教程。" source={source ? '此说明按所选固定 Commit 与源码线索整理' : '固定演示样本 · 按上游源码整理'} facts={[["输入", "仓库地址 / 本地目录"], ["核心动作", "理解源码并写教程"], ["得到", "Markdown 图解教程"]]} />
    <section className="system-board demo-system" aria-labelledby="demo-system-title">
      <div className="system-heading"><div><div className="visual-kicker">02 / 看系统如何工作</div><h2 id="demo-system-title">一张图看懂源码怎样变成教程</h2><p>上层负责启动和调度，下层六个工作站依次加工同一份共享数据。点选模块可看它在体系中的职责。</p></div><span className="visual-badge">固定版本 · 可核对源码</span></div>
      <div className="demo-control" aria-label="运行控制层">
        <div className="control-label"><span>运行控制层</span><strong>谁启动、谁排顺序？</strong></div>
        <button type="button" className={selected === 'main' ? 'is-selected' : ''} onClick={() => onSelect('main')} aria-label="查看 main.py 的作用"><Mascot kind="gate" small /><span><b>main.py · 启动台</b><small>接收地址与参数，准备共享数据</small></span><em>查看 ↗</em></button>
        <span className="control-link" aria-hidden="true">→</span>
        <button type="button" className={selected === 'flow' ? 'is-selected' : ''} onClick={() => onSelect('flow')} aria-label="查看 flow.py 的作用"><Mascot kind="engine" small /><span><b>flow.py · 路线指挥</b><small>把六个节点接成确定的顺序</small></span><em>查看 ↗</em></button>
      </div>
      <div className="pipeline-board" aria-label="PocketFlow 六阶段数据加工线">
        <div className="pipeline-heading"><div><span className="visual-kicker">源码 → 教程</span><h3>六站数据加工线</h3></div><button type="button" className={selected === 'nodes' ? 'is-selected' : ''} onClick={() => onSelect('nodes')} aria-label="查看 nodes.py 的作用"><b>nodes.py</b><span>六站实现都在这里</span><em>查看 ↗</em></button></div>
        <ol className="stage-track">{demoStages.map(stage => <li key={stage.no}><span className="stage-number">{stage.no}</span><Mascot kind={stage.character} small /><strong>{stage.title}</strong><p>{stage.action}</p><small>交出：{stage.result}</small></li>)}</ol>
        <div className="pipeline-endpoints"><span>入口：GitHub 地址 / 本地目录</span><span>产物：output/&lt;项目名&gt;/index.md 与各章节</span></div>
      </div>
      <div className="support-dock">
        <button type="button" className={selected === 'utils' ? 'is-selected' : ''} onClick={() => onSelect('utils')}><Mascot kind="tool" small /><span><b>utils/ · 工具间</b><small>第 1 站用文件抓取；第 2–5 站用模型调用</small></span><em>支撑六站 ↗</em></button>
        <button type="button" className={selected === 'docs' ? 'is-selected' : ''} onClick={() => onSelect('docs')}><Mascot kind="document" small /><span><b>docs/ · 样书与设计室</b><small>设计手册、站点索引与已发布教程</small></span><em>运行链之外 ↗</em></button>
      </div>
      <p className="visual-caveat">六站箭头表示固定源码中由 flow.py 连接的处理顺序；docs/ 属于展示和参考资料，默认输出写到 output/。点击模块可进入第 3 步查看职责与源码。</p>
    </section>
  </div>
}

export function DemoFolderVisual({ id, onSelect, source = false }: { id: FolderId; onSelect: (id: FolderId) => void; source?: boolean }) {
  const role = demoRoles[id]
  const neighbors: Record<FolderId, FolderId[]> = { root: ['main', 'flow', 'nodes', 'utils', 'docs'], main: ['flow'], flow: ['main', 'nodes'], nodes: ['flow', 'utils'], utils: ['nodes'], docs: ['main', 'flow'] }
  const contribution: Record<FolderId, { active: number[]; label: string }> = {
    root: { active: [1, 2, 3, 4, 5, 6], label: '六站共同完成教程生成' },
    main: { active: [1, 2, 3, 4, 5, 6], label: '启动整条加工线' },
    flow: { active: [1, 2, 3, 4, 5, 6], label: '规定六站的先后顺序' },
    nodes: { active: [1, 2, 3, 4, 5, 6], label: '实现六站各自的工作' },
    utils: { active: [1, 2, 3, 4, 5], label: '第 1 站抓取文件；第 2–5 站调用模型' },
    docs: { active: [], label: '位于生成链之外，保存设计与展示材料' },
  }
  return <section className="role-board story-role" aria-labelledby="demo-role-title">
    <div className="visual-kicker">03 / 在体系中定位</div>
    <div className="story-role-head"><Mascot kind={role.kind} /><div><span className="role-layer">{role.layer}</span><h3 id="demo-role-title">{id === 'root' ? '从这里认识各个角色' : `${role.name} 在系统中做什么`}</h3><p>{role.links}</p></div></div>
    <div className="role-stage-map"><div><b>它和六站的关系</b><small>{contribution[id].label}</small></div><ol>{demoStages.map((stage, index) => <li className={contribution[id].active.includes(index + 1) ? 'active' : ''} key={stage.no}><span>{stage.no}</span><strong>{stage.title}</strong></li>)}</ol></div>
    <div className="story-role-path" aria-label="输入、当前职责与产出"><div><span>接到</span><strong>{role.input}</strong></div><span className="path-arrow" aria-hidden="true">→</span><div className="active"><span>{role.name} 负责</span><strong>{role.action}</strong></div><span className="path-arrow" aria-hidden="true">→</span><div><span>交出</span><strong>{role.output}</strong></div></div>
    <div className="role-neighbors"><b>{id === 'root' ? '从哪个位置开始看？' : '相关位置'}</b><div>{neighbors[id].map(item => <button type="button" key={item} onClick={() => onSelect(item)}><span>{demoRoles[item].layer}</span><strong>{demoRoles[item].name}</strong><span aria-hidden="true">↗</span></button>)}</div></div>
    <p className="role-note">{role.note}{source && ' 当前快照的文件与源码在下方可核对。'}</p>
  </section>
}

function moduleVisual(kind: ArchitectureModule['kind']): { label: string; character: Character; zone: string } {
  switch (kind) {
    case 'entry': return { label: '启动入口', character: 'gate', zone: 'interface' }
    case 'interface': return { label: '用户界面', character: 'window', zone: 'interface' }
    case 'core': return { label: '核心处理', character: 'engine', zone: 'core' }
    case 'data': return { label: '数据与存储', character: 'database', zone: 'support' }
    case 'support': return { label: '支撑工具', character: 'tool', zone: 'support' }
    case 'docs': return { label: '说明文档', character: 'document', zone: 'reference' }
    case 'tests': return { label: '行为验证', character: 'document', zone: 'reference' }
    default: return { label: '其他模块', character: 'repo', zone: 'reference' }
  }
}

const zones = [
  { id: 'interface', no: 'A', title: '用户从哪里接触', description: '界面与启动入口' },
  { id: 'core', no: 'B', title: '主要逻辑在哪里', description: '项目的核心实现' },
  { id: 'support', no: 'C', title: '谁提供支撑', description: '工具、接口或数据层' },
  { id: 'reference', no: 'D', title: '怎样核对和学习', description: '文档、测试及其他' },
]

function fallbackSummary(snapshot: Snapshot) {
  const readme = snapshot.folder_cards.find(card => card.path === '.')?.evidence_refs.find(ref => /^readme(?:\.[^/]*)?$/i.test(ref.file_path))
  return readme?.excerpt.split('\n').map(line => line.replace(/^#{1,6}\s*/, '').replace(/[`*_>]/g, '').trim()).find(line => line.length >= 18) || '当前快照中没有足够的项目简介线索。可从下方的模块和源码逐步确认它的用途。'
}

function fallbackModules(snapshot: Snapshot): ArchitectureModule[] {
  return snapshot.folder_cards.filter(card => card.path !== '.' && !card.path.includes('/')).slice(0, 8).map(card => ({
    id: `folder:${card.path}`, title: `${card.path}/`, role: card.description || '目录用途待核对', kind: 'other', paths: [card.path], evidence: [], confidence: 'unknown',
    file_count: snapshot.files.filter(file => file.path.startsWith(`${card.path}/`)).length,
  }))
}

function moduleName(id: string, modules: ArchitectureModule[]) {
  return modules.find(module => module.id === id)?.title || id.replace(/^(folder|file):/, '')
}

function beginnerRole(module: ArchitectureModule) {
  if (module.id === 'folder:.') return '这里汇总项目快照；点选主要模块，再看它们各自负责什么。'
  if (!module.id.startsWith('folder:')) {
    if (module.kind === 'entry') return module.role.startsWith('HTML 模块脚本入口') ? '浏览器从这里加载前端入口，再沿源码引用进入页面与组件' : module.role.startsWith('清单声明的入口') ? '项目清单指定的入口，可从这里追踪它引用的模块' : '已发现启动入口；点开查看它连接的源码'
    return module.role
  }
  const leaf = module.paths[0].split('/').at(-1)?.toLowerCase()
  if (leaf === 'pages' || leaf === 'views') return '可能对应用户能打开的页面'
  if (leaf === 'components') return '可能放可复用的界面零件'
  if (leaf === 'routes' || leaf === 'api') return '可能定义请求入口和接口'
  if (leaf === 'docs') return '说明、用法或设计资料'
  if (leaf === 'tests' || leaf === 'test') return '用例帮助验证项目行为'
  switch (module.kind) {
    case 'interface': return '可能负责用户界面或接口层'
    case 'core': return '可能放主要业务处理逻辑'
    case 'data': return '可能负责数据模型或持久化'
    case 'support': return '可能提供配置和复用工具'
    default: return '用途待结合内部文件核对'
  }
}

export function SnapshotOverview({ snapshot, name, architecture, selectedId, onSelect }: { snapshot: Snapshot; name: string; architecture?: Architecture; selectedId?: string; onSelect: (module: ArchitectureModule) => void }) {
  const [expandedZones, setExpandedZones] = useState<string[]>([])
  const [showAllRelations, setShowAllRelations] = useState(false)
  const modules = architecture?.modules.length ? architecture.modules.filter(module => module.id !== 'folder:.') : fallbackModules(snapshot)
  const moduleById = new Map(modules.map(module => [module.id, module]))
  const actualLinks = architecture?.connections.filter(link => link.kind === 'imports' || link.kind === 'references') ?? []
  const summary = architecture?.summary || fallbackSummary(snapshot)
  const presentZones = zones.filter(zone => modules.some(module => moduleVisual(module.kind).zone === zone.id))
  const degree = new Map<string, number>()
  for (const link of actualLinks) {
    degree.set(link.from_id, (degree.get(link.from_id) || 0) + 1)
    degree.set(link.to_id, (degree.get(link.to_id) || 0) + 1)
  }
  const rank = (module: ArchitectureModule) => (module.kind === 'entry' ? 130 : module.id.startsWith('folder:') ? 70 + Math.min(module.file_count, 20) : 10) + (degree.get(module.id) || 0) * 2 + (module.confidence === 'observed' ? 3 : 0) - module.paths[0].split('/').length * 8
  const declaredEntries = new Set(architecture?.connections.filter(link => link.kind === 'references' && link.label.includes('入口')).map(link => link.to_id) || [])
  const orderedZoneItems = (zoneId: string) => {
    const items = modules.filter(module => moduleVisual(module.kind).zone === zoneId).sort((a, b) => rank(b) - rank(a))
    const entry = items.find(module => declaredEntries.has(module.id)) || items.find(module => module.kind === 'entry')
    const topFolder = items.find(module => module.id.startsWith('folder:') && !module.paths[0].includes('/'))
    const usefulFolder = items.find(module => module.id.startsWith('folder:') && module.paths[0].includes('/') && !['src', 'app'].includes(module.paths[0].split('/').at(-1) || ''))
    const seen = new Set<string>()
    const ordered: ArchitectureModule[] = []
    for (const module of [entry, topFolder, usefulFolder, ...items]) {
      if (!module || seen.has(module.id)) continue
      seen.add(module.id)
      ordered.push(module)
    }
    return ordered
  }
  const featured = new Set(presentZones.flatMap(zone => orderedZoneItems(zone.id).slice(0, 3).map(module => module.id)))
  const connectionScore = (link: NonNullable<Architecture>['connections'][number]) => {
    const from = moduleById.get(link.from_id)
    const to = moduleById.get(link.to_id)
    return (from?.kind === 'entry' ? 140 : 0) + (to?.kind === 'entry' ? 80 : 0)
      + (link.kind === 'references' && link.label.includes('入口') ? 110 : 0)
      + (featured.has(link.from_id) ? 20 : 0) + (featured.has(link.to_id) ? 20 : 0)
      + (selectedId && (selectedId === link.from_id || selectedId === link.to_id) ? 100 : 0)
  }
  const rankedLinks = [...actualLinks].sort((a, b) => connectionScore(b) - connectionScore(a))
  const firstLinks = (() => {
    const grouped = new Map<string, typeof rankedLinks>()
    for (const link of rankedLinks) {
      const path = moduleById.get(link.from_id)?.paths[0] || ''
      const root = path.split('/')[0] || '其他'
      const items = grouped.get(root)
      if (items) items.push(link)
      else grouped.set(root, [link])
    }
    const picked: typeof rankedLinks = []
    while (picked.length < 8 && [...grouped.values()].some(items => items.length)) {
      for (const items of grouped.values()) {
        const item = items.shift()
        if (item) picked.push(item)
        if (picked.length === 8) break
      }
    }
    return picked
  })()
  const readingTrail = (() => {
    const declared = actualLinks.find(link => link.kind === 'references' && link.label.includes('入口') && moduleById.has(link.from_id) && moduleById.has(link.to_id))
    const trail = declared ? [moduleById.get(declared.from_id)!, moduleById.get(declared.to_id)!]
      : [modules.find(module => module.kind === 'entry')].filter((module): module is ArchitectureModule => !!module)
    const visited = new Set(trail.map(module => module.id))
    while (trail.length && trail.length < 4) {
      const last = trail.at(-1)!
      const next = actualLinks.filter(link => link.from_id === last.id && !visited.has(link.to_id) && moduleById.has(link.to_id))
        .map(link => moduleById.get(link.to_id)!)
        .sort((a, b) => (b.id.startsWith('file:') ? 1 : 0) - (a.id.startsWith('file:') ? 1 : 0) || (degree.get(b.id) || 0) - (degree.get(a.id) || 0))[0]
      if (!next) break
      trail.push(next)
      visited.add(next.id)
    }
    return trail.length > 1 ? trail : []
  })()
  return <div className="project-story">
    <Identity name={`${name} 项目地图`} summary={summary} source={architecture?.summary_source ? `项目简介线索：${architecture.summary_source.file_path} · L${architecture.summary_source.line_start}` : '项目简介缺少直接证据；以下仅根据已保存源码给出结构线索'} facts={[["已保存源码", `${snapshot.files.length} 个文件`], ["识别模块", `${modules.length} 个`], ["源码关系", `${actualLinks.length} 条`]]} />
    <section className="system-board" aria-labelledby="snapshot-system-title">
      <div className="system-heading"><div><div className="visual-kicker">02 / 看项目体系</div><h2 id="snapshot-system-title">这份代码由哪些部分组成？</h2><p>按入口、核心、支撑和参考资料分层；下方的连线说明哪些模块在源码中引用了其他模块。</p></div><span className="visual-badge">当前快照 · 静态分析</span></div>
      <div className={`architecture-world zones-${presentZones.length}`} aria-label="项目模块分层图">
        {presentZones.map(zone => {
          const allItems = orderedZoneItems(zone.id)
          const isExpanded = expandedZones.includes(zone.id)
          const items = isExpanded ? allItems : allItems.slice(0, 3)
          return <section className={`architecture-zone zone-${zone.id}`} key={zone.id} aria-label={zone.title}>
            <div className="zone-heading"><span>{zone.no}</span><div><h3>{zone.title}</h3><small>{zone.description}</small></div></div>
            <div className="zone-modules">{items.length ? items.map(module => {
              const visual = moduleVisual(module.kind)
              return <button type="button" className={`architecture-module ${selectedId === module.id ? 'is-selected' : ''}`} key={module.id} onClick={() => onSelect(module)} aria-label={`查看 ${module.title} 的作用`}><Mascot kind={visual.character} small /><span className="module-copy"><small>{visual.label} · {module.confidence === 'observed' ? '源码线索' : module.confidence === 'inferred' ? '静态推断' : '待核实'}</small><strong>{module.title}</strong><span>{beginnerRole(module)}</span></span><em>↗</em></button>
            }) : <p className="zone-empty">当前快照未识别到这一层的模块</p>}{allItems.length > 3 && <button type="button" className="zone-more" onClick={() => setExpandedZones(current => isExpanded ? current.filter(id => id !== zone.id) : [...current, zone.id])}>{isExpanded ? '收起这个分区 ↑' : `展开这个分区其余 ${allItems.length - 3} 个模块 ↓`}</button>}</div>
          </section>
        })}{!presentZones.length && <p className="relation-empty">没有足够的保留源码来识别项目模块，可从左侧打开已保存的文件。</p>}
      </div>
      {!!readingTrail.length && <div className="reading-trail" aria-label="源码阅读主线"><div><span className="visual-kicker">一条有证据的阅读路线</span><h3>从入口走进项目</h3><p>沿清单或源码引用跟读，点击任一位置可看职责与证据。</p></div><ol>{readingTrail.map((module, index) => <li key={module.id}><button type="button" onClick={() => onSelect(module)} aria-label={`查看阅读路线中的 ${module.title}`}><Mascot kind={moduleVisual(module.kind).character} small /><span><small>第 {index + 1} 站</small><strong>{module.title}</strong></span></button>{index < readingTrail.length - 1 && <span className="trail-arrow" aria-hidden="true">→</span>}</li>)}</ol><small>箭头是已保存源码中的引用或清单指向，供阅读定位，不代表完整运行顺序。</small></div>}
      <div className="architecture-relations"><div className="relations-heading"><div><span className="visual-kicker">源码中确认的连接</span><h3>模块怎样互相使用</h3></div><small>{actualLinks.length} 条引用关系</small></div>
        {actualLinks.length ? <div className="relation-list">{(showAllRelations ? rankedLinks : firstLinks).map((link, index) => {
          const from = moduleById.get(link.from_id)
          const to = moduleById.get(link.to_id)
          return <div className="relation-line" key={`${link.from_id}-${link.to_id}-${index}`}><button type="button" onClick={() => from && onSelect(from)} disabled={!from}>{moduleName(link.from_id, modules)}</button><b aria-hidden="true">→</b><button type="button" onClick={() => to && onSelect(to)} disabled={!to}>{moduleName(link.to_id, modules)}</button><small>{link.label || (link.kind === 'imports' ? '源码导入' : '清单引用')}{link.evidence[0] ? ` · ${link.evidence[0].file_path}:L${link.evidence[0].line_start}` : ''}</small></div>
        })}</div> : <p className="relation-empty">在已保留的源码中，暂未确认模块间的引用关系。上方仍可查看结构，但不把目录包含关系当作运行流程。</p>}
        {actualLinks.length > 8 && <button type="button" className="relation-more" onClick={() => setShowAllRelations(value => !value)}>{showAllRelations ? '收起引用关系 ↑' : `查看全部 ${actualLinks.length} 条引用关系 ↓`}</button>}
      </div>
      <p className="visual-caveat">优先展示入口、主要目录和引用较多的文件，可展开其余模块。箭头仅表示源码引用或清单引用，不等于运行顺序；点击模块可查看依据。</p>
      {architecture && <details className="map-method"><summary>这张图覆盖了什么、还有哪些未知？</summary><p>保留 {architecture.coverage.retained_files} 个文本文件，检查 {architecture.coverage.inspected_source_files} 个源码文件，解析 {architecture.coverage.resolved_imports} 处本地导入。</p><ul>{architecture.limitations.map(line => <li key={line}>{line}</li>)}</ul></details>}
    </section>
  </div>
}

export function SnapshotFolderVisual({ snapshot, card, architecture, selectedId, onSelect, onEvidence }: { snapshot: Snapshot; card?: Card; architecture?: Architecture; selectedId?: string; onSelect?: (module: ArchitectureModule) => void; onEvidence?: (evidence: ArchitectureEvidence) => void }) {
  const modules = architecture?.modules.length ? architecture.modules : fallbackModules(snapshot)
  const moduleById = new Map(modules.map(module => [module.id, module]))
  const path = card?.path ?? '.'
  const selected = modules.find(module => module.id === selectedId) || modules.find(module => module.paths.includes(path) || module.paths.some(item => item.startsWith(`${path}/`) && path !== '.'))
  const visual = selected?.id === 'folder:.' ? { label: '项目全貌', character: 'repo' as Character, zone: 'reference' } : selected ? moduleVisual(selected.kind) : { label: '项目根目录', character: 'repo' as Character, zone: 'interface' }
  const isSelectedFolder = selected?.id.startsWith('folder:') || false
  const selectedPath = selected?.paths[0] || '.'
  const within = (module?: ArchitectureModule) => !!module && (module.id === selected?.id || (isSelectedFolder && (selectedPath === '.' || module.paths[0].startsWith(`${selectedPath}/`))))
  const immediatePart = (module: ArchitectureModule) => {
    if (!isSelectedFolder || !within(module) || module.id === selected?.id) return module
    const remainder = selectedPath === '.' ? module.paths[0] : module.paths[0].slice(selectedPath.length + 1)
    const child = selectedPath === '.' ? remainder.split('/')[0] : `${selectedPath}/${remainder.split('/')[0]}`
    return moduleById.get(`folder:${child}`) || moduleById.get(`file:${child}`) || module
  }
  const groupLinks = (links: ArchitectureConnection[], simplify: boolean) => {
    const grouped = new Map<string, { from: ArchitectureModule; to: ArchitectureModule; kind: ArchitectureConnection['kind']; count: number }>()
    for (const link of links) {
      const source = moduleById.get(link.from_id)
      const target = moduleById.get(link.to_id)
      if (!source || !target || (!within(source) && !within(target))) continue
      const from = simplify ? immediatePart(source) : source
      const to = simplify ? immediatePart(target) : target
      if (from.id === to.id) continue
      const key = `${from.id}|${to.id}|${link.kind}`
      const group = grouped.get(key)
      if (group) group.count += Math.max(1, link.evidence.length)
      else grouped.set(key, { from, to, kind: link.kind, count: Math.max(1, link.evidence.length) })
    }
    return [...grouped.values()].sort((a, b) => b.count - a.count || a.from.title.localeCompare(b.from.title))
  }
  const sourceLinks = architecture?.connections.filter(link => link.kind !== 'contains') || []
  const simplifiedLinks = groupLinks(sourceLinks, true)
  const related = selected?.id === 'folder:.'
    ? (architecture?.connections.filter(link => link.kind === 'contains' && link.from_id === 'folder:.' && link.to_id.startsWith('folder:')).map(link => ({ from: moduleById.get(link.from_id)!, to: moduleById.get(link.to_id)!, kind: link.kind, count: 1 })).filter(link => link.from && link.to) || [])
    : (simplifiedLinks.length ? simplifiedLinks : groupLinks(sourceLinks, false))
  const directFiles = snapshot.files.filter(file => (file.path.includes('/') ? file.path.slice(0, file.path.lastIndexOf('/')) : '.') === path)
  const childFolders = snapshot.folder_cards.filter(item => item.path !== path && (item.path.includes('/') ? item.path.slice(0, item.path.lastIndexOf('/')) : '.') === path)
  return <section className="role-board story-role" aria-labelledby="snapshot-role-title">
    <div className="visual-kicker">03 / 放回体系中看</div>
    <div className="story-role-head"><Mascot kind={visual.character} /><div><span className="role-layer">{visual.label}</span><h3 id="snapshot-role-title">{selected?.title || (path === '.' ? '项目根目录' : `${path}/`)} 的作用</h3><p>{selected ? beginnerRole(selected) : card?.description || '此位置的职责仍需结合源码确认。'}</p></div></div>
    <div className="folder-context"><div><span>在项目中的位置</span><strong>{selected?.paths.join('、') || (path === '.' ? '根目录 /' : `${path}/`)}</strong></div><div><span>这个位置包含</span><strong>{selected ? `${selected.file_count} 个保留文件` : `${directFiles.length} 个文件 · ${childFolders.length} 个子目录`}</strong></div><div><span>依据状态</span><strong>{selected?.confidence === 'observed' ? '有源码线索' : selected?.confidence === 'inferred' ? '静态推断，需核对' : '职责待核实'}</strong></div></div>
    <div className="role-neighbors snapshot-neighbors"><b>它与哪些部分相连</b><div>{related.length ? related.slice(0, 6).map((link, index) => <div className="relation-line" key={`${link.from.id}-${link.to.id}-${index}`}><button type="button" onClick={() => onSelect?.(link.from)}>{link.from.title}</button><b aria-hidden="true">→</b><button type="button" onClick={() => onSelect?.(link.to)}>{link.to.title}</button><small>{link.kind === 'contains' ? '直接包含' : link.kind === 'imports' ? `${link.count} 处源码导入` : `${link.count} 处清单引用`}</small></div>) : <p className="muted">静态扫描暂未确认它与其他模块的引用关系；可从下方文件继续核对。</p>}</div></div>
    {!!selected?.evidence.length && <div className="role-evidence"><b>可查看的源码线索</b><div>{selected.evidence.slice(0, 3).map((evidence, index) => <button type="button" key={`${evidence.file_path}-${evidence.line_start}-${index}`} onClick={() => onEvidence?.(evidence)}>{evidence.file_path}:L{evidence.line_start} ↗</button>)}</div></div>}
    <p className="role-note">{selected?.role} 文件数仅计算本次保存的文本文件。关系来自可定位的源码引用；目录归属和作用推断不会冒充运行调用。</p>
  </section>
}
