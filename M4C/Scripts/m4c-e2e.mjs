// M4-C 端到端验收：真实 Chrome（headless 默认，M4C_HEADED=1 时用真实窗口 + 系统 GPU）驱动 M4-C WebGL 构建。
// 用法：node m4c-e2e.mjs <http URL> <新建证据目录> <phase: online|offline|resume>
// 以 M4A-QA/Scripts/m4a-e2e.mjs（M4-A 已验收）为基础扩展：自由输入、Mock/超时、离线回退、会话恢复。
// 复跑离线/恢复阶段时用 M4C_PROFILE=<上一轮的 profile> 复用浏览器配置，使 PlayerPrefs 存档延续。
import { spawn } from 'node:child_process';
import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { setTimeout as delay } from 'node:timers/promises';

const [url, output, phase = 'online'] = process.argv.slice(2);
if (!url || new URL(url).hostname !== '127.0.0.1' || !output) {
  throw new Error('Provide a loopback HTTP URL and a new evidence directory.');
}
const out = resolve(output);
await mkdir(out, { recursive: true });
// 复用 profile 时先建目录：Playwright 式的“已存在才复用”太容易踩坑，
// 之前的一次运行就因为目录不存在而退化成全新 profile，导致存档没接上。
const reuse = process.env.M4C_PROFILE;
if (reuse) await mkdir(reuse, { recursive: true });
const profile = reuse || await mkdtemp(join(tmpdir(), 'echo-m4c-chrome-'));
// M4C_HEADED=1 时改用真实窗口 + 默认 GPU（D3D11/ANGLE），用于“非 headless 的真实 GPU 渲染”验收。
const headed = process.env.M4C_HEADED === '1';
const gpuArgs = headed ? ['--use-angle=d3d11'] : ['--enable-unsafe-swiftshader', '--use-angle=swiftshader'];
const chrome = spawn(process.env.M4C_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe', [
  ...(headed ? [] : ['--headless=new']), '--remote-debugging-pipe', '--no-first-run', '--disable-default-apps',
  '--window-size=1200,850', ...gpuArgs,
  '--mute-audio', '--user-data-dir=' + profile, 'about:blank',
], { stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe'], windowsHide: true });
let stderr = '';
chrome.stderr.on('data', d => { stderr = (stderr + d).slice(-12000); });
let seq = 0, sessionId;
const pending = new Map(), consoles = [], resources = [], requests = [], exceptions = [], dialogs = [];
function rpc(method, params = {}, session = sessionId) {
  return new Promise((done, fail) => {
    const id = ++seq;
    const timer = setTimeout(() => { pending.delete(id); fail(Error('Timeout: ' + method)); }, 30000);
    pending.set(id, m => {
      clearTimeout(timer);
      if (m.error) fail(Error(method + ': ' + m.error.message));
      else done(m.result);
    });
    chrome.stdio[3].write(JSON.stringify({ id, method, params, sessionId: session }) + '\0');
  });
}
let buffer = '';
chrome.stdio[4].setEncoding('utf8').on('data', data => {
  buffer += data;
  for (let cut; (cut = buffer.indexOf('\0')) >= 0;) {
    const msg = JSON.parse(buffer.slice(0, cut));
    buffer = buffer.slice(cut + 1);
    if (pending.has(msg.id)) {
      pending.get(msg.id)(msg); pending.delete(msg.id);
    } else if (msg.method === 'Runtime.consoleAPICalled') {
      consoles.push({ type: msg.params.type, message: msg.params.args.map(a => a.value ?? a.description).join(' ') });
    } else if (msg.method === 'Runtime.exceptionThrown') {
      exceptions.push(msg.params.exceptionDetails);
    } else if (msg.method === 'Page.javascriptDialogOpening') {
      dialogs.push(msg.params.message);
      rpc('Page.handleJavaScriptDialog', { accept: true }).catch(() => {});
    } else if (msg.method === 'Network.requestWillBeSent') {
      const { request, requestId } = msg.params;
      if (request.url.includes('/api/v1/')) requests.push({ id: requestId, method: request.method, url: request.url, body: request.postData ?? null });
    } else if (msg.method === 'Network.responseReceived') {
      const { url: u, status, mimeType, headers } = msg.params.response;
      resources.push({ url: u, status, mimeType, encoding: headers['Content-Encoding'] });
    }
  }
});
const evaluate = async expression => (await rpc('Runtime.evaluate', { expression, returnByValue: true })).result.value;
async function until(read, seconds) {
  const start = Date.now();
  do { const value = await read(); if (value) return value; await delay(200); } while (Date.now() - start < seconds * 1000);
  throw Error('Timeout waiting for ' + read);
}
const screenshot = async name => {
  const { data } = await rpc('Page.captureScreenshot', { format: 'png' });
  await writeFile(join(out, name + '.png'), Buffer.from(data, 'base64'));
};
const pages = () => consoles.filter(c => /^M4A page /.test(c.message)).map(c => c.message);
const lastPage = () => pages().at(-1) ?? '';
const logs = re => consoles.filter(c => re.test(c.message)).map(c => c.message);
const steps = [], soft = [];
function step(name, detail = '') { steps.push({ name, detail, page: lastPage(), at: new Date().toISOString() }); }
async function waitPage(substr, seconds = 15) {
  await until(() => pages().some(p => p.includes(substr)), seconds);
  const page = lastPage();
  step('page:' + substr);
  return page;
}
async function waitLog(re, seconds = 20) {
  const line = await until(() => logs(re).at(-1), seconds);
  step('log:' + re);
  return line;
}
function choiceLines() {
  const flags = consoles.map(c => /^M4A page /.test(c.message));
  const start = flags.lastIndexOf(true);
  return consoles.slice(start + 1).filter(c => /^M4A choice \d+ /.test(c.message));
}
async function chooseMatch(re, seconds = 12) {
  const line = await until(() => choiceLines().find(c => re.test(c.message))?.message, seconds);
  const index = /^M4A choice (\d+) /.exec(line)[1];
  await key(index);
  step('choose:' + line.slice(12) + '#' + index);
  return index;
}
const choose = label => chooseMatch(new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
const keyMap = {
  e: { key: 'e', code: 'KeyE', keyCode: 69 },
  w: { key: 'w', code: 'KeyW', keyCode: 87 },
  a: { key: 'a', code: 'KeyA', keyCode: 65 },
  s: { key: 's', code: 'KeyS', keyCode: 83 },
  d: { key: 'd', code: 'KeyD', keyCode: 68 },
  '1': { key: '1', code: 'Digit1', keyCode: 49 },
  '2': { key: '2', code: 'Digit2', keyCode: 50 },
  '3': { key: '3', code: 'Digit3', keyCode: 51 },
  '4': { key: '4', code: 'Digit4', keyCode: 52 },
  '5': { key: '5', code: 'Digit5', keyCode: 53 },
  '6': { key: '6', code: 'Digit6', keyCode: 54 },
  '7': { key: '7', code: 'Digit7', keyCode: 55 },
  '8': { key: '8', code: 'Digit8', keyCode: 56 },
  '9': { key: '9', code: 'Digit9', keyCode: 57 },
  Enter: { key: 'Enter', code: 'Enter', keyCode: 13 },
  Escape: { key: 'Escape', code: 'Escape', keyCode: 27 },
};
async function key(name, ms = 130) {
  const params = keyMap[name];
  if (!params) throw Error('unknown key ' + name);
  await rpc('Input.dispatchKeyEvent', { type: 'rawKeyDown', ...params, windowsVirtualKeyCode: params.keyCode, nativeVirtualKeyCode: params.keyCode });
  await delay(ms);
  await rpc('Input.dispatchKeyEvent', { type: 'keyUp', ...params, windowsVirtualKeyCode: params.keyCode, nativeVirtualKeyCode: params.keyCode });
  await delay(400);
}
const results = { phase, url, profile, renderer: headed ? 'Chromium headed + system GPU (D3D11/ANGLE)' : 'Chromium headless + SwiftShader (ANGLE)', resources, requests, consoles, exceptions, dialogs, steps };
let point;
async function clickAt(p) {
  await rpc('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p });
  await rpc('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', buttons: 1, clickCount: 1 });
  await delay(120);
  await rpc('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 });
  await delay(500);
}
const clickCanvas = () => clickAt(point);
async function relock() {
  for (let i = 0; i < 3; i += 1) {
    if (await evaluate("document.pointerLockElement?.id === 'unity-canvas'")) return true;
    await clickCanvas();
  }
  return evaluate("document.pointerLockElement?.id === 'unity-canvas'");
}
// HUD 参考坐标（960x600, CanvasScaler ScaleWithScreenSize + match .5）→ 屏幕像素。
async function hudPoint(refX, refY) {
  return evaluate(`(()=>{const r=document.querySelector('#unity-canvas').getBoundingClientRect();
    const s=Math.sqrt((r.width/960)*(r.height/600));
    return {x:Math.round(r.x+r.width/2+(${refX})*s), y:Math.round(r.y+r.height/2-(${refY})*s)};})()`);
}
// 一次移动超过 ~40px 时，真实窗口里的指针会被窗口边缘钳制（headless 不会），
// 所以视角一律按小块累积，保证 headed 与 headless 得到相同的转角。
async function turn(dx, dy) {
  await rpc('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point });
  const steps = Math.max(1, Math.ceil(Math.max(Math.abs(dx), Math.abs(dy)) / 40));
  for (let i = 1; i <= steps; i += 1) {
    await rpc('Input.dispatchMouseEvent', { type: 'mouseMoved', x: point.x + Math.round(dx * i / steps), y: point.y + Math.round(dy * i / steps) });
    await delay(60);
  }
  await delay(300);
}
async function pitch(dy) {
  await turn(0, dy);
}
async function look(dx, dy) {
  await turn(dx, dy);
}
// 探针结论：Unity WebGL 不建隐藏输入框，Input.insertText 无效；
// 逐字符 char 事件可以正确进入 TMP_InputField（含中文），Enter 触发 onSubmit。
async function typeText(text) {
  for (const ch of text) {
    await rpc('Input.dispatchKeyEvent', { type: 'char', text: ch, unmodifiedText: ch, key: ch });
    await delay(70);
  }
  await delay(300);
}
async function freeText(text, label) {
  const input = await hudPoint(-55, 78);
  await clickAt(input);
  await typeText(text);
  await screenshot(label + '-typed');
  const offset = consoles.length;
  const newLog = re => consoles.slice(offset).find(c => re.test(c.message))?.message;
  await key('Enter');
  const submit = await until(() => newLog(/^M4C free text (submit|offline) /), 12);
  results.lastSubmit = submit;
  const reply = /offline/.test(submit) ? null : await until(() => newLog(/^M4C free text reply /), 25);
  results.lastReply = reply;
  await screenshot(label + '-reply');
  return { submit, reply, page: lastPage() };
}
async function loadPage() {
  await evaluate('delete window.m4cLoaderHidden');
  await rpc('Page.navigate', { url });
  const ms = await until(() => evaluate('window.m4cLoaderHidden'), 240);
  await delay(5000);
  return ms;
}
try {
  results.browser = (await rpc('Browser.getVersion')).product;
  const target = (await rpc('Target.createTarget', { url: 'about:blank' })).targetId;
  sessionId = (await rpc('Target.attachToTarget', { targetId: target, flatten: true })).sessionId;
  for (const api of ['Page', 'Network', 'Runtime']) await rpc(api + '.enable');
  await rpc('Network.setCacheDisabled', { cacheDisabled: true });
  await rpc('Page.addScriptToEvaluateOnNewDocument', { source: `
    new MutationObserver(() => {
      const bar = document.querySelector('#unity-loading-bar');
      if (bar && bar.style.display === 'none' && !window.m4cLoaderHidden) window.m4cLoaderHidden = performance.now();
    }).observe(document, { subtree: true, attributes: true, childList: true });
  ` });
  results.coldLoadMs = await loadPage();
  results.webgl = await evaluate("(()=>{const g=document.querySelector('#unity-canvas').getContext('webgl2');if(!g)return null;const i=g.getExtension('WEBGL_debug_renderer_info');return {api:g.getParameter(g.VERSION),renderer:i?g.getParameter(i.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER)}})()");
  point = await evaluate("(()=>{const r=document.querySelector('#unity-canvas').getBoundingClientRect();return {x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}})()");
  await screenshot('01-station');
  step('loaded', 'coldLoadMs=' + Math.round(results.coldLoadMs));

  // ---------- 打开老周对话（固定剧情回归）----------
  if (!(await relock())) throw Error('pointer lock was not acquired after clicking the canvas');
  step('pointer-locked');
  await key('e');
  results.laozhouOpening = await waitPage('老周');
  await screenshot('02-npc-opening');

  if (phase === 'chapter') {
    async function current(text) {
      return until(() => lastPage().includes(text) && lastPage(), 15);
    }
    async function walkToWatch() {
      if (!(await relock())) throw Error('Watch approach: missing pointer lock');
      await key('d', 400);
      await key('w', 530);
      await pitch(90);
      await key('e');
    }
    await choose('结束对话');
    await walkToWatch();
    await current('逐步查看');
    for (let i = 0; i < 5; i++) await chooseMatch(/查看 |重看 /);
    await current('QH-283');
    await choose('装袋待核');
    await screenshot('03-bag-confirmation');
    await choose('确认装袋并登记');
    await current('怀表已装袋待核');
    await current('第一章调查交接');
    await screenshot('04-bag-settlement');
    await choose('读取交接前检查点');
    await choose('确认读取');
    if (!(await relock())) throw Error('Checkpoint did not release the panel');
    await key('d', 320);
    await pitch(150);
    await key('e');
    await choose('查同号单据');
    await choose('翻副联册的对应档位');
    await choose('取出指定领件联');
    await current('E04');
    await loadPage();
    await walkToWatch();
    await choose('核对怀表原主');
    await choose('原主沈禾，今可由她书面指定的林遥领件');
    await current('已核');
    await screenshot('05-owner-conclusion');
    await loadPage();
    if (!(await relock())) throw Error('Linyao approach: missing pointer lock');
    await key('a', 1700);
    await key('w', 1270);
    await look(-750, 0);
    await key('e');
    await current('我妈留的领取凭号');
    await choose('出示 E03');
    await choose('出示 E04');
    await current('是我妈妈');
    await choose('办理今夜暂收');
    await current('交回受限封存');
    await screenshot('06-temporary-receipt');
    await choose('确认暂收并登记');
    await current('第一章调查交接');
    await current('林遥今夜暂收怀表');
    await screenshot('07-handover-settlement');
    results.reloadMs = await loadPage();
    if (!(await relock())) throw Error('Reentry: missing pointer lock');
    await key('d', 400);
    await key('w', 530);
    await key('d', 320);
    await pitch(240);
    await key('e');
    await choose('查看保管回执');
    await current('第二章资格已开放');
    await screenshot('08-persisted-settlement');
    step('both-choices-and-reentry-passed');
  } else if (phase === 'online') {
    // 1) 中文自由输入 → 服务端回合（真实 HTTP，不走本地 Mock）
    const first = await freeText('站台那晚亮着吗', '03-free-text');
    results.firstFreeText = first;
    if (!first.reply || !/ok=True/.test(first.reply)) throw Error('first free text turn failed: ' + first.reply);
    if (!first.page.includes('你：站台那晚亮着吗')) throw Error('the free text did not reach the dialogue page: ' + first.page);
    if (!/（/.test(first.page)) throw Error('the reply is missing its source attribution: ' + first.page);

    // 2) 中文自由输入 → Mock 超时回退（不得冒充真实模型）
    const timeout = await freeText('超时测试', '04-free-text-timeout');
    results.timeoutFreeText = timeout;
    if (!timeout.reply || !/reason=timeout/.test(timeout.reply)) throw Error('the mock timeout was not reported: ' + timeout.reply);
    if (!timeout.page.includes('模型回应超时')) throw Error('the timeout notice is missing: ' + timeout.page);
    step('mock-timeout-verified');

    // 3) 关闭对话，走到怀表，逐项看完五处细节 → E01
    await choose('结束对话');
    await delay(700);
    if (!(await relock())) throw Error('pointer lock was not restored after closing the dialogue');
    await key('d', 400);
    await key('w', 530);
    await pitch(90);
    await screenshot('05-watch-approach');
    await key('e');
    await waitPage('怀表');
    await screenshot('06-watch-parts');
    for (let i = 1; i <= 5; i += 1) {
      await chooseMatch(/查看 |重看 /);
      await delay(500);
      results['watchPart' + i] = lastPage();
    }
    const e01 = await waitPage('E01', 15);
    await screenshot('07-watch-e01');
    if (!e01.includes('QH-283')) throw Error('E01 page is missing the serial number: ' + e01);
    await choose('返回车站');
    await delay(700);
    if (!(await relock())) throw Error('pointer lock was not restored after the watch page');

    // 4) 失物包（编号已看到 → 查同号单据 → 旧修表收据 E03 → 翻副联册 → 指定领件联 E04）
    await key('d', 320);
    await pitch(150);
    await screenshot('08-package-approach');
    await key('e');
    results.packagePage = await waitPage('失物包');
    await chooseMatch(/查同号单据/);
    const e03 = await waitPage('E03', 15);
    await screenshot('09-package-e03');
    if (!e03.includes('沈禾')) throw Error('E03 page is missing the repair customer: ' + e03);
    await chooseMatch(/翻副联册的对应档位/);
    results.binderPage = await waitPage('失物副联册', 15);
    await screenshot('10-binder');
    if (!results.binderPage.includes('指定领件')) throw Error('the binder page is missing the designated receipt line: ' + results.binderPage);
    await chooseMatch(/取出指定领件联/);
    const e04 = await waitPage('E04', 15);
    await screenshot('11-binder-e04');
    if (!e04.includes('沈禾') && !e04.includes('领取')) throw Error('E04 page looks wrong: ' + e04);
    await choose('返回车站');
    await delay(700);
    if (!(await relock())) throw Error('pointer lock was not restored after the package page');

    // 5) 刷新（存档仍在）后回维修柜：E02 正面 → 背面索引 → E05
    results.reloadMs = await loadPage();
    if (!(await relock())) throw Error('pointer lock was not acquired after reload');
    await key('a', 1200);
    await key('w', 1400);
    await screenshot('12-cabinet-approach');
    await key('e');
    await waitPage('维修柜');
    await chooseMatch(/配电故障卡/);
    results.e02Page = await waitPage('E02', 15);
    await screenshot('13-cabinet-e02');
    await choose('返回车站');
    await delay(700);
    if (!(await relock())) throw Error('pointer lock was not restored after the cabinet page');
    await key('e');
    await waitPage('维修柜');
    await chooseMatch(/背面的索引/);
    results.indexPage = await waitPage('背面索引', 15);
    await screenshot('14-cabinet-index');
    await chooseMatch(/拾物与检点联/);
    results.e05Page = await waitPage('E05', 15);
    await screenshot('15-cabinet-e05');
    await choose('返回车站');
    await delay(700);
    if (!(await relock())) throw Error('pointer lock was not restored after the E05 page');

    // 6) 回到老周：Mock 回复（E01+E02 已到手）→ 出示 E02(D01) → E03+E04(D02) → E01+E05(D03)
    results.reloadMs = await loadPage();
    if (!(await relock())) throw Error('pointer lock was not acquired before the final dialogue');
    await key('e');
    await waitPage('老周');
    await screenshot('16-npc-return');
    try {
      const mockReply = await freeText('这两样对上了吗', '17-mock-reply');
      results.mockReply = mockReply;
      if (!mockReply.reply || !/source=mock/.test(mockReply.reply)) throw Error('expected a server mock reply: ' + mockReply.reply);
      if (!mockReply.page.includes('服务器模拟回复')) throw Error('the mock reply is not labelled synthetic: ' + mockReply.page);
      step('mock-reply-verified');
    } catch (error) {
      soft.push({ step: 'mock-reply', error: String(error) });
      await screenshot('17-mock-reply-failed').catch(() => {});
    }
    try {
      await chooseMatch(/出示 E02/);
      results.d01Page = await waitPage('我的灯到二十才摆好', 15);
      await screenshot('18-d01');
      await waitLog(/^M4C mirror ok E02/, 15);
      await chooseMatch(/出示 E03/);
      await waitLog(/^M4C mirror ok E03/, 15);
      await chooseMatch(/出示 E04/);
      const d02Mirror = await waitLog(/^M4C mirror ok E04/, 15);
      results.d02Mirror = d02Mirror;
      await screenshot('19-d02-mirror');
      await chooseMatch(/出示 E01/);
      await waitLog(/^M4C mirror ok E01/, 15);
      await chooseMatch(/出示 E05/);
      results.d03Page = await waitPage('冠头是歪的', 15);
      await screenshot('20-d03-disclosure');
      results.d03Events = logs(/dialogue\.disclosure_triggered D03/).length;
      if (results.d03Events !== 1) throw Error('D03 was triggered ' + results.d03Events + ' times, expected exactly 1');
      results.d01Events = logs(/dialogue\.disclosure_triggered D01/).length;
      if (results.d01Events !== 1) throw Error('D01 was triggered ' + results.d01Events + ' times, expected exactly 1');
    } catch (error) {
      soft.push({ step: 'npc-d01-d02-d03', error: String(error) });
      await screenshot('20-npc-disclosure-failed').catch(() => {});
    }

    // 7) 林遥：出示 E01 → REC.engraving；出示 E03+E04 → D02（第一章两位 NPC 都在场）
    try {
      await choose('结束对话');
      await delay(700);
      results.reloadMs = await loadPage();
      if (!(await relock())) throw Error('pointer lock was not acquired before Linyao');
      await key('a', 1700);
      await key('w', 1270);
      // 面向西侧的西值班窗（林遥站在窗旁）
      await look(-750, 0);
      await screenshot('21-linyao-approach');
      await key('e');
      results.linyaoPage = await waitPage('林遥', 15);
      if (!results.linyaoPage.includes('我妈留的领取凭号')) throw Error('Linyao opening line changed: ' + results.linyaoPage);
      await chooseMatch(/出示 E01/);
      results.engravingPage = await waitPage('四月十二', 15);
      await screenshot('22-linyao-engraving');
      await chooseMatch(/出示 E03/);
      await waitLog(/^M4C mirror ok E03/, 15);
      await chooseMatch(/出示 E04/);
      results.d02LinyaoPage = await waitPage('是我妈妈', 15);
      await screenshot('23-linyao-d02');
      results.recEvents = logs(/dialogue\.disclosure_triggered REC\.engraving/).length;
      if (results.recEvents !== 1) throw Error('REC.engraving was triggered ' + results.recEvents + ' times, expected exactly 1');
    } catch (error) {
      soft.push({ step: 'linyao', error: String(error) });
      await screenshot('23-linyao-failed').catch(() => {});
    }
  } else {
    // ---------- 离线 / 恢复 ----------
    const probe = await waitLog(/^M4C online dialogue (ready|offline)/, 25);
    results.probeLog = probe;
    if (phase === 'offline' && !/offline/.test(probe)) throw Error('expected offline: ' + probe);
    if (phase === 'resume' && !/ready/.test(probe)) throw Error('expected online: ' + probe);
    await screenshot('03-probe-' + phase);
    if (phase === 'offline') {
      // 服务不可用时：固定剧情与证据调查必须照常进行，自由输入明确拒绝。
      results.offlineOpening = lastPage();
      await freeText('站台那晚亮着吗', '04-offline-free-text');
      const offlineTurn = await waitLog(/^M4C free text offline /, 12);
      results.offlineFreeText = offlineTurn;
      results.offlineStatus = await evaluate("window.stationStatusProbe === undefined ? null : window.stationStatusProbe");
      await screenshot('05-offline-refusal');
      await choose('结束对话');
      await delay(700);
      if (!(await relock())) throw Error('pointer lock was not restored while offline');
      await key('d', 400);
      await key('w', 530);
      await pitch(90);
      await key('e');
      await waitPage('怀表');
      for (let i = 1; i <= 5; i += 1) { await chooseMatch(/查看 |重看 /); await delay(450); }
      const offlineE01 = await waitPage('E01', 15);
      await screenshot('06-offline-e01');
      if (!offlineE01.includes('QH-283')) throw Error('the offline watch record is incomplete: ' + offlineE01);
      step('offline-fixed-content-ok');
      // 刷新一次（服务仍不可用）：证据必须仍在存档里，本地固定对话照常可用。
      results.offlineReloadMs = await loadPage();
      if (!(await relock())) throw Error('pointer lock was not acquired after the offline reload');
      await key('e');
      results.offlineNpcPage = await waitPage('老周', 15);
      const offlineChoices = choiceLines().map(c => c.message);
      results.offlineFixedChoices = offlineChoices;
      await screenshot('07-offline-persisted');
      if (!offlineChoices.some(c => /出示 E01/.test(c))) throw Error('offline evidence did not persist: ' + offlineChoices.join(' / '));
      await chooseMatch(/出示 E01/);
      results.offlinePresentPage = await waitPage('21:17', 15);
      results.offlineApiCalls = requests.filter(r => r.url.includes('/api/v1/')).map(r => r.method + ' ' + r.url.replace(/^https?:\/\/[^/]+/, ''));
    } else {
      // 服务恢复后：存档里的证据仍在，固定选项与自由输入都能继续。
      const evidenceChoices = choiceLines().filter(c => /出示 E0\d/.test(c.message)).map(c => c.message);
      results.resumeEvidenceChoices = evidenceChoices;
      if (evidenceChoices.length < 5) throw Error('evidence did not survive the restart: ' + evidenceChoices.join(' / '));
      step('resume-evidence-kept');
      const resumed = await freeText('灯还亮着吗', '04-resume-free-text');
      results.resumeFreeText = resumed;
      if (!resumed.reply || !/ok=True/.test(resumed.reply)) throw Error('resumed free text failed: ' + resumed.reply);
      if (!resumed.page.includes('你：灯还亮着吗')) throw Error('the resumed turn did not reach the page: ' + resumed.page);
      await chooseMatch(/出示 E02/);
      const resumedD01 = await waitPage('我的灯到二十才摆好', 15);
      results.resumeD01Page = resumedD01;
      await screenshot('05-resume-d01');
    }
  }

  results.pages = pages();
  results.interactions = logs(/Station interaction:/i);
  results.mirrorLogs = logs(/^M4C mirror /);
  results.freeTextLogs = logs(/^M4C free text /);
  if (dialogs.length || exceptions.length) throw Error('Browser dialogs/exceptions; see browser.json');
  // 离线阶段故意让服务不可用：此时 API 请求失败与对应控制台报错都是预期行为，
  // 但仍不允许出现其它控制台错误或静态资源 4xx/5xx。
  const offlineNoise = /api\/v1|Failed to fetch|net::|ERR_|Connection|拒绝|404/i;
  const badConsoles = consoles.filter(c => c.type === 'error' && !(phase === 'offline' && offlineNoise.test(String(c.message))));
  if (badConsoles.length) throw Error('Console errors; see browser.json');
  const badResources = resources.filter(r => r.status >= 400 && !(phase === 'offline' && r.url.includes('/api/v1/')));
  if (badResources.length) throw Error('HTTP failures; see browser.json');
  results.completed = true;
} catch (error) {
  results.failure = String(error);
  results.pages = pages();
  steps.push({ name: 'FAILED', detail: String(error), console: consoles.slice(-30).map(c => c.message) });
  if (sessionId) await screenshot('failure').catch(() => {});
  process.exitCode = 1;
} finally {
  results.soft = soft;
  results.stderr = stderr;
  await writeFile(join(out, 'browser.json'), JSON.stringify(results, null, 2));
  if (chrome.exitCode === null) chrome.kill();
}
