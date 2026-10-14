import { useEffect, useId, useRef, useState } from 'react'
import type { ArchitectureConnection } from '../api/projects'
import { modulePath, type ModuleLink, type ProjectModule } from './project-overview'

type Props = {
  name: string; modules: ProjectModule[]; links: ModuleLink[]; active?: ProjectModule;
  chooseModule: (id: string) => void; chooseFile: (path: string) => void;
  inspect: (link: ArchitectureConnection) => void;
}
export function ProjectOverview({ name, modules, links, active, chooseModule, chooseFile, inspect }: Props) {
  const host = useRef<HTMLDivElement>(null), marker = useId().replace(/:/g, '')
  const [width, setWidth] = useState(900), [showAll, setShowAll] = useState(false), [query, setQuery] = useState('')
  useEffect(() => {
    if (!host.current) return
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(host.current)
    return () => observer.disconnect()
  }, [])
  useEffect(() => { setQuery('') }, [active?.id])
  const visible = showAll ? modules : modules.slice(0, 18)
  const lanes = [0, 1, 2].map(lane => visible.filter(module => module.lane === lane))
  const nodeWidth = (width - 140) / 3, height = Math.max(340, Math.max(...lanes.map((lane, column) => lane.length * (column === 2 ? 80 : 152))) + 65)
  const positions = new Map(lanes.flatMap((lane, column) => lane.map((module, row) => [module.id, { x: 24 + column * (nodeWidth + 46), y: 58 + row * (column === 2 ? 80 : 152) }] as const)))
  const connected = new Set(links.filter(link => link.from === active?.id || link.to === active?.id).flatMap(link => [link.from, link.to]))
  const relevant = active ? links.filter(link => link.from === active.id || link.to === active.id) : links
  const matchingFiles = active?.files.filter(file => file.path.toLowerCase().includes(query.toLowerCase())) || []
  const byId = new Map(modules.map(module => [module.id, module]))
  const detail = <div className={`rx-overview-detail ${active ? 'has-module' : ''}`}>
      {active && <section className="rx-module-files" aria-label="模块内文件"><div className="rx-detail-heading"><h3>{active.title} · 文件</h3><span>{active.loaded}/{active.files.length} 已读取</span></div><label className="rx-module-search"><span className="sr-only">查找模块内文件</span><input type="search" value={query} placeholder="查找这个模块中的文件…" onChange={event => setQuery(event.target.value)} /></label>
        <div className="rx-module-file-list">{matchingFiles.slice(0, 100).map(file => <button type="button" key={file.path} onClick={() => chooseFile(file.path)} aria-label={`分析文件 ${file.path}`}><span className="rx-file-icon" aria-hidden="true">▤</span><span><strong>{file.path.split('/').at(-1)}</strong><small>{file.path}</small></span><small>{file.loaded ? '查看分析 →' : '未读取 →'}</small></button>)}{!matchingFiles.length && <p className="rx-muted">没有匹配的文件。</p>}{matchingFiles.length > 100 && <p className="rx-muted">展示前 100 个文件，共 {matchingFiles.length} 个。可搜索定位其他文件。</p>}</div>
      </section>}
      <section className="rx-module-connections" aria-label="模块引用依据"><div className="rx-detail-heading"><h3>{active ? '这个模块与谁协作' : '从模块关系，读懂源码连接'}</h3><span>{active ? active.internal.length + ' 条内部引用' : '可展开核对依据'}</span></div>
        {!relevant.length && <p className="rx-muted">当前已读源码尚未解析出{active ? '这个模块的' : ''}跨模块引用。模块仍按完整可读目录展示；未读取和动态关联不会补造连线。</p>}
        <div className="rx-module-edge-list">{relevant.map(link => <details key={JSON.stringify([link.from, link.to])}><summary><span>{byId.get(link.from)!.title}<small>{modulePath(byId.get(link.from)!)}</small></span><b aria-hidden="true">→</b><span>{byId.get(link.to)!.title}<small>{modulePath(byId.get(link.to)!)}</small></span><em>{link.references.length} 条引用</em></summary>
          {link.references.map((reference, i) => <button type="button" key={i} disabled={!reference.evidence.length} onClick={() => inspect(reference)}><span>{reference.from_id.slice(5)} → {reference.to_id.slice(5)}</span><small>{reference.evidence[0] ? `核对源码 · L${reference.evidence[0].line_start}` : '无行号证据'}</small></button>)}
        </details>)}</div>
      </section>
    </div>
  return <section className="rx-panel rx-overview-panel" aria-label="项目模块总览">
    <div className="rx-panel-title"><h2><span>02</span> {active ? '走进模块' : '整个项目，如何协作'}</h2><span className="rx-badge">{modules.length} 个目录分组</span></div>
    <div className="rx-overview-intro"><div><div className="rx-eyebrow">{active ? 'MODULE / FILES' : 'PROJECT / MODULE MAP'}</div><h3>{active ? active.title : name + ' · 模块协作总图'}</h3><p>{active ? `${modulePath(active)} · 先看模块的关联，再选择文件查看分析。` : '先看项目由哪些部分组成，再点击模块展开文件与源码。'}</p></div>
      <div className="rx-overview-stats"><strong>{active ? active.files.length : modules.reduce((sum, module) => sum + module.files.length, 0)}</strong><span>{active ? '模块内文件' : '可读文件'}</span><strong>{relevant.length}</strong><span>跨模块关系</span></div>
    </div>
    {active && detail}
    <div className="rx-overview-scroll" tabIndex={0} aria-label="模块地图，可横向滚动"><div className="rx-overview-canvas" ref={host} style={{ height }}>
      <div className="rx-overview-lanes"><span>入口与界面</span><span>逻辑与数据</span><span>支撑与文档</span></div>
      <svg className="rx-overview-lines" width={width} height={height} aria-hidden="true"><defs><marker id={marker} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10Z" fill="#69a5a2" /></marker></defs>
        {links.map(link => {
          const a = positions.get(link.from), b = positions.get(link.to)
          if (!a || !b) return null
          const sameColumn = a.x === b.x, forward = b.x > a.x
          const ax = a.x + (sameColumn || forward ? nodeWidth : 0), bx = b.x + (sameColumn || !forward ? nodeWidth : 0)
          const ay = a.y + (byId.get(link.from)!.lane === 2 ? 32 : 64), by = b.y + (byId.get(link.to)!.lane === 2 ? 32 : 64), bend = sameColumn ? ax + 28 : (ax + bx) / 2
          return <path key={JSON.stringify([link.from, link.to])} d={`M${ax} ${ay} C${bend} ${ay},${bend} ${by},${bx} ${by}`} markerEnd={`url(#${marker})`} opacity={active && link.from !== active.id && link.to !== active.id ? .12 : .85} />
        })}
      </svg>
      {visible.map(module => {
        const position = positions.get(module.id)!
        const outgoing = links.filter(link => link.from === module.id).length
        return <button key={module.id} type="button" className={`rx-module-card rx-module-lane-${module.lane}${active?.id === module.id ? ' is-selected' : ''}${active && active.id !== module.id && !connected.has(module.id) ? ' is-muted' : ''}`} style={{ left: position.x, top: position.y, width: nodeWidth }} aria-label={`展开模块 ${module.title} · ${modulePath(module)}`} aria-pressed={active?.id === module.id} onClick={() => chooseModule(module.id)}>
          <span className="rx-module-card-top"><span className="rx-module-icon" aria-hidden="true">{['▧', '◇', '▤'][module.lane]}</span><small>{module.files.length} 个文件</small><span aria-hidden="true">↗</span></span>
          <strong>{module.title}</strong><code title={modulePath(module)}>{modulePath(module)}</code>
          <span className="rx-module-card-bottom"><span>{module.loaded ? `已读 ${module.loaded}/${module.files.length}` : '正文待读取'}</span><span>{outgoing ? `引用 ${outgoing} 个模块` : `${module.internal.length} 条内部引用`}</span></span>
        </button>
      })}
      {!modules.length && <p className="rx-graph-empty">正在等待项目文件目录…</p>}
    </div></div>
    {!showAll && modules.length > 18 && <button className="rx-button rx-show-modules" onClick={() => setShowAll(true)}>展开全部 {modules.length} 个模块分组</button>}
    <div className="rx-overview-caption"><span><i /> 箭头：已解析的跨模块源码引用</span><span>分组与名称按目录推断；布局不代表执行顺序。</span></div>
    {!active && detail}
    <div className="rx-overview-guide"><span><b>1</b> 看整体模块</span><span aria-hidden="true">→</span><span><b>2</b> 展开模块文件</span><span aria-hidden="true">→</span><span><b>3</b> 分析单个文件</span></div>
  </section>
}
