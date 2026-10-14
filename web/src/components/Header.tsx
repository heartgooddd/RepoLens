export function Header({ workspace, demo = false, online = false }: { workspace: boolean; demo?: boolean; online?: boolean }) {
  return <>
    <a className="skip-link" href={workspace ? '#/workspace' : '#/'} onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus() }}>跳到主要内容</a>
    <header className="topbar">
      <a className="brand" href="#/" aria-label="RepoLens 首页"><span className="brand-mark" aria-hidden="true" />RepoLens</a>
      <div className="top-actions">
        <span className="draft">{online ? '在线浏览 · 按需读取' : demo ? '演示模式 · 不调用模型' : '本地工作区 · 真实快照'}</span>
        <a className="top-link" href={workspace ? '#/' : '#/workspace'}>{workspace ? '返回输入页' : '示例工作台'} ↗</a>
      </div>
    </header>
  </>
}
