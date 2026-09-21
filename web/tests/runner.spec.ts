import { test, expect } from '@playwright/test'
import type { Page, TestInfo } from '@playwright/test'

async function openProject(page: Page) {
  const response = await page.request.post('/api/projects/import', { data: {
    source: 'upload', name: 'M3 任务验证', files: [
      { path: 'main.py', content_base64: Buffer.from('def main():\n    return 42\n').toString('base64') },
      { path: 'utils/helper.py', content_base64: Buffer.from('def helper():\n    pass\n').toString('base64') },
    ],
  } })
  expect(response.status()).toBe(201)
  const detail = (await response.json()).detail
  await page.goto(`/#/projects/${detail.project.id}`)
  await expect(page.getByRole('button', { name: '启动替身任务' })).toBeEnabled()
}
async function capture(page: Page, info: TestInfo, name: string) {
  await page.evaluate(() => { window.scrollTo(0, 0); document.querySelector('.run-panel')?.scrollTo(0, 0) })
  await page.mouse.move(0, 0)
  await page.screenshot({ path: info.outputPath(name), fullPage: true })
}

test('任务表单、成功产物、安全 Markdown、下载和刷新重开', async ({ page }, info) => {
  const errors: string[] = [], external: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('request', request => { if (!new URL(request.url()).hostname.match(/^(127\.0\.0\.1|localhost)$/)) external.push(request.url()) })
  await openProject(page)
  await expect(page.getByText('替身验证 · 无模型')).toBeVisible()
  await capture(page, info, 'task-ready.png')
  await page.getByLabel('分析范围', { exact: true }).selectOption('utils')
  await page.getByLabel('任务语言').selectOption('en')
  await page.getByLabel('核心主题数').selectOption('5')
  await page.getByRole('button', { name: '启动替身任务' }).click()
  await expect(page.getByRole('status')).toContainText('替身处理中')
  await expect(page.getByLabel('任务语言')).toBeDisabled()
  await capture(page, info, 'task-running.png')
  await expect(page.getByRole('status')).toContainText('替身完成')
  await expect(page.getByLabel('后台任务日志')).toContainText('REPOLENS_STAGE:CombineTutorial')
  await page.getByRole('button', { name: '查看替身结果' }).click()
  const preview = page.getByRole('article', { name: '生成 Markdown 预览' })
  await expect(preview).toContainText('Stub verification result')
  await expect(preview).toContainText('en / 5')
  await expect(preview).toContainText('读取 1 个')
  await expect(preview.locator('script, iframe, img, a[href^="javascript:"]')).toHaveCount(0)
  expect(await page.evaluate(() => '__unsafeMarkdown' in window)).toBe(false)
  await expect(page.getByText(/待核实：固定替身职责说明/)).toBeVisible()
  await capture(page, info, 'task-result.png')
  await preview.getByRole('button', { name: '第一章' }).click()
  await expect(preview).toContainText('固定章节')
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('link', { name: '下载当前 Markdown' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('repolens-artifact.md')
  await page.reload()
  await expect(page.getByRole('status')).toContainText('替身完成')
  // New form defaults must not alter historical parameters or results.
  await page.getByLabel('任务语言').selectOption('zh')
  await page.getByRole('button', { name: '查看替身结果' }).click()
  await expect(preview).toContainText('en / 5')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(errors).toEqual([])
  expect(external).toEqual([])
})

test('失败、取消和历史任务保持终态', async ({ page }, info) => {
  await openProject(page)
  await page.getByLabel('替身验证情境').selectOption('failure')
  await page.getByRole('button', { name: '启动替身任务' }).click()
  await expect(page.getByRole('status')).toContainText('任务失败')
  await expect(page.getByLabel('后台任务日志')).toContainText('模拟生成失败')
  await expect(page.getByRole('button', { name: '查看替身结果' })).toHaveCount(0)
  const failedId = await page.getByLabel('运行历史').inputValue()
  await capture(page, info, 'task-failed.png')
  await page.getByLabel('替身验证情境').selectOption('slow')
  await page.getByRole('button', { name: '启动替身任务' }).click()
  await expect(page.getByRole('status')).toContainText('替身处理中')
  await page.getByRole('button', { name: '取消任务' }).click()
  await expect(page.getByRole('status')).toContainText('已取消')
  await expect(page.getByRole('button', { name: '查看替身结果' })).toHaveCount(0)
  await capture(page, info, 'task-cancelled.png')
  await page.reload()
  await expect(page.getByRole('status')).toContainText('已取消')
  await page.getByLabel('运行历史').selectOption(failedId)
  await expect(page.getByRole('status')).toContainText('任务失败')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('真实模式缺少密钥时禁用启动并支持重新读取配置', async ({ page }, info) => {
  // Only configuration is simulated; no model request is made by this browser test.
  let reads = 0, creates = 0
  page.on('request', request => { if (request.method() === 'POST' && request.url().endsWith('/api/runs')) creates++ })
  await page.route('**/api/runner', route => {
    reads++
    return route.fulfill({ json: { mode: 'selectable', real_enabled: true, real_ready: false,
      model: { provider: 'OPENROUTER', model: 'offline/config-fixture', api_key_configured: false, configuration_complete: false, missing: ['api_key'] } } })
  })
  const response = await page.request.post('/api/projects/import', { data: { source: 'builtin' } })
  expect(response.status()).toBe(201)
  const detail = (await response.json()).detail
  await page.goto(`/#/projects/${detail.project.id}`)
  await page.getByLabel('运行模式', { exact: true }).selectOption('pocketflow')
  await expect(page.getByText('真实运行 · 调用模型')).toBeVisible()
  await expect(page.getByLabel('分析范围', { exact: true })).toHaveValue('utils')
  await expect(page.getByLabel('分析范围', { exact: true })).toBeDisabled()
  await expect(page.getByLabel('任务语言')).toBeDisabled()
  await expect(page.getByLabel('核心主题数').locator('option')).toHaveCount(2)
  await expect(page.getByRole('button', { name: '启动真实任务' })).toBeDisabled()
  await expect(page.getByText('模型配置不齐全', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: '重新读取', exact: true }).click()
  await expect.poll(() => reads).toBeGreaterThan(1)
  expect(creates).toBe(0)
  await capture(page, info, 'real-missing-key-fixture.png')
})
