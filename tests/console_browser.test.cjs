/* Optional real-browser UI regression. No runtime/build dependency is added.
 * Run with node --test tests/console_browser.test.cjs and provide an installed
 * Playwright via KNOA_PLAYWRIGHT_MODULE, plus KNOA_BROWSER_EXECUTABLE if needed.
 * This server serves only repository static assets and synthetic API fixtures.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs/promises');
const path = require('node:path');
const {createHash} = require('node:crypto');

let playwright;
try {
  playwright = require(process.env.KNOA_PLAYWRIGHT_MODULE || 'playwright');
} catch (error) {
  if (process.env.KNOA_PLAYWRIGHT_MODULE) throw error;
}

const root = path.resolve(__dirname, '..');
const staticRoot = path.join(root, 'src/knoa_parse/apps/console/static');
const screenshotRoot = path.join(root, '.local/manual-testing/console-review');
const artifactId = `artifact-${'0123456789'.repeat(9)}`;
const injection = '<img src=x onerror="window.__consoleInjected=true">';
const secretError = 'PRIVATE_BODY_SENTINEL {"api_key": "synthetic secret with spaces"}';

function fixtures() {
  const jobs = ['succeeded', 'partial', 'failed', 'cancelled', 'queued', 'running'].map((state, i) => ({
    id: `job-${state}`, source_id: `source-${state}`, state, target: 'native_extract',
    result_artifact_id: ['succeeded', 'partial'].includes(state) ? `result-${state}` : null,
    created_at: 1794268800 + i,
    source: {id: `source-${state}`, filename: `${state}-${'资料'.repeat(12)}.txt`, size_bytes: 512, media_type: 'text/plain', sha256:'a'.repeat(64)},
    error: state === 'failed' ? {code:'synthetic_failure', message:'合成失败原因'} : null,
  }));
  const results = Object.fromEntries(jobs.filter(j => j.result_artifact_id).map(j => [j.id, {
    schema_version:'0.2.0-draft.1', engine:'synthetic-browser-fixture',
    status:j.state === 'partial' ? 'partial' : 'completed',
    blocks:Array.from({length:25}, (_, i) => ({id:`block-${i}`,kind:'text',acquisition:'native',text:`第 ${i + 1} 条合成证据。${'内容和来源均可核对。'.repeat(12)}`,data:{label:'paragraph'},locators:[{artifact_id:j.source_id,kind:'text_span',precision:'source_exact',start:i,end:i+1}]})),
    coverage:[{unit_id:'document',status:j.state === 'partial' ? 'failed' : 'completed', issue_codes:j.state === 'partial' ? ['synthetic_gap'] : []}],
    issues:j.state === 'partial' ? [{code:'synthetic_gap',severity:'error',unit_id:'document',message:'合成覆盖缺口'}] : [],
    artifacts:[{id:j.source_id,role:'source',media_type:'text/plain',size_bytes:512},{id:artifactId,role:'derived',media_type:'text/plain',size_bytes:18}],
  }]));
  return {
    jobs, allJobs:Object.fromEntries(jobs.map(j => [j.id,j])), results,
    listCalls:0, resultCalls:{}, jobCalls:{}, listError:false, resultError:false,
    resultGate:null, resultRelease:null, listGate:null, listRelease:null, onList:null,
    imageGate:null, imageRelease:null, onImage:null, sourceError:false,
    settings:{provider:'custom-platform',protocol:'openai',base_url:'https://example.test/v1',model:'synthetic-model',timeout_seconds:60,enable_thinking:false,key_configured:true,editable:true},
    caps:{schema_version:'0.2.0-draft.1',local_model_inference:false,formats:[{extension:'.txt',target:'native_extract'},{extension:'.json',target:'native_extract'}],external_capabilities:[]},
  };
}

async function fixtureServer(data) {
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const json = (body, status = 200) => {res.writeHead(status, {'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(body));};
    if (url.pathname === '/api/v1/capabilities') return json(data.caps);
    if (url.pathname === '/api/v1/jobs') {
      data.listCalls += 1;
      const items = structuredClone(data.jobs), gate = data.listGate;
      data.onList?.(); data.onList=null;
      if (gate) await gate;
      if (res.destroyed) return;
      return data.listError ? json({error:{code:'synthetic_error',message:secretError}},500) : json({items,has_more:false,limit:100});
    }
    const result = url.pathname.match(/^\/api\/v1\/jobs\/([^/]+)\/result$/);
    if (result) {
      const id = decodeURIComponent(result[1]);
      data.resultCalls[id] = (data.resultCalls[id] || 0) + 1;
      const body = structuredClone(data.results[id]), gate = data.resultGate;
      if (gate) await gate;
      if (res.destroyed) return;
      return data.resultError ? json({error:{code:'synthetic_error',message:secretError}},500) : json(body);
    }
    const job = url.pathname.match(/^\/api\/v1\/jobs\/([^/]+)$/);
    if (job) {
      const id = decodeURIComponent(job[1]);
      data.jobCalls[id] = (data.jobCalls[id] || 0) + 1;
      return data.allJobs[id] ? json(data.allJobs[id]) : json({error:{code:'not_found',message:'合成任务不存在'}},404);
    }
    const source = url.pathname.match(/^\/api\/v1\/sources\/([^/]+)$/);
    if (source) {
      const item = Object.values(data.allJobs).find(j => j.source_id === decodeURIComponent(source[1]));
      return data.sourceError || !item?.source ? json({error:{code:'not_found',message:'来源元数据不可用'}},404) : json(item.source);
    }
    if (url.pathname === '/api/v1/settings/model') return json(data.settings);
    if (url.pathname === '/api/v1/settings/model/test') return json({error:{code:'synthetic_error',message:secretError}},500);
    if (url.pathname === '/api/v1/artifacts/image-old') {
      data.onImage?.();data.onImage=null;
      if (data.imageGate) await data.imageGate;
      if (res.destroyed) return;
      res.writeHead(200,{'Content-Type':'image/png'});
      return res.end(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5RkAAAAASUVORK5CYII=','base64'));
    }
    if (url.pathname.startsWith('/api/v1/artifacts/')) {
      res.writeHead(200,{'Content-Type':'text/plain; charset=utf-8'}); return res.end('synthetic artifact');
    }
    const files = {'/':'index.html','/index.html':'index.html','/app.js':'app.js','/model.mjs':'model.mjs','/style.css':'style.css'};
    if (!Object.hasOwn(files,url.pathname)) {res.writeHead(404);return res.end();}
    try {
      const bytes = await fs.readFile(path.join(staticRoot,files[url.pathname]));
      const mime = url.pathname.endsWith('.css') ? 'text/css' : /\.(?:m?js)$/.test(url.pathname) ? 'text/javascript' : 'text/html';
      res.writeHead(200,{'Content-Type':`${mime}; charset=utf-8`,'Cache-Control':'no-store'}); res.end(bytes);
    } catch(error) {res.writeHead(500);res.end('Fixture asset unavailable');}
  });
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  return {url:`http://127.0.0.1:${server.address().port}`,close:async () => {
    data.resultRelease?.();data.listRelease?.();data.imageRelease?.();
    server.closeAllConnections(); await new Promise(resolve => server.close(resolve));
  }};
}

async function browserCase(browser, work, setup = () => {}) {
  const data = fixtures(); setup(data);
  const server = await fixtureServer(data);
  const context = await browser.newContext({viewport:{width:1440,height:900},permissions:['clipboard-read','clipboard-write']});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror',error => errors.push(error.message));
  // No test traffic can reach a provider or any other external host.
  await context.route('**/*',route => route.request().url().startsWith(server.url) ? route.continue() : route.abort());
  try {
    await page.goto(server.url);
    await page.waitForFunction(() => document.querySelectorAll('.task-row').length === 6);
    await work({page,data,server,context});
    assert.deepEqual(errors, [], 'the console must not throw browser errors');
  } finally {await context.close();await server.close();}
}

