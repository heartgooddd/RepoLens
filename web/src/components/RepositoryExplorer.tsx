import { useEffect, useMemo, useRef, useState } from 'react'
import type { Architecture, ArchitectureConnection, ArchitectureEvidence, ArchitectureModule, SourceSlice } from '../api/projects'
import type { ExplorerFile } from '../api/online'
import './repository-explorer.css'

type Props = {
  name: string; files: ExplorerFile[]; architecture?: Architecture; repositoryUrl?: string; commit?: string;
  online?: boolean; busy?: boolean; error?: string; warnings?: string[]; excludedCount?: number;
  onRead?: (paths?: string[]) => Promise<void>;
  loadSource: (path: string, start: number, signal: AbortSignal) => Promise<SourceSlice>;
}
const basename = (path: string) => path.split('/').at(-1) || path
const kindLabel: Record<ArchitectureModule['kind'], string> = {
  entry: '启动入口', interface: '界面 / 接口', core: '核心逻辑', data: '数据存储', support: '辅助工具', docs: '说明文档', tests: '测试验证', other: '源码文件',
}
function fileRole(path: string, module?: ArchitectureModule) {
  if (module) return kindLabel[module.kind]
  if (/readme|\.md$/i.test(path)) return '项目文档'
  if (/package\.json|\.toml$|\.ya?ml$/.test(path)) return '项目配置'
  return '待分析'
}

// A reading trail follows observed static edges. It is explicitly not a call trace.
export function readingTrail(root: string, links: ArchitectureConnection[], modules: ArchitectureModule[]) {
  const ids = new Set(modules.map(module => module.id))
  const trail = root && ids.has(root) ? [root] : []
  while (trail.length && trail.length < 6) {
    const next = links.filter(link => link.from_id === trail.at(-1) && !trail.includes(link.to_id) && ids.has(link.to_id))
      .sort((a, b) => Number(b.kind === 'references') - Number(a.kind === 'references') || a.to_id.localeCompare(b.to_id))[0]
    if (!next) break
    trail.push(next.to_id)
  }
  return trail
}

type TreeNode = { name: string; path: string; children: Map<string, TreeNode>; file?: ExplorerFile }
function fileTree(files: ExplorerFile[]) {
  const root: TreeNode = { name: '', path: '', children: new Map() }
  for (const file of files) {
    let node = root
    const parts = file.path.split('/')
    parts.forEach((name, index) => {
      const path = parts.slice(0, index + 1).join('/')
      if (!node.children.has(name)) node.children.set(name, { name, path, children: new Map() })
      node = node.children.get(name)!
    })
    node.file = file
  }
  return root
}
function TreeBranch({ node, selected, expanded, toggle, choose, modules, depth = 0 }: {
  node: TreeNode; selected: string; expanded: Set<string>; toggle: (path: string) => void;
  choose: (path: string) => void; modules: Map<string, ArchitectureModule>; depth?: number;
}) {
  const children = [...node.children.values()].sort((a, b) => Number(!!a.file) - Number(!!b.file) || a.name.localeCompare(b.name))
  return <ul className="rx-tree-list">{children.map(child => <li key={child.path}>
    {child.file ? <button type="button" className={`rx-tree-file ${selected === child.path ? 'is-selected' : ''}`} style={{ paddingLeft: 10 + depth * 14 }}
      aria-pressed={selected === child.path} aria-label={`文件 ${child.path}${child.file.loaded ? '' : ' · 未读取'}`} onClick={() => choose(child.path)} title={child.path}>
      <span className="rx-file-icon" aria-hidden="true">▤</span><span className="rx-tree-name">{child.name}<small>{fileRole(child.path, modules.get(child.path))}</small></span>
      <span className={`rx-read-dot ${child.file.loaded ? 'loaded' : ''}`} title={child.file.loaded ? '已读取' : '未读取'} aria-hidden="true" />
    </button> : <><button type="button" className="rx-tree-folder" style={{ paddingLeft: 10 + depth * 14 }} aria-expanded={expanded.has(child.path)} onClick={() => toggle(child.path)} title={child.path}>
      <span aria-hidden="true">{expanded.has(child.path) ? '⌄' : '›'}</span><span className="rx-folder-icon" aria-hidden="true">▰</span><span>{child.name}</span>
    </button>{expanded.has(child.path) && <TreeBranch node={child} selected={selected} expanded={expanded} toggle={toggle} choose={choose} modules={modules} depth={depth + 1} />}</>}
  </li>)}</ul>
}

