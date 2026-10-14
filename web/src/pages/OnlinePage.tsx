import { useCallback, useEffect, useRef, useState } from 'react'
import { onlineProject, onlineSource, readOnline } from '../api/online'
import type { OnlineProject } from '../api/online'
import { RepositoryExplorer } from '../components/RepositoryExplorer'

export function OnlinePage({ id }: { id: string }) {
  const [data, setData] = useState<OnlineProject>()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)
  const alive = useRef(false)
  const reading = useRef(false)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  const read = useCallback(async (paths: string[] = []) => {
    if (reading.current) return
    reading.current = true; setBusy(true); setError('')
    try {
      const result = await readOnline(id, paths)
      if (alive.current) setData(result)
    } catch (reason) {
      if (alive.current) {
        setError(reason instanceof Error ? reason.message : '读取失败，请重试。')
        try { const latest = await onlineProject(id); if (alive.current) setData(latest) } catch { /* retain original error */ }
      }
    } finally { reading.current = false; if (alive.current) setBusy(false) }
  }, [id])
  const started = useRef(false)
  useEffect(() => {
    const controller = new AbortController()
    setError('')
    onlineProject(id, controller.signal).then(result => {
      if (controller.signal.aborted) return
      setData(result)
      if (!result.loaded_count && !started.current) { started.current = true; void read() }
    }).catch(reason => { if (!controller.signal.aborted) setError(reason.message) })
    return () => controller.abort()
  }, [id, retry, read])
  const loadSource = useCallback((path: string, start: number, signal: AbortSignal) => onlineSource(id, path, start, signal), [id])
  return <main className="explorer-page" id="main-content" tabIndex={-1}>
    {data ? <RepositoryExplorer name={data.name} files={data.files} architecture={data.architecture} repositoryUrl={data.repository_url}
      commit={data.commit_sha} online busy={busy} error={error} warnings={data.warnings} excludedCount={data.excluded_count} onRead={read} loadSource={loadSource} />
      : <section className="analysis-loading"><h1>打开在线项目</h1>{error ? <><p role="alert">{error}</p><button className="secondary" onClick={() => setRetry(value => value + 1)}>重新读取</button><p><a href="#/">返回首页，重新打开仓库</a></p></> : <p role="status">正在读取项目目录…</p>}</section>}
  </main>
}