async function waitForContent(page) {
  await page.locator('.block-text').first().waitFor();
}

async function foregroundRefresh(page) {
  const response = page.waitForResponse(r => r.url().includes('/api/v1/jobs?limit=100'));
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await response;
  await page.waitForFunction(() => !document.querySelector('#refresh').disabled);
}

test('optional console browser regression', {skip:!playwright,timeout:180000}, async t => {
  const browser = await playwright.chromium.launch({headless:true,...(process.env.KNOA_BROWSER_EXECUTABLE ? {executablePath:process.env.KNOA_BROWSER_EXECUTABLE} : {})});
  try {
    for (const [width,height] of [[1440,900],[1280,800],[1024,768]]) {
      await t.test(`${width}px desktop keeps all three views inside the viewport`, async () => browserCase(browser,async ({page}) => {
        await page.setViewportSize({width,height}); await waitForContent(page);
        for (const view of ['workspace','capabilities','models']) {
          await page.locator(`[data-view="${view}"]`).click();
          if (view === 'workspace') await page.locator('.diagnostic-toggle').click();
          await page.waitForFunction(() => document.fonts.status === 'loaded');
          const geometry = await page.evaluate(() => ({viewport:innerWidth,width:document.documentElement.scrollWidth}));
          assert.ok(geometry.width <= geometry.viewport, `${view} overflows: ${JSON.stringify(geometry)}`);
          if (view === 'workspace') {
            const list = await page.locator('.task-panel').boundingBox();
            const inspector = await page.locator('.inspector').boundingBox();
            assert.ok(list.x + list.width <= inspector.x + 1,'desktop panes must not overlap');
          }
          if (process.env.KNOA_CONSOLE_SCREENSHOTS === '1') {
            await fs.mkdir(screenshotRoot,{recursive:true});
            await page.evaluate(() => {document.activeElement?.blur();window.scrollTo(0,0);});
            await page.screenshot({path:path.join(screenshotRoot,`${width}-${view}.png`),fullPage:false});
            if (width === 1024 && view === 'workspace') {
              await page.locator('#diagnostic-drawer').scrollIntoViewIfNeeded();
              await page.screenshot({path:path.join(screenshotRoot,'1024-diagnostics.png'),fullPage:false});
            }
          }
        }
      }));
    }

    await t.test('six statuses keep partial, failed and cancelled distinct from success', async () => browserCase(browser,async ({page}) => {
      const labels = {queued:'等待执行',running:'解析中',succeeded:'已完成',partial:'部分完成',failed:'解析失败',cancelled:'已取消'};
      for (const [state,label] of Object.entries(labels)) {
        await page.locator(`[data-job="job-${state}"]`).click();
        assert.equal(await page.locator('.detail-topline .badge').innerText(),label);
        const middle = page.locator('.track-step').nth(1);
        if (['partial','failed','cancelled'].includes(state)) {
          assert.equal(await middle.evaluate(node => node.classList.contains('done')),false,`${state} must not claim success`);
          assert.doesNotMatch(await middle.innerText(),/✓/);
        }
      }
    }));

    await t.test('keyboard tabs address their active panel and preserve focus', async () => browserCase(browser,async ({page}) => {
      await waitForContent(page);
      await page.locator('[data-tab="content"]').focus();
      for (const [key,selected] of [['ArrowRight','issues'],['End','raw'],['Home','content']]) {
        await page.keyboard.press(key);
        const tab = page.locator(`[data-tab="${selected}"]`);
        assert.equal(await tab.getAttribute('aria-selected'),'true');
        assert.equal(await tab.evaluate(node => node === document.activeElement),true);
        const panel = page.locator(`#${await tab.getAttribute('aria-controls')}`);
        assert.equal(await panel.getAttribute('aria-labelledby'),await tab.getAttribute('id'));
        assert.equal(await panel.isVisible(),true);
      }
    }));

    await t.test('foreground polling preserves task focus while active jobs have no result', async () => browserCase(browser,async ({page}) => {
      const row = page.locator('[data-job="job-queued"]');
      await row.click(); await row.focus();
      await foregroundRefresh(page);
      assert.equal(await row.evaluate(node => node === document.activeElement),true);
      assert.equal(await row.getAttribute('aria-pressed'),'true');
    }));

    await t.test('diagnostics preserve focus and event scroll through polling; Escape returns focus', async () => browserCase(browser,async ({page}) => {
      await waitForContent(page);await page.locator('.diagnostic-toggle').click();
      for (let i=0;i<8;i+=1) await foregroundRefresh(page);
      const events = page.locator('.diagnostic-events ol');
      await events.evaluate(node => {node.scrollTop=60;});
      const oldTop = await events.evaluate(node => node.scrollTop);
      assert.ok(oldTop > 0,'fixture must create a scrollable event log');
      const close = page.locator('[data-action="close-diagnostics"]');
      await close.focus();await foregroundRefresh(page);
      assert.equal(await close.evaluate(node => node === document.activeElement),true);
      assert.equal(await events.evaluate(node => node.scrollTop),oldTop);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#diagnostic-drawer').isVisible(),false);
      assert.equal(await page.locator('.diagnostic-toggle').evaluate(node => node === document.activeElement),true);
    }));

    await t.test('reconnection retains the page event history and reload clears it', async () => browserCase(browser,async ({page}) => {
      await waitForContent(page);await page.locator('.diagnostic-toggle').click();
      for (let i=0;i<3;i+=1) await foregroundRefresh(page);
      const before = await page.locator('.diagnostic-events li').count();
      await page.locator('#connection-nav').click();await waitForContent(page);
      if (!(await page.locator('#diagnostic-drawer').isVisible())) await page.locator('.diagnostic-toggle').click();
      const after = await page.locator('.diagnostic-events li').count();
      assert.ok(after > before,`reconnect discarded page history (${before} -> ${after})`);
      await page.reload();await waitForContent(page);await page.locator('.diagnostic-toggle').click();
      assert.ok(await page.locator('.diagnostic-events li').count() < after,'full page reload must start a new in-memory log');
    }));

    await t.test('opening a task survives missing source metadata', async () => browserCase(browser,async ({page,data}) => {
      data.sourceError=true;
      data.allJobs['outside-job']={id:'outside-job',source_id:'missing-source',state:'running',target:'native_extract',result_artifact_id:null};
      await page.locator('#import-job').click();await page.locator('#job-id-input').fill('outside-job');
      await page.locator('#job-form button[type="submit"]').click();
      await page.waitForFunction(() => document.querySelector('#job-dialog').open === false);
      assert.equal(await page.locator('#inspector-title').innerText(),'missing-source');
      assert.match(await page.locator('#inspector-content').innerText(),/来源.*(?:不可用|失败|缺失|无法)/);
    }));

    await t.test('malicious filenames and evidence remain literal text', async () => browserCase(browser,async ({page}) => {
      await waitForContent(page);
      assert.equal(await page.locator('.block-text').first().innerText(),injection);
      assert.equal(await page.locator('[onerror]').count(),0);
      assert.equal(await page.evaluate(() => window.__consoleInjected),undefined);
      assert.match(await page.locator('.task-items').innerText(),/<img src=x/);
      await page.locator('[data-tab="raw"]').click();
      assert.equal(await page.locator('.raw-json script, .raw-json img').count(),0);
      assert.equal(await page.evaluate(() => window.__consoleInjected),undefined);
    },data => {data.jobs[0].source.filename=`${injection}.txt`;data.results['job-succeeded'].blocks[0].text=injection;}));

    await t.test('diagnostics never retain arbitrary error bodies or credentials', async () => browserCase(browser,async ({page,data}) => {
      await page.locator('.waiting-state').filter({hasText:'暂时无法读取结果'}).waitFor();
      await page.locator('.diagnostic-toggle').click();
      assert.doesNotMatch(await page.locator('.diagnostic-events').innerText(),/PRIVATE_BODY_SENTINEL|synthetic secret/);
      data.listError=true;await foregroundRefresh(page);
      assert.doesNotMatch(await page.locator('.diagnostic-events').innerText(),/PRIVATE_BODY_SENTINEL|synthetic secret/);
      await page.locator('[data-view="models"]').click();await page.locator('#model-api-key').fill('synthetic-input-key');
      assert.equal(await page.evaluate(() => localStorage.length),0);
      assert.doesNotMatch(await page.locator('#diagnostic-content').innerText(),/synthetic-input-key/);
    },data => {data.resultError=true;}));

    await t.test('long artifact IDs can be inspected, copied and downloaded intact', async () => browserCase(browser,async ({page}) => {
      await waitForContent(page);await page.locator('.diagnostic-toggle').click();
      assert.ok((await page.locator('.diagnostic-chain').innerText()).includes(artifactId),'artifact ID must be fully inspectable');
      const copy = page.locator(`.diagnostic-chain [data-copy-id="${artifactId}"]`);
      await copy.click();
      assert.equal(await page.evaluate(() => navigator.clipboard.readText()),artifactId);
      const downloading = page.waitForEvent('download');
      await page.locator(`.diagnostic-chain [data-download-artifact="${artifactId}"]`).click();
      const download = await downloading;
      const content = await fs.readFile(await download.path());
      assert.equal(createHash('sha256').update(content).digest('hex'),createHash('sha256').update('synthetic artifact').digest('hex'));
    }));

    await t.test('environment-controlled model settings are read-only in the form', async () => browserCase(browser,async ({page}) => {
      await page.locator('[data-view="models"]').click();
      await page.waitForFunction(() => document.querySelector('#model-key-state').textContent.includes('已配置'));
      const editable = await page.locator('#model-settings-form input, #model-settings-form select').evaluateAll(nodes => nodes.filter(n => !n.disabled && !n.readOnly).map(n => n.id));
      assert.deepEqual(editable,[],'read-only settings must not invite edits that cannot be saved');
      assert.equal(await page.locator('#model-save').isDisabled(),true);
    },data => {data.settings.editable=false;}));

    await t.test('revisiting model settings keeps an unsaved draft', async () => browserCase(browser,async ({page}) => {
      await page.locator('[data-view="models"]').click();
      await page.waitForFunction(() => document.querySelector('#model-name').value === 'synthetic-model');
      await page.locator('#model-name').fill('unsaved-local-draft');
      await page.locator('[data-view="capabilities"]').click();await page.locator('[data-view="models"]').click();
      assert.equal(await page.locator('#model-name').inputValue(),'unsaved-local-draft');
    }));

    await t.test('repeated selection coalesces one pending result request', async () => browserCase(browser,async ({page,data}) => {
      await page.locator('.waiting-state').filter({hasText:'正在读取证据'}).waitFor();
      await page.locator('[data-job="job-succeeded"]').click();
      await page.locator('[data-job="job-succeeded"]').click();
      assert.equal(data.resultCalls['job-succeeded'],1,'an in-flight result must not be sent again');
      data.resultRelease();await waitForContent(page);
      assert.equal(data.resultCalls['job-succeeded'],1);
    },data => {data.resultGate=new Promise(resolve => {data.resultRelease=resolve;});}));

    await t.test('a delayed result from before reconnect cannot overwrite the new session', async () => browserCase(browser,async ({page,data}) => {
      await page.locator('.waiting-state').filter({hasText:'正在读取证据'}).waitFor();
      data.results['job-succeeded']=structuredClone(data.results['job-succeeded']);
      data.results['job-succeeded'].blocks[0].text='新会话的独立证据';
      data.resultGate=null;
      await page.locator('#connection-nav').click();await waitForContent(page);
      assert.equal(await page.locator('.block-text').first().innerText(),'新会话的独立证据');
      const staleResponse=page.waitForResponse(r => r.url().endsWith('/api/v1/jobs/job-succeeded/result'));
      data.resultRelease();await staleResponse;
      await page.locator('[data-job="job-partial"]').click();await waitForContent(page);
      await page.locator('[data-job="job-succeeded"]').click();await waitForContent(page);
      assert.equal(await page.locator('.block-text').first().innerText(),'新会话的独立证据','late old data must not poison the result cache');
    },data => {data.resultGate=new Promise(resolve => {data.resultRelease=resolve;});}));

    await t.test('a delayed list refresh cannot restore the old session after reconnect', async () => browserCase(browser,async ({page,data}) => {
      await waitForContent(page);
      const entered=new Promise(resolve => {data.onList=resolve;});
      data.listGate=new Promise(resolve => {data.listRelease=resolve;});
      await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
      await entered;
      data.jobs=structuredClone(data.jobs);
      data.jobs[0].source.filename='new-session-source.txt';
      data.listGate=null;
      await page.locator('#connection-nav').click();await waitForContent(page);
      assert.equal(await page.locator('#inspector-title').innerText(),'new-session-source.txt');
      const staleResponse=page.waitForResponse(r => r.url().includes('/api/v1/jobs?limit=100'));
      data.listRelease();await staleResponse;
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await page.locator('#inspector-title').innerText(),'new-session-source.txt');
      assert.equal(await page.locator('.filename').first().innerText(),'new-session-source.txt');
    }));

    await t.test('a delayed image from another selection is not cached in the current page', async () => browserCase(browser,async ({page,data}) => {
      await waitForContent(page);
      const entered=new Promise(resolve => {data.onImage=resolve;});
      await page.locator('[data-load-image="image-old"]').click();await entered;
      await page.locator('[data-job="job-partial"]').click();await waitForContent(page);
      const staleResponse=page.waitForResponse(r => r.url().endsWith('/api/v1/artifacts/image-old'));
      data.imageRelease();await staleResponse;
      await page.locator('[data-job="job-succeeded"]').click();await waitForContent(page);
      assert.equal(await page.locator('.image-preview').count(),0,'a late image from an old selection must be discarded');
      assert.equal(await page.locator('[data-load-image="image-old"]').isVisible(),true);
    },data => {
      data.imageGate=new Promise(resolve => {data.imageRelease=resolve;});
      data.results['job-succeeded'].blocks.unshift({id:'image-block',kind:'image',acquisition:'native',data:{image_artifact_id:'image-old'},locators:[]});
    }));

    await t.test('a selected task leaving the recent window remains observable', async () => browserCase(browser,async ({page,data}) => {
      await page.locator('[data-job="job-running"]').click();
      const title = await page.locator('#inspector-title').innerText();
      data.jobs=data.jobs.filter(j => j.id !== 'job-running');
      await foregroundRefresh(page);
      assert.equal(await page.locator('#inspector-title').innerText(),title);
      assert.ok(data.jobCalls['job-running'] >= 1,'selected task must use the direct status endpoint');
      assert.equal(await page.locator('.detail-topline .badge').innerText(),'解析中');
    }));
  } finally {await browser.close();}
});
