import { ImportPanel } from '../components/ImportPanel'

export function HomePage() {
  return <main className="home" id="main-content" tabIndex={-1}>
    <div className="home-inner">
      <div className="eyebrow">UNDERSTAND · EXPLORE · RUN</div>
      <h1>打开一份仓库，<br />先看懂它。</h1>
      <p className="lede">从文件夹的作用开始，找到真正的入口。需要动手时，在同一页面填写参数、查看过程与结果。</p>
      <label className="input-label" htmlFor="repository">GitHub 仓库地址</label>
      <div className="input-shell">
        <input id="repository" disabled placeholder="粘贴 GitHub 仓库地址，例如 owner/repo" aria-describedby="import-note" />
        <button disabled>尚未开放</button>
      </div>
      <p className="home-tip" id="import-note">公开 GitHub URL 导入将在后续阶段开放。现在可以扫描本机已有样本，或上传你选择的目录。</p>
      <ImportPanel />
      <div className="home-choice"><span>对比演示模式</span><a className="primary" href="#/workspace">进入 PocketFlow 示例工作台 · 演示 ↗</a></div>
      <div className="home-features">
        <article><b>01 / 文件夹地图</b><p>先看结构和职责，再决定要读哪一个文件。</p></article>
        <article><b>02 / 可追溯解释</b><p>从已保存的真实源码核对定义、入口与行号。</p></article>
        <article><b>03 / 页面内运行</b><p>用演示表单体验进度、结果和失败后的下一步。</p></article>
      </div>
      <p className="footnote">真实地图只做静态扫描与本机保存，不调用模型。演示工作台保持独立，模拟结果不会写入项目。</p>
    </div>
  </main>
}
