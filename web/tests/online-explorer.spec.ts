import { test, expect } from '@playwright/test'

test('online directory, real parser, linked steps, source evidence and reload', async ({ page }, info) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await expect(page.getByLabel('在线浏览 · 不保存源码')).toBeChecked()
  await page.getByLabel('GitHub 仓库地址').fill(`https://github.com/example/demo-${info.project.name}-${info.testId.replace(/[^a-z0-9]/gi, '').slice(-16)}`)
  await page.getByRole('button', { name: '在线解析仓库' }).click()
  await expect(page).toHaveURL(/#\/online\/[\w-]+/)
  await expect(page.getByRole('heading', { name: '从文件到运行，读懂这个项目' })).toBeVisible()
  await expect(page.getByRole('button', { name: '继续分析相关文件' })).toBeEnabled()
  await page.getByRole('button', { name: '继续分析相关文件' }).click()
  await expect(page.getByRole('button', { name: '继续分析相关文件' })).toBeDisabled()
  const playback = page.getByRole('region', { name: '源码路径推演', exact: true })
  await playback.getByRole('combobox').selectOption('file:web/index.html')
  const tree = page.getByRole('complementary', { name: '项目文件结构' })
  await expect(tree.getByRole('button', { name: '文件 web/index.html', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await playback.getByRole('button', { name: '下一步 →' }).click()
  await expect(tree.getByRole('button', { name: '文件 web/src/main.tsx', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.rx-graph-node.is-selected')).toContainText('main.tsx')
  const inspector = page.getByRole('complementary', { name: '文件职责与源码' })
  await expect(inspector).toContainText('web/src/main.tsx')
  await playback.getByRole('button', { name: '▶ 播放路径' }).click()
  await expect(tree.getByRole('button', { name: '文件 web/src/App.tsx', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await playback.getByRole('button', { name: 'Ⅱ 暂停' }).click()
  await inspector.getByRole('button', { name: '查看源码', exact: true }).click()
  await expect(page.getByRole('region', { name: '源码片段', exact: true })).toContainText("import { HomePage }")
  await page.locator('.rx-relations summary').click()
  await page.locator('.rx-relations').getByRole('button').filter({ hasText: 'App.tsx → HomePage.tsx' }).click()
  await expect(page.getByRole('region', { name: '源码片段', exact: true })).toContainText('关系证据 · L1')
  await expect(inspector.getByRole('link', { name: '在 GitHub 核对固定版本' })).toHaveAttribute('href', /\/blob\/a{40}\/web\/src\/App.tsx#L1$/)
  await page.getByRole('searchbox', { name: '查找文件' }).fill('github_importer')
  await tree.getByRole('button', { name: '文件 server/app/github_importer.py', exact: true }).click()
  await expect(page.locator('.rx-graph-node.is-selected')).toContainText('github_importer.py')
  await page.getByRole('searchbox', { name: '查找文件' }).fill('')
  await page.screenshot({ path: info.outputPath('linked-explorer.png'), fullPage: true })
  for (const width of [320, 390, 768, 1100, 1600]) {
    await page.setViewportSize({ width, height: 1100 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  await page.reload()
  await expect(page.getByRole('heading', { name: '从文件到运行，读懂这个项目' })).toBeVisible()
  await expect(page.getByRole('button', { name: '继续分析相关文件' })).toBeDisabled()
  expect(errors).toEqual([])
})

test('unread files are explicit, failures retry, and session expiry recovers', async ({ page }, info) => {
  await page.goto('/')
  await page.getByLabel('GitHub 仓库地址').fill(`https://github.com/example/demo-${info.project.name}-${info.testId.replace(/[^a-z0-9]/gi, '').slice(-16)}`)
  await page.getByRole('button', { name: '在线解析仓库' }).click()
  await expect(page).toHaveURL(/#\/online\//)
  const id = new URL(page.url()).hash.split('/').at(-1)!
  await expect(page.getByRole('button', { name: '继续分析相关文件' })).toBeEnabled()
  const unreadPath = 'docs/design.md'
  await page.getByRole('searchbox', { name: '查找文件' }).fill('design.md')
  await page.getByRole('button', { name: `文件 ${unreadPath} · 未读取` }).click()
  await expect(page.getByText('文件目录已获取，正文尚未读取。')).toBeVisible()
  await page.route(`**/api/online/${id}/read`, route => route.fulfill({ status: 429, json: { detail: { message: 'GitHub 暂时限制读取，请稍后重试。' } } }))
  await page.getByRole('button', { name: '读取并分析此文件' }).click()
  await expect(page.getByRole('alert')).toContainText('GitHub 暂时限制读取')
  await page.unroute(`**/api/online/${id}/read`)
  await page.getByRole('button', { name: '读取并分析此文件' }).click()
  await expect(page.getByRole('button', { name: '查看源码', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '查看源码', exact: true }).click()
  await expect(page.getByRole('region', { name: '源码片段', exact: true })).toContainText('Static fixture')
  await page.goto('/#/online/00000000-0000-4000-8000-000000000000')
  await expect(page.getByRole('alert')).toContainText('会话已过期')
  await expect(page.getByRole('link', { name: '返回首页，重新打开仓库' })).toBeVisible()
})

test('snapshot uploads use the same linked explorer and keep legacy tools accessible', async ({ page }) => {
  const response = await page.request.post('/api/projects/import', { data: {
    source: 'upload', name: 'Snapshot regression', files: [
      { path: 'main.py', content_base64: Buffer.from("from helpers import clean\nif __name__ == '__main__':\n    clean('hello')\n").toString('base64') },
      { path: 'helpers.py', content_base64: Buffer.from("def clean(value):\n    return value.strip()\n").toString('base64') },
    ],
  } })
  expect(response.status()).toBe(201)
  const detail = (await response.json()).detail
  await page.goto(`/#/projects/${detail.project.id}`)
  await expect(page.getByRole('heading', { name: '从文件到运行，读懂这个项目' })).toBeVisible()
  const tree = page.getByRole('complementary', { name: '项目文件结构' })
  await tree.getByRole('button', { name: '文件 helpers.py', exact: true }).click()
  const contract = page.getByRole('region', { name: '函数输入与输出', exact: true })
  await expect(contract).toContainText('clean(value)')
  await expect(contract).toContainText('return value.strip()')
  await contract.getByRole('button', { name: /查看函数源码/ }).click()
  await expect(page.getByRole('region', { name: '源码片段', exact: true })).toContainText('def clean')
  await page.locator('.snapshot-legacy > summary').click()
  await page.getByRole('button', { name: /运行此项目的分析任务/ }).click()
  await expect(page.getByRole('button', { name: '启动替身任务' })).toBeEnabled()
})
