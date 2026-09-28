import { useEffect, useState } from 'react'
import { project, source } from '../api/projects'
import { TaskPanel } from '../components/TaskPanel'
import { TaskResult } from '../components/TaskResult'
import { DemoFolderVisual, DemoOverview, SnapshotFolderVisual, SnapshotOverview } from '../components/ProjectVisuals'
import { folders as pocketFlowFolders, snapshot as pocketFlowCommit } from '../demo/pocketflow'
import type { FolderId } from '../types'
import type { Run } from '../api/runs'
import type { Detail, Snapshot, SourceSlice } from '../api/projects'

const parent = (path: string) => path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '.'

export function RepositoryPage({ id }: { id: string }) {
  const [detail, setDetail] = useState<Detail>()
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setError(''); setDetail(undefined)
    project(id, controller.signal).then(setDetail).catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [id, retry])
  if (!detail) return <main className="wrap" id="main-content" tabIndex={-1}><h1>打开已保存的项目</h1>{error ? <div role="alert"><p>{error}</p><button className="secondary" onClick={() => setRetry(value => value + 1)}>重新读取</button></div> : <p role="status">正在读取项目快照…</p>}<p><a href="#/">返回输入页</a></p></main>
  return <RepositoryWorkspace key={detail.project.id} detail={detail} />
}

function RepositoryWorkspace({ detail }: { detail: Detail }) {
  const [snapshotId, setSnapshotId] = useState(detail.snapshots[0]?.id)
  const snapshot = detail.snapshots.find(item => item.id === snapshotId)
  return <main className="wrap" id="main-content" tabIndex={-1}>
    <div className="page-heading">
      <div><div className="eyebrow">PROJECT WORKSPACE / SOURCE</div><h1>{detail.project.name} 项目地图</h1><p className="lede">先看 README 与目录结构图，再沿源码证据核对具体作用。</p></div>
      <div className="source-pill"><span className="dot" /><strong>真实快照</strong><span>· {snapshot?.commit_sha?.slice(0, 7) || snapshot?.revision.slice(7, 15)}</span></div>
    </div>
    {detail.snapshots.length > 1 && <label>快照版本 <select value={snapshotId} onChange={event => setSnapshotId(event.target.value)}>{detail.snapshots.map(item => <option key={item.id} value={item.id}>{item.created_at} · {item.revision.slice(0, 20)}</option>)}</select></label>}
    {snapshot && detail.project.source_type === 'github' && <section className="snapshot-version" aria-label="GitHub 固定版本">
      <div><strong>公开 GitHub 来源</strong><span>{detail.project.source_label}</span></div>
      <div><strong>固定 Commit</strong><code>{snapshot.commit_sha}</code></div>
      <p>地图扫描与运行分析共用此快照；再次导入同一 Commit 会复用源码快照，模型结果另按模型与参数隔离。</p>
    </section>}
    {snapshot ? <SnapshotWorkspace key={snapshot.id} snapshot={snapshot} name={detail.project.name} sourceType={detail.project.source_type} sourceLabel={detail.project.source_label} /> : <p className="muted">此项目尚无源码快照，请返回输入页重新导入。</p>}
  </main>
}

