import { ImportPanel } from '../components/ImportPanel'
import { GitHubImportForm } from '../components/GitHubImportForm'

export function HomePage() {
  return <main className="home" id="main-content" tabIndex={-1}>
    <div className="home-inner">
      <div className="eyebrow">UNDERSTAND · EXPLORE · RUN</div>
      <h1>打开一份仓库，<br />先看懂它。</h1>
      <p className="lede">粘贴 GitHub 链接，从文件结构看起，沿着模块关系理解代码。选中一步，文件、关系图和源码同步定位。</p>
      <GitHubImportForm />
      <ImportPanel />
      <div className="home-choice"><span>对比演示模式</span><a className="primary" href="#/workspace">进入 PocketFlow 示例工作台 · 演示 ↗</a></div>
      <div className="home-features">
        <article><b>01 / 可视化项目总览</b><p>先看项目目标与重要目录，再决定要读哪一个文件。</p></article>
        <article><b>02 / 可追溯解释</b><p>从已保存的真实源码核对定义、入口与行号。</p></article>
        <article><b>03 / 路径联动推演</b><p>沿真实源码引用逐步阅读，区分静态路径与实际运行。</p></article>
      </div>
      <p className="footnote">在线模式仅在内存暂存已读源码；保存快照和本地导入可持久化。两种方式都不执行导入仓库的代码。</p>
    </div>
  </main>
}