function RelationGraph({ focus, modules, links, choose, inspect }: {
  focus?: ArchitectureModule; modules: ArchitectureModule[]; links: ArchitectureConnection[];
  choose: (path: string) => void; inspect: (edge: ArchitectureConnection) => void;
}) {
  const host = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(650)
  useEffect(() => {
    if (!host.current) return
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(host.current)
    return () => observer.disconnect()
  }, [])
  const byId = new Map(modules.map(module => [module.id, module]))
  const incoming = links.filter(link => link.to_id === focus?.id && byId.has(link.from_id))
  const outgoing = links.filter(link => link.from_id === focus?.id && byId.has(link.to_id))
  const left = [...new Set(incoming.map(link => link.from_id))].slice(0, 4)
  const right = [...new Set(outgoing.map(link => link.to_id))].slice(0, 4)
  const height = Math.max(350, Math.max(left.length, right.length) * 106 + 80)
  const nodeWidth = (width - 72) / 3
  const x = [12, (width - nodeWidth) / 2, width - nodeWidth - 12]
  const positions = new Map<string, { x: number; y: number }>()
  left.forEach((id, i) => positions.set(id, { x: x[0], y: 60 + i * 106 }))
  right.forEach((id, i) => { if (!positions.has(id)) positions.set(id, { x: x[2], y: 60 + i * 106 }) })
  if (focus) positions.set(focus.id, { x: x[1], y: height / 2 - 25 })
  const visibleEdges = [...incoming, ...outgoing].filter(link => positions.has(link.from_id) && positions.has(link.to_id))
  return <>
    <div className="rx-graph-scroll"><div className="rx-graph" ref={host} style={{ height }} aria-label="文件引用关系图">
      <div className="rx-graph-labels"><span>谁引用它</span><span>当前文件</span><span>它引用谁</span></div>
      <svg width={width} height={height} aria-hidden="true" className="rx-graph-lines"><defs><marker id="rx-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" /></marker></defs>
        {visibleEdges.map((link, i) => {
          const a = positions.get(link.from_id)!, b = positions.get(link.to_id)!
          const forward = b.x > a.x
          const ax = a.x + (forward ? nodeWidth : 0), bx = b.x + (forward ? 0 : nodeWidth), ay = a.y + 40, by = b.y + 40
          return <path key={`${link.from_id}:${link.to_id}:${i}`} d={`M ${ax} ${ay} C ${(ax + bx) / 2} ${ay}, ${(ax + bx) / 2} ${by}, ${bx} ${by}`} markerEnd="url(#rx-arrow)" />
        })}
      </svg>
      {[...positions].map(([id, position]) => {
        const module = byId.get(id)!
        return <button type="button" key={id} className={`rx-graph-node ${id === focus?.id ? 'is-selected' : ''}`} aria-pressed={id === focus?.id} onClick={() => choose(module.paths[0])}
          style={{ left: position.x, top: position.y, width: nodeWidth }} title={module.paths[0]}>
          <span className="rx-node-kind">{kindLabel[module.kind]}</span><strong>{basename(module.paths[0])}</strong><small>{module.paths[0].includes('/') ? module.paths[0].slice(0, module.paths[0].lastIndexOf('/')) : '根目录'}</small>
        </button>
      })}
      {!focus && <div className="rx-graph-empty"><span>◇</span><h3>从一个文件开始</h3><p>读取关键文件后，这里会出现有源码依据的引用关系。</p></div>}
      {focus && !visibleEdges.length && <p className="rx-graph-unlinked">当前已读源码中，尚未发现该文件的本地引用关系。</p>}
    </div></div>
    <div className="rx-graph-legend"><span><i /> 箭头表示源码引用</span><span>非函数执行顺序</span></div>
    {(left.length < new Set(incoming.map(link => link.from_id)).size || right.length < new Set(outgoing.map(link => link.to_id)).size) && <p className="rx-muted">图中每侧展示前 4 个相邻文件；完整关系见下方列表。</p>}
    {!![...incoming, ...outgoing].length && <details className="rx-relations"><summary>核对引用依据 · {incoming.length + outgoing.length} 条</summary>
      {[...incoming, ...outgoing].map((link, index) => <button key={index} type="button" onClick={() => inspect(link)}>
        <span>{basename(byId.get(link.from_id)?.paths[0] || '')} → {basename(byId.get(link.to_id)?.paths[0] || '')}</span><small>{link.label} · L{link.evidence[0]?.line_start ?? '—'}</small>
      </button>)}
    </details>}
  </>
}