function SnapshotWorkspace({ snapshot, name, sourceType, sourceLabel }: { snapshot: Snapshot; name: string; sourceType: string; sourceLabel: string }) {
  const [result, setResult] = useState<Run>()
  const [folderPath, setFolderPath] = useState('.')
  const [focusedRole, setFocusedRole] = useState<FolderId>('root')
  const [filePath, setFilePath] = useState(snapshot.files.find(file => file.path === 'main.py')?.path || snapshot.files[0]?.path || '')
  const [start, setStart] = useState(1)
  const [loadedSlice, setSlice] = useState<SourceSlice>()
  const slice = loadedSlice?.path === filePath && loadedSlice.line_start === start ? loadedSlice : undefined
  const [error, setError] = useState('')
  const card = snapshot.folder_cards.find(item => item.path === folderPath)
  const visibleFolders = snapshot.folder_cards.filter(item => item.path === '.' || !item.path.includes('/') || parent(item.path) === folderPath || folderPath === item.path || folderPath.startsWith(`${item.path}/`))
  const files = snapshot.files.filter(file => parent(file.path) === folderPath)
  const refs = card?.evidence_refs.filter(ref => ref.file_path === filePath) ?? []
  const knownPocketFlow = sourceType === 'github' && /^https:\/\/github\.com\/The-Pocket\/PocketFlow-Tutorial-Codebase-Knowledge(?:\.git)?\/?$/i.test(sourceLabel)
    && snapshot.commit_sha === pocketFlowCommit && ['main.py', 'flow.py', 'nodes.py'].every(path => snapshot.files.some(file => file.path === path))
  const knownRole = knownPocketFlow ? pocketFlowFolders.find(item => item.id === focusedRole) : undefined
  const displayPath = knownRole && ['main', 'flow', 'nodes'].includes(focusedRole) ? `${focusedRole}.py` : folderPath
  const scroll = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  useEffect(() => {
    const controller = new AbortController()
    setSlice(undefined); setError('')
    if (filePath) source(snapshot.id, filePath, start, controller.signal).then(setSlice).catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => controller.abort()
  }, [snapshot.id, filePath, start])
  function chooseFolder(path: string) {
    setResult(undefined); setFolderPath(path); setFilePath(snapshot.files.find(file => parent(file.path) === path)?.path || ''); setStart(1)
    setFocusedRole(path === 'utils' || path === 'docs' ? path : 'root')
    if (window.innerWidth < 761) scroll('folder-detail')
  }
  function chooseKnownRole(id: FolderId) {
    setResult(undefined); setFocusedRole(id); setStart(1)
    const path = id === 'utils' || id === 'docs' ? id : '.'
    setFolderPath(path)
    setFilePath(id === 'main' || id === 'flow' || id === 'nodes' ? `${id}.py` : snapshot.files.find(file => parent(file.path) === path)?.path || '')
    scroll('folder-detail')
  }
  function chooseFromOverview(path: string) {
    chooseFolder(path)
    scroll('folder-detail')
  }
  return <>
    {knownPocketFlow ? <DemoOverview source onSelect={chooseKnownRole} /> : <SnapshotOverview snapshot={snapshot} name={name} onSelect={chooseFromOverview} />}
    <nav className="mobile-jump" aria-label="工作台区域导航"><button onClick={() => scroll('folder-map')}>文件夹</button><button onClick={() => scroll('folder-detail')}>源码与说明</button><button onClick={() => scroll('run-panel')}>运行窗口</button></nav>
    <div className="workspace">
      <aside className="panel" id="folder-map" aria-label="真实文件夹地图">
        <div className="panel-pad"><div className="side-header"><h2 className="small-title">文件夹地图</h2><span className="count">{snapshot.files.length} 文件</span></div>
          <div className="repository-tree">{visibleFolders.map(item => <button className={`tree-item ${item.path === folderPath ? 'active' : ''}`} key={item.id} aria-pressed={item.path === folderPath} onClick={() => chooseFolder(item.path)}><span className="tree-icon" aria-hidden="true">▱</span><span>{item.path === '.' ? '/ 根目录' : item.path}</span></button>)}</div>
          <p className="muted">点击目录可展开下一级。</p>
        </div>
        <div className="side-footer">只展示过滤后保存的文本文件。目录结构来自此快照，不包含环境文件、依赖或二进制资源。</div>
      </aside>
      <section className="panel main-panel" id="folder-detail" aria-label="真实源码与说明">
        <div hidden={!!result}><div className="main-top"><div className="breadcrumbs">{name} / {displayPath}</div><div className="folder-title-row"><h2>{knownRole?.title ?? card?.title ?? folderPath}</h2><span className={`tag ${!knownRole && card?.claim_type === 'unverified' ? 'amber' : ''}`}>{knownRole ? '固定版本整理' : card?.claim_type === 'fact' ? '源码事实' : card?.claim_type === 'inference' ? '推断' : '职责待核实'}</span></div><p className="folder-description">{knownRole?.description ?? card?.description}</p>
          {!knownRole && card?.inference && <div className="evidence-card"><b>名称推断 · 待核实</b><p>{card.inference}</p></div>}
        </div>
        <div className="main-content">
          {knownPocketFlow ? <DemoFolderVisual source id={focusedRole} onSelect={chooseKnownRole} /> : <SnapshotFolderVisual snapshot={snapshot} card={card} />}
          <div className="section-heading"><h3>此目录中的文件</h3><span className="section-note">点击核对保存的源码</span></div>
          {!files.length && <p className="muted">此目录只有子目录，请从左侧继续展开。</p>}
          <div className="repository-files">{files.map(file => <button key={file.path} className={`file-card ${file.path === filePath ? 'selected' : ''}`} aria-pressed={file.path === filePath} onClick={() => { setFilePath(file.path); setStart(1); if (knownPocketFlow) setFocusedRole(file.path === 'main.py' ? 'main' : file.path === 'flow.py' ? 'flow' : file.path === 'nodes.py' ? 'nodes' : folderPath === 'utils' || folderPath === 'docs' ? folderPath : 'root') }}><b>{file.path}</b><small>{file.size_bytes.toLocaleString()} bytes</small></button>)}</div>
          {filePath && <>
            <div className="section-heading"><h3>定义与源码线索</h3><span className="section-note">静态提取 · 未执行</span></div>
            {refs.length ? <div className="source-symbols">{refs.map(ref => <button className="text-button" key={ref.id} onClick={() => setStart(ref.line_start)}>{ref.symbol || '文本线索'} · L{ref.line_start}–{ref.line_end}</button>)}</div> : <p className="muted">{knownRole ? '静态扫描未提取到定义或配置线索；可阅读原始文件核对上方的固定版本说明。' : '没有提取到可解释功能的定义或配置线索，职责待核实。可阅读原始文件。'}</p>}
            <section className="source-preview" aria-label="真实源码片段">
              <h3>{filePath}</h3>
              {error ? <p role="alert" className="error-note">{error}</p> : !slice ? <p role="status">正在读取并校验源码…</p> : <>
                <p className="muted">已校验 SHA-256 · {slice.total_lines ? `L${slice.line_start}–${slice.line_end} / 共 ${slice.total_lines} 行` : '空文件'}</p>
                <pre>{slice.content.split('\n').map((line, i) => <span className="code-line" key={i}><span className="line-number">{slice.line_start + i}</span><code>{line}</code>{'\n'}</span>)}</pre>
                <div className="source-pagination"><button className="secondary" disabled={start <= 1} onClick={() => setStart(Math.max(1, start - 80))}>上一段</button><button className="secondary" disabled={slice.line_end >= slice.total_lines} onClick={() => setStart(slice.line_end + 1)}>下一段</button></div>
              </>}
            </section>
          </>}
        </div>
      </div>{result && <TaskResult key={result.id} run={result} onBack={() => setResult(undefined)} />}
      </section>
      <TaskPanel snapshot={snapshot} onResult={run=>{setResult(run);scroll('folder-detail')}} />
    </div>
    <p className="footnote">真实文件与 SQLite 记录 · 事实附源码位置，名称推断单独标记 · 扫描与运行共用此快照 · 输入源码不作为程序执行。</p>
  </>
}
