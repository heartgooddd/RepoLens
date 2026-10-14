import { useEffect, useState } from 'react'
import { Header } from './components/Header'
import { HomePage } from './pages/HomePage'
import { WorkspacePage } from './pages/WorkspacePage'
import { OnlinePage } from './pages/OnlinePage'
import { RepositoryPage } from './pages/RepositoryPage'

export default function App() {
  const [route, setRoute] = useState(window.location.hash)
  const demo = route === '#/workspace'
  const projectId = route.match(/^#\/projects\/([\w-]+)$/)?.[1]
  const onlineId = route.match(/^#\/online\/([\w-]+)$/)?.[1]
  const workspace = demo || Boolean(projectId) || Boolean(onlineId)
  useEffect(() => {
    const onNavigate = () => { setRoute(window.location.hash); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', onNavigate)
    return () => window.removeEventListener('hashchange', onNavigate)
  }, [])
  useEffect(() => { document.title = demo ? 'PocketFlow 工作台 · RepoLens 演示' : onlineId ? '在线项目可视化 · RepoLens' : projectId ? '真实项目地图 · RepoLens' : 'RepoLens · 先看懂一份仓库' }, [demo, projectId, onlineId])
  return <><Header workspace={workspace} demo={demo} online={Boolean(onlineId)} />{onlineId ? <OnlinePage key={onlineId} id={onlineId} /> : demo ? <WorkspacePage /> : projectId ? <RepositoryPage key={projectId} id={projectId} /> : <HomePage />}</>
}
