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
      <p className="home-tip" id="import-note">仓库导入尚未接入。先用准备好的 PocketFlow 演示样本，体验文件夹浏览与模拟运行。</p>
      <button className="local-preview" disabled>选择本地文件夹 · 尚未开放</button>
      <div className="home-choice"><span>从示例开始</span><a className="primary" href="#/workspace">进入 PocketFlow 示例工作台 ↗</a></div>
      <div className="home-features">
        <article><b>01 / 文件夹地图</b><p>先看结构和职责，再决定要读哪一个文件。</p></article>
        <article><b>02 / 可追溯解释</b><p>查看人工整理的说明与固定版本源码片段。</p></article>
        <article><b>03 / 页面内运行</b><p>用演示表单体验进度、结果和失败后的下一步。</p></article>
      </div>
      <p className="footnote">当前为演示原型。预置说明与结果不会读取你的仓库，也不会消耗模型额度。</p>
    </div>
  </main>
}
