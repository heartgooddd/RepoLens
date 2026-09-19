import { folders } from '../demo/pocketflow'
import type { FolderId } from '../types'

export function FolderMap({ selected, onSelect }: { selected: FolderId; onSelect: (id: FolderId) => void }) {
  return <aside className="panel" id="folder-map" aria-label="文件夹地图">
    <div className="panel-pad">
      <div className="side-header"><h2 className="small-title">文件夹地图</h2><span className="count">演示数据</span></div>
      <nav aria-label="项目文件夹与入口">
        {folders.map((folder, index) => <div key={folder.id}>
          {(index === 0 || index === 3) && <div className="mini-label">{index === 0 ? '项目结构' : '关键入口'}</div>}
          <button className={`tree-item ${selected === folder.id ? 'active' : ''} ${index === 1 || index === 2 ? 'nested' : ''}`} aria-pressed={selected === folder.id} onClick={() => onSelect(folder.id)}>
            <span className="tree-icon" aria-hidden="true">{index < 3 ? '▣' : '◇'}</span>{folder.label}
          </button>
        </div>)}
      </nav>
    </div>
    <div className="side-footer">固定样本 · 人工整理<br />仅展示选定目录与关键入口。</div>
  </aside>
}
