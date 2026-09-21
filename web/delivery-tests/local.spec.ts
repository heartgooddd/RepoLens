import {test, expect} from '@playwright/test'

test('本地交付：项目地图、源码依据、页面替身运行、刷新历史', async ({page}, info)=>{
  test.skip(!!process.env.REPOLENS_RESTORED_PROJECT, '恢复模式仅检查历史，不创建新任务')
  await page.goto('/')
  await page.getByRole('button',{name:'扫描 PocketFlow 样本'}).click()
  await expect(page.getByRole('heading',{name:'PocketFlow 项目地图'})).toBeVisible()
  await page.getByRole('button',{name:/^flow.py/}).click()
  await expect(page.getByRole('region',{name:'真实源码片段'})).toContainText('fetch_repo >> identify_abstractions')
  await page.getByLabel('运行模式',{exact:true}).selectOption('stub')
  await page.getByRole('button',{name:'启动替身任务'}).click()
  await expect(page.getByRole('button',{name:'查看替身结果'})).toBeVisible()
  await page.getByRole('button',{name:'查看替身结果'}).click()
  await expect(page.getByRole('article',{name:'生成 Markdown 预览'})).toContainText('替身')
  await page.reload()
  await expect(page.getByRole('button',{name:'查看替身结果'})).toBeVisible()
  await page.screenshot({path:info.outputPath('local-delivery.png'),fullPage:true})
})

test('恢复的数据可打开原项目、源码与M3真实历史产物，不再次调用模型', async ({page},info)=>{
  const project=process.env.REPOLENS_RESTORED_PROJECT
  const run=process.env.REPOLENS_RESTORED_RUN
  test.skip(!project||!run,'仅在已恢复数据的启动器上运行')
  let posts=0
  page.on('request', request=>{if(request.method()==='POST'&&request.url().endsWith('/api/runs'))posts++})
  await page.goto(`/#/projects/${project}`)
  await expect(page.getByRole('heading',{name:'PocketFlow 项目地图'})).toBeVisible()
  await page.getByRole('button',{name:/^flow.py/}).click()
  await expect(page.getByRole('region',{name:'真实源码片段'})).toContainText('已校验 SHA-256')
  await page.getByLabel('运行历史').selectOption(run!)
  await page.getByRole('button',{name:'查看真实结果'}).click()
  await expect(page.getByRole('article',{name:'生成 Markdown 预览'})).toContainText('Tutorial: project')
  await expect(page.getByText(/deepseek\/deepseek-v4-flash/).first()).toBeVisible()
  await page.screenshot({path:info.outputPath('restored-m3-result.png'),fullPage:true})
  expect(posts).toBe(0)
})
