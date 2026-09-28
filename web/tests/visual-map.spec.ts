import { expect, test } from '@playwright/test'

const projectId = '22222222-2222-4222-8222-222222222222'
const snapshotId = '33333333-3333-4333-8333-333333333333'
const pocketFlowCommit = '05b24cbbb0fe409c5e23c9791f0342f07524ffdc'
const evidence = { id: '55555555-5555-4555-8555-555555555555', file_path: 'README.md', line_start: 1, line_end: 3, symbol: null, excerpt: '# RepoLens\n\n开源 AI 项目拆解与学习平台工作区。' }

async function mockTaskPanel(page: import('@playwright/test').Page) {
  await page.route('**/api/runner', route => route.fulfill({ json: { real_enabled: false, real_ready: false, model: { api_key_configured: false, configuration_complete: false, missing: [] } } }))
  await page.route('**/api/recipes', route => route.fulfill({ json: { items: [] } }))
  await page.route('**/api/runs?*', route => route.fulfill({ json: { items: [], total: 0 } }))
}

test('演示先显示整体路线，点击辅助文件夹后显示它的输入与产出', async ({ page }) => {
  await page.goto('/#/workspace')
  await expect(page.locator('.overview-board')).toContainText('一张图看懂 PocketFlow')
  await expect(page.locator('.visual-flow .visual-step')).toHaveCount(5)
  await expect(page.getByRole('button', { name: '项目总览' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'utils/ 为节点提供文件读取和模型调用' }).click()
  await expect(page.locator('.role-board')).toContainText('读取本地或 GitHub 文件，封装模型调用')
  await expect(page.locator('.role-board')).toContainText('供 nodes.py 使用的源码文本和模型回答')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('真实仓库展示 README 摘要、目录关系和可核对的职责线索', async ({ page }) => {
  const folder = (path: string, id: string) => ({ id, snapshot_id: snapshotId, path, title: path === '.' ? '项目根目录' : path, description: '静态扫描目录。', claim_type: 'fact', inference: null, evidence_refs: path === '.' ? [evidence] : [] })
  await mockTaskPanel(page)
  await page.route(`**/api/projects/${projectId}`, route => route.fulfill({ json: {
    project: { id: projectId, name: 'RepoLens', source_type: 'github', source_label: 'https://github.com/heartgooddd/RepoLens', created_at: '2026-09-28T00:00:00Z' },
    snapshots: [{ id: snapshotId, revision: 'git:' + 'a'.repeat(40), commit_sha: 'a'.repeat(40), created_at: '2026-09-28T00:00:00Z',
      files: [
        { path: 'README.md', size_bytes: 50, sha256: 'a'.repeat(64) },
        { path: 'web/src/App.tsx', size_bytes: 60, sha256: 'b'.repeat(64) },
        { path: 'server/app/main.py', size_bytes: 70, sha256: 'c'.repeat(64) },
        { path: 'docs/guide.md', size_bytes: 80, sha256: 'd'.repeat(64) },
      ],
      folder_cards: [folder('.', '1'), folder('web', '2'), folder('web/src', '3'), folder('server', '4'), folder('server/app', '5'), folder('docs', '6')],
    }],
  } }))
  await page.route(`**/api/snapshots/${snapshotId}/source**`, route => route.fulfill({ json: { path: 'README.md', sha256: 'a'.repeat(64), line_start: 1, line_end: 3, total_lines: 3, content: evidence.excerpt } }))
  await page.goto(`/#/projects/${projectId}`)
  await expect(page.locator('.overview-board')).toContainText('开源 AI 项目拆解与学习平台工作区。')
  await expect(page.locator('.structure-node')).toHaveCount(3)
  await expect(page.locator('.overview-board')).toContainText('可能负责页面渲染与交互')
  await expect(page.locator('.overview-board')).toContainText('连线只表示包含关系')
  await page.getByRole('button', { name: /顶层目录 web\/ 可能负责页面渲染与交互/ }).click()
  await expect(page.locator('.role-board')).toContainText('当前目录')
  await expect(page.locator('.role-board')).toContainText('web/')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('固定 PocketFlow GitHub 版本使用演示中的流程图并能定位真实源码', async ({ page }) => {
  await mockTaskPanel(page)
  const files = ['main.py', 'flow.py', 'nodes.py', 'utils/crawl_local_files.py', 'docs/design.md'].map(path => ({ path, size_bytes: 80, sha256: 'a'.repeat(64) }))
  const folder = (path: string, id: string) => ({ id, snapshot_id: snapshotId, path, title: path, description: '静态扫描目录。', claim_type: 'unverified', inference: null, evidence_refs: [] })
  await page.route(`**/api/projects/${projectId}`, route => route.fulfill({ json: {
    project: { id: projectId, name: 'PocketFlow-Tutorial-Codebase-Knowledge', source_type: 'github', source_label: 'https://github.com/The-Pocket/PocketFlow-Tutorial-Codebase-Knowledge', created_at: '2026-09-28T00:00:00Z' },
    snapshots: [{ id: snapshotId, revision: `git:${pocketFlowCommit}`, commit_sha: pocketFlowCommit, created_at: '2026-09-28T00:00:00Z', files,
      folder_cards: [folder('.', '1'), folder('utils', '2'), folder('docs', '3')] }],
  } }))
  await page.route(`**/api/snapshots/${snapshotId}/source**`, route => {
    const path = new URL(route.request().url()).searchParams.get('path') || 'main.py'
    return route.fulfill({ json: { path, sha256: 'a'.repeat(64), line_start: 1, line_end: 2, total_lines: 2, content: 'def main():\n    return 42' } })
  })
  await page.goto(`/#/projects/${projectId}`)
  await expect(page.locator('.overview-board')).toContainText('一张图看懂 PocketFlow')
  await expect(page.locator('.overview-board')).toContainText('当前快照 · 固定版本核对')
  await page.getByRole('button', { name: '查看 main.py 的作用' }).click()
  await expect(page.getByRole('heading', { name: 'main.py / 程序入口' })).toBeVisible()
  await expect(page.locator('.role-board')).toContainText('交给 flow.py 的运行上下文')
  await expect(page.locator('.repository-files').getByRole('button', { name: /main.py/ })).toHaveAttribute('aria-pressed', 'true')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