export function RepositoryExplorer({ name, files, architecture, repositoryUrl, commit, online, busy, error, warnings = [], excludedCount = 0, onRead, loadSource }: Props) {
  const modules = useMemo(() => architecture?.modules.filter(module => module.id.startsWith('file:')) || [], [architecture])
  const links = useMemo(() => architecture?.connections.filter(link => link.kind !== 'contains') || [], [architecture])
  const modulesByPath = useMemo(() => new Map(modules.map(module => [module.paths[0], module])), [modules])
  const treeScroll = useRef<HTMLDivElement>(null)
  const [selected, setSelected] = useState('')
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(['web', 'web/src', 'web/src/pages', 'web/src/api', 'server', 'server/app', 'src']))
  const [filter, setFilter] = useState('')
  const [root, setRoot] = useState('')
  const [playing, setPlaying] = useState(false)
  const [sourceOpen, setSourceOpen] = useState(false)
  const [sourceStart, setSourceStart] = useState(1)
  const [sourceData, setSourceData] = useState<SourceSlice>()
  const [sourceError, setSourceError] = useState('')
  const [sourceRetry, setSourceRetry] = useState(0)
  const [contractIndex, setContractIndex] = useState(0)
  const [edgeEvidence, setEdgeEvidence] = useState<ArchitectureEvidence>()
  const roots = useMemo(() => [...modules].sort((a, b) => Number(b.kind === 'entry') - Number(a.kind === 'entry') ||
    links.filter(link => link.from_id === b.id).length - links.filter(link => link.from_id === a.id).length || a.title.localeCompare(b.title)), [modules, links])
  const trail = useMemo(() => readingTrail(root || roots[0]?.id || '', links, modules), [root, roots, links, modules])
  const activeIndex = trail.indexOf(`file:${selected}`)
  const focus = modulesByPath.get(selected)
  const contract = focus?.contracts?.[contractIndex] || focus?.contracts?.[0]
  const selectedFile = files.find(file => file.path === selected)
  const loadedCount = files.filter(file => file.loaded).length
  const filtered = useMemo(() => files.filter(file => file.path.toLowerCase().includes(filter.toLowerCase())), [files, filter])
  const tree = useMemo(() => fileTree(filtered), [filtered])
  const filterExpanded = useMemo(() => {
    if (!filter) return expanded
    const all = new Set(expanded)
    filtered.forEach(file => file.path.split('/').slice(0, -1).forEach((_, i, parts) => all.add(parts.slice(0, i + 1).join('/'))))
    return all
  }, [filter, filtered, expanded])

  function select(path: string, stop = true) {
    if (stop) setPlaying(false)
    setSelected(path); setContractIndex(0); setSourceStart(1); setEdgeEvidence(undefined); setSourceOpen(false)
    setExpanded(previous => {
      const next = new Set(previous), parts = path.split('/')
      for (let i = 1; i < parts.length; i++) next.add(parts.slice(0, i).join('/'))
      return next
    })
  }
  useEffect(() => {
    if (!selected && roots.length) select(roots[0].paths[0])
  }, [roots, selected])
  useEffect(() => {
    if (!playing || busy || trail.length < 2) return
    if (activeIndex === trail.length - 1) { setPlaying(false); return }
    const timer = window.setTimeout(() => select(trail[Math.max(0, activeIndex + 1)].slice(5), false), 1800)
    return () => window.clearTimeout(timer)
  }, [playing, activeIndex, trail, busy])
  useEffect(() => {
    if (!sourceOpen || !selected) return
    const controller = new AbortController()
    setSourceData(undefined); setSourceError('')
    loadSource(selected, sourceStart, controller.signal).then(value => {
      if (!controller.signal.aborted) setSourceData(value)
    }).catch(reason => { if (!controller.signal.aborted) setSourceError(reason.message) })
    return () => controller.abort()
  }, [sourceOpen, selected, sourceStart, sourceRetry, loadSource])
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const container = treeScroll.current
      const item = container?.querySelector('.rx-tree-file.is-selected')
      if (!container || !item) return
      const bounds = container.getBoundingClientRect(), row = item.getBoundingClientRect()
      if (row.bottom > bounds.bottom) container.scrollTop += row.bottom - bounds.bottom + 12
      else if (row.top < bounds.top) container.scrollTop -= bounds.top - row.top + 12
    })
    return () => cancelAnimationFrame(frame)
  }, [selected, expanded, filter])
  const incoming = links.filter(link => link.to_id === focus?.id)
  const outgoing = links.filter(link => link.from_id === focus?.id)
  const githubPath = repositoryUrl && commit && selected ? `${repositoryUrl}/blob/${commit}/${selected.split('/').map(encodeURIComponent).join('/')}` : undefined
  function inspect(link: ArchitectureConnection) {
    const evidence = link.evidence[0]
    if (evidence) { select(evidence.file_path); setEdgeEvidence(evidence); setSourceStart(evidence.line_start); setSourceOpen(true) }
  }
  async function readSelected() { if (onRead && selected) await onRead([selected]) }
  return <div className="rx-explorer">
    <div className="rx-heading"><div><div className="rx-eyebrow">{name} / PROJECT EXPLORER</div><h1>从文件到运行，读懂这个项目</h1><p>文件结构 <span>→</span> 模块协作 <span>→</span> 源码路径推演</p></div>
      <div className="rx-revision"><span className="rx-status-dot" />{online ? 'GitHub 在线读取' : '已保存快照'}{commit && <code>{commit.slice(0, 7)}</code>}</div>
    </div>
    {repositoryUrl && <a className="rx-repo-link" href={repositoryUrl} target="_blank" rel="noreferrer">{repositoryUrl.replace('https://', '')} ↗</a>}
    <div className="rx-coverage"><span><strong>{files.length}</strong> 个可读文件 <span className="rx-separator">/</span> 已读取 <strong>{loadedCount}</strong> 个 <span className="rx-separator">/</span> {links.length} 条已解析引用</span>
      {onRead && <button type="button" className="rx-button rx-button-primary" disabled={busy || loadedCount === files.length} onClick={() => void onRead()}>{busy ? '正在读取与分析…' : loadedCount ? '继续分析相关文件' : '分析关键文件'}</button>}
    </div>
    {error && <p className="rx-error" role="alert">{error}</p>}
    {warnings.map((warning, i) => <p className="rx-notice" role="status" key={i}>{warning}</p>)}
    <div className="rx-columns">
      <aside className="rx-panel rx-file-panel" aria-label="项目文件结构"><div className="rx-panel-title"><h2><span>01</span> 文件结构</h2><span>{files.length}</span></div>
        <label className="rx-search"><span className="sr-only">查找文件</span><input type="search" value={filter} onChange={event => setFilter(event.target.value)} placeholder="查找文件或目录…" /></label>
        <div className="rx-tree-scroll" ref={treeScroll}><div className="rx-tree-root">▰ {name}</div><TreeBranch node={tree} selected={selected} expanded={filterExpanded} toggle={path => setExpanded(previous => { const next = new Set(previous); if (next.has(path)) next.delete(path); else next.add(path); return next })} choose={select} modules={modulesByPath} />
          {!filtered.length && <p className="rx-muted">没有匹配的文件。</p>}
        </div>
        <div className="rx-tree-footer"><span><i className="rx-read-dot loaded" /> 已读取</span><span><i className="rx-read-dot" /> 未读取</span><p>仅列出可读文本。{excludedCount > 0 ? `已排除 ${excludedCount} 个资源或不支持的文件。` : ''}</p></div>
      </aside>
      <section className="rx-panel rx-map-panel" aria-label="模块协作图"><div className="rx-panel-title"><h2><span>02</span> 模块如何协作</h2><span className="rx-badge">源码依据</span></div>
        <div className="rx-map-intro"><h3>{focus ? basename(selected) : '项目引用关系'}</h3><p>{selected && !focus ? '这个文件还没有可展示的关系，读取后可继续查看。' : '选择文件查看上下游，点击关系可核对源码。'}</p></div>
        <RelationGraph focus={focus} modules={modules} links={links} choose={select} inspect={inspect} />
      </section>
      <aside className="rx-panel rx-inspector" aria-label="文件职责与源码"><div className="rx-panel-title"><h2>当前文件</h2><span className="rx-badge">{selectedFile?.loaded ? '已读取' : '待选择 / 读取'}</span></div>
        {selected ? <><div className="rx-inspector-file"><span className="rx-file-icon" aria-hidden="true">▤</span><div><h3>{basename(selected)}</h3><p>{selected}</p></div></div>
          {selectedFile && !selectedFile.loaded && onRead ? <div className="rx-unread"><p>文件目录已获取，正文尚未读取。</p><button type="button" className="rx-button rx-button-primary" disabled={busy} onClick={() => void readSelected()}>读取并分析此文件</button></div> : <>
            {contract && <section className="rx-contract" aria-label="函数输入与输出">
              <label>函数 <select value={contractIndex} onChange={event => { setContractIndex(Number(event.target.value)); setSourceOpen(false) }}>{focus?.contracts?.map((item, i) => <option key={`${item.symbol}:${item.line_start}`} value={i}>{item.symbol} · L{item.line_start}</option>)}</select></label>
              <div className="rx-fact"><span>输入</span><div><strong>源码声明的参数</strong><code>{contract.signature}</code></div></div>
              <div className="rx-fact"><span>处理</span><div><strong>{contract.symbol}</strong><p>{contract.description || '具体逻辑见函数源码；未推断其运行时行为。'}</p></div></div>
              <div className="rx-fact"><span>输出</span><div><strong>返回表达式 · 最多 3 处</strong>{contract.returns.length ? contract.returns.map((value, i) => <code key={i}>{value}</code>) : <p>未发现显式 return；不代表没有副作用或其他输出。</p>}</div></div>
              <button type="button" className="rx-contract-link" onClick={() => { setSourceStart(contract.line_start); setSourceOpen(true); setEdgeEvidence(undefined) }}>查看函数源码 · L{contract.line_start} ↗</button>
            </section>}
            {!contract && <>
            <div className="rx-fact"><span>来源</span><div><strong>{incoming.length ? `${incoming.length} 个文件引用它` : '暂无已解析的上游引用'}</strong><p>{incoming.slice(0, 3).map(link => basename(link.from_id.slice(5))).join('、') || '这不代表它不会被调用。'}</p></div></div>
            <div className="rx-fact"><span>职责</span><div><strong>{focus ? kindLabel[focus.kind] : fileRole(selected)}</strong><p>{focus?.role || '尚未提取到明确职责，可查看源码核对。'}</p>{focus?.confidence === 'inferred' && <small>类别按名称推断，实际职责待核对</small>}</div></div>
            <div className="rx-fact"><span>依赖</span><div><strong>{outgoing.length ? `引用 ${outgoing.length} 个本地模块` : '暂无已解析的下游引用'}</strong><p>{outgoing.slice(0, 3).map(link => basename(link.to_id.slice(5))).join('、') || '动态调用与外部依赖可能未被解析。'}</p></div></div>
            </>}
            {contract && <p className="rx-contract-refs">被 {incoming.length} 个文件引用 · 引用 {outgoing.length} 个本地模块</p>}
            <div className="rx-source-actions"><button type="button" className="rx-button" onClick={() => { setSourceOpen(value => !value); setSourceStart(1); setEdgeEvidence(undefined) }}>{sourceOpen ? '收起源码' : '查看源码'}</button>
              {focus && <button type="button" className="rx-button" onClick={() => { setRoot(focus.id); setPlaying(false) }}>从此文件追踪</button>}</div>
          </>}
          {sourceOpen && <section className="rx-source" aria-label="源码片段">{edgeEvidence && <p className="rx-muted">关系证据 · L{edgeEvidence.line_start}</p>}
            {sourceError ? <div role="alert"><p className="rx-error">{sourceError}</p><button className="rx-button" onClick={() => setSourceRetry(value => value + 1)}>重试源码</button></div> : !sourceData ? <p role="status">正在读取源码…</p> : <><p className="rx-muted">L{sourceData.line_start}–{sourceData.line_end} / {sourceData.total_lines} 行</p><pre>{sourceData.content.split('\n').map((line, i) => <span key={i}><em>{sourceData.line_start + i}</em>{line}{'\n'}</span>)}</pre><div className="rx-source-pager"><button className="rx-button" disabled={sourceStart <= 1} onClick={() => setSourceStart(Math.max(1, sourceStart - 80))}>上一段</button><button className="rx-button" disabled={sourceData.line_end >= sourceData.total_lines} onClick={() => setSourceStart(sourceData.line_end + 1)}>下一段</button></div></>}
          </section>}
          {githubPath && <a className="rx-source-link" href={githubPath + (edgeEvidence ? `#L${edgeEvidence.line_start}` : '')} target="_blank" rel="noreferrer">在 GitHub 核对固定版本 ↗</a>}
        </> : <div className="rx-inspector-empty">从左侧选择一个文件，查看职责、引用关系和源码。</div>}
      </aside>
    </div>
    <section className="rx-playback rx-panel" aria-label="源码路径推演"><div className="rx-playback-heading"><h2><span>03</span> 跟着源码走一遍</h2>
      <label>追踪起点 <select value={root || roots[0]?.id || ''} disabled={!roots.length} onChange={event => { setRoot(event.target.value); select(event.target.value.slice(5)) }}>
        {!roots.length && <option value="">等待源码分析</option>}{roots.map(module => <option key={module.id} value={module.id}>{module.paths[0]}</option>)}
      </select></label><span className="rx-badge">静态引用路径 · 未实际运行</span>
    </div>
      {trail.length ? <ol className="rx-steps">{trail.map((id, i) => <li key={id}><button type="button" aria-current={activeIndex === i ? 'step' : undefined} onClick={() => select(id.slice(5))} title={id.slice(5)}><span className="rx-step-number">{i + 1}</span><span><strong>{basename(id.slice(5))}</strong><small>{i === 0 ? '阅读起点' : links.find(link => link.from_id === trail[i - 1] && link.to_id === id)?.label || '源码引用'}</small></span></button>{i < trail.length - 1 && <span className="rx-step-arrow" aria-hidden="true">→</span>}</li>)}</ol> : <p className="rx-muted">读取关键文件后，按真实引用生成阅读路径。</p>}
      <div className="rx-playback-footer"><p aria-live="polite">{trail.length < 2 ? '当前没有可继续追踪的已解析引用。可选择其他文件或继续分析。' : activeIndex >= 0 ? `第 ${activeIndex + 1} / ${trail.length} 步 · ${selected}` : '选择步骤，联动查看文件与关系。'}<small>一条阅读分支，最多 6 步；不代表完整调用链或数据流。</small></p>
        <div><button type="button" className="rx-button rx-button-primary" disabled={trail.length < 2 || busy} onClick={() => { if (!playing && (activeIndex < 0 || activeIndex === trail.length - 1)) select(trail[0].slice(5)); setPlaying(value => !value) }}>{playing ? 'Ⅱ 暂停' : '▶ 播放路径'}</button><button type="button" className="rx-button" disabled={!trail.length || activeIndex === trail.length - 1 || busy} onClick={() => select(trail[Math.max(0, activeIndex + 1)].slice(5))}>下一步 →</button></div>
      </div>
    </section>
    <p className="rx-footnote">{online ? '源码仅在服务内存中暂存，空闲 30 分钟后过期；不下载归档，不写入本地快照。' : '分析来自已保存快照。'} 当前支持 Python、JavaScript / TypeScript 的部分静态引用；未解析部分不补造连线。</p>
  </div>
}
