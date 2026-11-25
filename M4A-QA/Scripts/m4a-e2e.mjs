// M4-A 端到端验收：真实 Chrome headless + SwiftShader 驱动 M4-A WebGL 构建。
// node m4a-e2e.mjs http://127.0.0.1:PORT <新建证据目录>
// 依据 M3-A 的 browser-smoke.mjs（CDP，零依赖）扩展为完整的证据/对话流程。
import { spawn } from 'node:child_process';
import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { setTimeout as delay } from 'node:timers/promises';

const [url, output] = process.argv.slice(2);
if (!url || new URL(url).hostname !== '127.0.0.1' || !output) {
  throw new Error('Provide a loopback HTTP URL and a new evidence directory.');
}
const out = resolve(output);
await mkdir(out, { recursive: true });
const profile = await mkdtemp(join(tmpdir(), 'echo-m4a-chrome-'));
const chrome = spawn(process.env.M4A_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe', [
  '--headless=new', '--remote-debugging-pipe', '--no-first-run', '--disable-default-apps',
  '--window-size=1200,850', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--mute-audio', '--user-data-dir=' + profile, 'about:blank',
], { stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe'], windowsHide: true });
let stderr = '';
chrome.stderr.on('data', d => { stderr = (stderr + d).slice(-12000); });
let seq = 0, sessionId;
const pending = new Map(), consoles = [], resources = [], exceptions = [], dialogs = [];
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
    } else if (msg.method === 'Network.responseReceived') {
      const { url, status, mimeType, headers } = msg.params.response;
      resources.push({ url, status, mimeType, encoding: headers['Content-Encoding'] });
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
const steps = [];
function step(name, detail = '') { steps.push({ name, detail, page: lastPage(), at: new Date().toISOString() }); }
async function waitPage(substr, seconds = 12) {
  await until(() => pages().some(p => p.includes(substr)), seconds);
  step('page:' + substr);
}
// HUD 每次 Page() 都会把当前选项写成 "M4A choice N 标签"，据此按标签选择，避免硬编码序号。
function choiceLines() {
  const flags = consoles.map(c => /^M4A page /.test(c.message));
  const start = flags.lastIndexOf(true);
  return consoles.slice(start + 1).filter(c => /^M4A choice \d+ /.test(c.message));
}
async function choose(label) {
  await until(() => choiceLines().some(c => c.message.includes(label)), 10);
  const line = choiceLines().find(c => c.message.includes(label)).message;
  const index = /^M4A choice (\d+) /.exec(line)[1];
  await key(index);
  step('choose:' + label + '#' + index);
  return index;
}
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
const results = { url, profile, renderer: 'Chromium headless + SwiftShader (ANGLE)', resources, consoles, exceptions, dialogs, steps };
let point;
async function clickCanvas() {
  await rpc('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point });
  await rpc('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', buttons: 1, clickCount: 1 });
  await delay(120);
  await rpc('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', clickCount: 1 });
  await delay(600);
}
async function relock() {
  for (let i = 0; i < 3; i += 1) {
    if (await evaluate("document.pointerLockElement?.id === 'unity-canvas'")) return true;
    await clickCanvas();
  }
  return evaluate("document.pointerLockElement?.id === 'unity-canvas'");
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
      if (bar && bar.style.display === 'none' && !window.m4aLoaderHidden) window.m4aLoaderHidden = performance.now();
    }).observe(document, { subtree: true, attributes: true, childList: true });
  ` });
  await rpc('Page.navigate', { url });
  results.coldLoadMs = await until(() => evaluate('window.m4aLoaderHidden'), 240);
  results.webgl = await evaluate("(()=>{const g=document.querySelector('#unity-canvas').getContext('webgl2');if(!g)return null;const i=g.getExtension('WEBGL_debug_renderer_info');return {api:g.getParameter(g.VERSION),renderer:i?g.getParameter(i.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER),vh:g.getParameter(g.MAX_VERTEX_UNIFORM_VECTORS)}})()");
  point = await evaluate("(()=>{const r=document.querySelector('#unity-canvas').getBoundingClientRect();return {x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}})()");
  await delay(6000);
  await screenshot('01-station');
  step('loaded', 'coldLoadMs=' + Math.round(results.coldLoadMs));

  // 1) 锁定鼠标 → 与老周对话 → 选择问题 → 结束
  if (!(await relock())) throw Error('pointer lock was not acquired after clicking the canvas');
  step('pointer-locked');
  await key('e');
  await waitPage('老周');
  await screenshot('02-npc-opening');
  await choose('问站台那晚的照明');
  await until(() => pages().filter(p => p.includes('老周')).length >= 2, 12);
  await screenshot('03-npc-question');
  await choose('结束对话'); // 关闭对话，回到车站
  await delay(600);
  if (!(await relock())) throw Error('pointer lock could not be restored after closing the dialogue');

  // 2) 走到维修柜，取得 E02（配电故障卡）
  await key('a', 1200);
  await key('w', 1400);
  await screenshot('04-cabinet-approach');
  await key('e');
  await waitPage('E02');
  await screenshot('05-cabinet-e02');
  await choose('返回车站');
  await delay(600);
  if (!(await relock())) throw Error('pointer lock could not be restored after closing the cabinet page');

  // 3) 走到怀表，观察表盘并登记 E01
  await key('s', 1250);
  await key('d', 1600);
  await rpc('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point });
  await rpc('Input.dispatchMouseEvent', { type: 'mouseMoved', x: point.x, y: point.y + 90 });
  await delay(700);
  await screenshot('06-watch-approach');
  await key('e');
  await waitPage('怀表');
  await screenshot('07-watch-dial');
  await choose('翻看背刻、编号和表冠');
  await waitPage('E01');
  await screenshot('08-watch-e01');
  await choose('返回车站');
  await delay(600);
  if (!(await relock())) throw Error('pointer lock could not be restored after closing the watch page');

  // 4) 回到老周，出示 E02，观察反馈变化
  await key('a', 400);
  await key('w', 270);
  await screenshot('09-npc-approach');
  await key('e');
  await until(() => pages().filter(p => p.includes('老周')).length >= 3, 12);
  await screenshot('10-npc-with-evidence');
  await choose('出示 E02');
  await waitPage('我的灯到二十才摆好'); // D01 披露文本，只有出示 E02 才会出现
  const disclosurePage = lastPage();
  await screenshot('11-disclosure');
  await choose('再问站台那晚的照明');
  await until(() => lastPage() !== disclosurePage, 12);
  await delay(500);
  const afterRepeat = lastPage();
  await screenshot('12-repeat-question');
  await choose('出示 E02'); // 同一会话再次出示：M3B 语义是复用已解锁的证词，且不重复触发披露事件
  await until(() => pages().filter(p => p.includes('我的灯到二十才摆好')).length >= 2, 12);
  results.repeatPresentationPage = lastPage();
  results.d01Events = consoles.filter(c => /dialogue\.disclosure_triggered D01/.test(c.message)).length;
  step('repeat-presentation', 'd01Events=' + results.d01Events);
  await screenshot('13-repeat-presentation');
  if (results.d01Events !== 1) throw Error('D01 was triggered ' + results.d01Events + ' times, expected exactly 1');

  // 5) 刷新页面，确认证据持久化后仍可出示
  await evaluate('delete window.m4aLoaderHidden');
  await rpc('Page.navigate', { url });
  results.reloadMs = await until(() => evaluate('window.m4aLoaderHidden'), 240);
  await delay(6000);
  await screenshot('14-reloaded');
  if (!(await relock())) throw Error('pointer lock was not acquired after reload');
  await key('e');
  await until(() => pages().filter(p => p.includes('老周')).length >= 4, 12);
  await choose('出示 E02');
  await until(() => pages().some(p => p.includes('我的灯到二十才摆好')), 12);
  await screenshot('15-persisted-disclosure');

  results.pages = pages();
  results.interactions = consoles.filter(c => /Station interaction:/i.test(c.message)).map(c => c.message);
  results.repeatPage = afterRepeat;
  if (results.interactions.length < 4) throw Error('Expected at least four interactions, got ' + results.interactions.length);
  if (dialogs.length || exceptions.length || consoles.some(c => c.type === 'error') || resources.some(r => r.status >= 400)) {
    throw Error('Browser errors or HTTP failures; see browser.json');
  }
  results.completed = true;
} catch (error) {
  results.failure = String(error);
  results.pages = pages();
  steps.push({ name: 'FAILED', detail: String(error), console: consoles.slice(-25).map(c => c.message) });
  if (sessionId) await screenshot('failure').catch(() => {});
  process.exitCode = 1;
} finally {
  results.stderr = stderr;
  await writeFile(join(out, 'browser.json'), JSON.stringify(results, null, 2));
  if (chrome.exitCode === null) chrome.kill();
}
