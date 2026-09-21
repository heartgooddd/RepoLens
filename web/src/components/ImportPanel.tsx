import { useEffect, useRef, useState } from 'react'
import { importBuiltin, importDirectory, projects } from '../api/projects'
import type { ImportResult, ProjectList } from '../api/projects'

export function ImportPanel() {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [history, setHistory] = useState<ProjectList>()
  const [historyError, setHistoryError] = useState('')
  const [retry, setRetry] = useState(0)
  const picker = useRef<HTMLInputElement>(null)
  useEffect(() => {
    const controller = new AbortController()
    setHistoryError('')
    projects(0, controller.signal).then(setHistory).catch(error => { if (!controller.signal.aborted) setHistoryError(error.message) })
    return () => controller.abort()
  }, [retry])
  async function run(operation: () => Promise<ImportResult>) {
    setBusy(true); setError(''); setMessage('正在读取源码、扫描并保存…')
    try {
      const result = await operation()
      // The URL contains the durable project id. Refresh reads SQLite through the API.
      window.location.hash = `/projects/${result.detail.project.id}`
    } catch (error) { setError(error instanceof Error ? error.message : '导入失败，请重试。') }
    finally { setBusy(false); setMessage(''); if (picker.current) picker.current.value = '' }
  }
  return <section className="import-area" aria-label="真实项目导入" aria-busy={busy}>
    <div className="import-actions">
      <button className="primary" disabled={busy} onClick={() => void run(importBuiltin)}>扫描 PocketFlow 样本 ↗</button>
      <button className="secondary" disabled={busy} onClick={() => picker.current?.click()}>选择本地文件夹</button>
      <input ref={element => { picker.current = element; if (element) element.setAttribute('webkitdirectory', '') }} type="file" multiple hidden aria-label="上传本地目录" onChange={event => { const files = Array.from(event.currentTarget.files ?? []); void run(() => importDirectory(files, setMessage)) }} />
    </div>
    <p className="muted">仅上传选定目录中的文本源码；过滤环境文件、常见凭据、依赖和构建产物。单文件 ≤ 1 MiB，总量 ≤ 8 MiB，最多 500 个文件。上传前请检查源码中没有硬编码密钥。</p>
    {message && <p role="status" className="import-status">{message}</p>}
    {error && <p role="alert" className="error-note">{error}</p>}
    <p className="muted">空目录在部分浏览器中不会触发选择事件；若没有反应，请选择含源码文件的目录。</p>
    <div className="saved-projects">
      <h2>已保存的项目</h2>
      {historyError ? <p className="error-note">{historyError} <button className="text-button" onClick={() => setRetry(value => value + 1)}>重试连接</button></p> : !history ? <p className="muted">正在读取项目列表…</p> : <>
        {!history.items.length && <p className="muted">还没有项目。从 PocketFlow 样本或本地文件夹开始。</p>}
        {history.items.map(item => <a className="file-card" key={item.id} href={`#/projects/${item.id}`}><b>{item.name}</b><small>{item.source_label} · {item.snapshot_count} 份快照</small></a>)}
        {history.items.length < history.total && <button className="text-button" onClick={() => void projects(history.items.length).then(next => setHistory({ ...next, items: [...history.items, ...next.items] })).catch(error => setHistoryError(error.message))}>加载更多项目</button>}
      </>}
    </div>
  </section>
}
