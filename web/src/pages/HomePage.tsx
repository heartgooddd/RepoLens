import { ImportPanel } from '../components/ImportPanel'
import { GitHubImportForm } from '../components/GitHubImportForm'

export function HomePage() {
  return <main className="home" id="main-content" tabIndex={-1}>
    <div className="home-inner">
      <div className="eyebrow">UNDERSTAND · EXPLORE · RUN</div>
      <h1>打开一份仓库，<br />先看懂它。</h1>
      <p className="lede">从文件夹的作用开始，找到真正的入口。需要动手时，在同一页面填写参数、查看过程与结果。</p>
      <GitHubImportForm />
      <ImportPanel />
      <div className="home-choice"><span>对比演示模式</span><a className="primary" href="#/workspace">进入 PocketFlow 示例工作台 · 演示 ↗</a></div>
      <div className="home-features">
        <article><b>01 / 文件夹地图</b><p>先看结构和职责，再决定要读哪一个文件。</p></article>
        <article><b>02 / 可追溯解释</b><p>从已保存的真实源码核对定义、入口与行号。</p></article>
        <article><b>03 / 页面内运行</b><p>用演示表单体验进度、结果和失败后的下一步。</p></article>
      </div>
      <p className="footnote">GitHub 与本地导入只做静态扫描和本机保存，不执行仓库代码。模型任务读取已固定的同一快照；演示工作台保持独立。</p>
    </div>
  </main>
}
