import { useEffect, useState } from 'react'
import { Header } from './components/Header'
import { HomePage } from './pages/HomePage'
import { WorkspacePage } from './pages/WorkspacePage'

export default function App() {
  const [workspace, setWorkspace] = useState(window.location.hash === '#/workspace')
  useEffect(() => {
    const onNavigate = () => { setWorkspace(window.location.hash === '#/workspace'); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', onNavigate)
    return () => window.removeEventListener('hashchange', onNavigate)
  }, [])
  useEffect(() => { document.title = workspace ? 'PocketFlow 工作台 · RepoLens 演示' : 'RepoLens · 先看懂一份仓库' }, [workspace])
  return <><Header workspace={workspace} />{workspace ? <WorkspacePage /> : <HomePage />}</>
}
